# luminance/key/threshold alpha generators

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Literal

import numpy as np
from PIL import Image

from .io import (
    AlphaIOError,
    ensure_rgb,
    ensure_l,
    infer_output_path,
    load_image,
    save_mask_png,
    expand_inputs,
)

ProgressCb = Callable[[int, int, Path, str], None]
GenerateType = Literal["luminance", "threshold", "colorkey"]


@dataclass(frozen=True)
class GenerateOptions:
    kind: GenerateType = "luminance"
    threshold: int = 128  # 0..255
    key_color: tuple[int, int, int] = (0, 0, 0)
    tolerance: int = 20  # 0..255
    invert: bool = False


def generate_alpha_luminance(img: Image.Image) -> Image.Image:
    rgb = ensure_rgb(img)
    return rgb.convert("L")


def generate_alpha_threshold(img: Image.Image, threshold: int) -> Image.Image:
    if not (0 <= threshold <= 255):
        raise AlphaIOError("threshold must be between 0 and 255")
    lum = generate_alpha_luminance(img)
    arr = np.asarray(lum, dtype=np.uint8)
    out = np.where(arr >= threshold, 255, 0).astype(np.uint8)
    return Image.fromarray(out, mode="L")


def generate_alpha_colorkey(
    img: Image.Image,
    key_rgb: tuple[int, int, int],
    tolerance: int,
) -> Image.Image:
    if not (0 <= tolerance <= 255):
        raise AlphaIOError("tolerance must be between 0 and 255")
    rgb = ensure_rgb(img)
    arr = np.asarray(rgb, dtype=np.int16)  # avoid overflow
    key = np.array(key_rgb, dtype=np.int16).reshape((1, 1, 3))
    diff = np.abs(arr - key)
    dist = diff.max(axis=2)  # Chebyshev distance (fast, intuitive)
    # where color is close to key -> transparent (0); otherwise opaque (255)
    out = np.where(dist <= tolerance, 0, 255).astype(np.uint8)
    return Image.fromarray(out, mode="L")


def _maybe_invert(mask: Image.Image, invert: bool) -> Image.Image:
    m = ensure_l(mask)
    if not invert:
        return m
    return Image.eval(m, lambda v: 255 - v)


def generate_alpha_file(
    in_path: Path,
    out_mask_path: Path,
    opts: GenerateOptions,
    *,
    overwrite: bool = False,
) -> Path:
    img = load_image(in_path)

    if opts.kind == "luminance":
        mask = generate_alpha_luminance(img)
    elif opts.kind == "threshold":
        mask = generate_alpha_threshold(img, opts.threshold)
    elif opts.kind == "colorkey":
        mask = generate_alpha_colorkey(img, opts.key_color, opts.tolerance)
    else:
        raise AlphaIOError(f"Unknown generation kind: {opts.kind}")

    mask = _maybe_invert(mask, opts.invert)
    save_mask_png(mask, out_mask_path, overwrite=overwrite)
    return out_mask_path


def generate_alpha_files(
    in_paths: list[Path],
    out_dir: Path,
    opts: GenerateOptions,
    *,
    out_suffix: str = "_alpha",
    overwrite: bool = False,
    continue_on_error: bool = True,
    progress_cb: Optional[ProgressCb] = None,
    cancel_flag=None,
) -> list[Path]:
    files = expand_inputs(in_paths)
    total = len(files)
    outputs: list[Path] = []

    for i, p in enumerate(files, start=1):
        if cancel_flag is not None and getattr(cancel_flag, "is_set", lambda: False)():
            break

        if progress_cb:
            progress_cb(i - 1, total, p, "Generating alpha")

        out_mask = infer_output_path(p, out_dir, suffix=out_suffix, ext=".png")

        try:
            outputs.append(generate_alpha_file(p, out_mask, opts, overwrite=overwrite))
        except Exception:
            if not continue_on_error:
                raise
            continue

        if progress_cb:
            progress_cb(i, total, p, "Done")

    return outputs