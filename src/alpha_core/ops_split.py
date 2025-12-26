# split alpha to mask

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from .io import (
    AlphaIOError,
    ensure_rgb,
    ensure_rgba,
    infer_output_path,
    load_image,
    save_mask_png,
    save_png,
    expand_inputs,
)

ProgressCb = Callable[[int, int, Path, str], None]


def split_alpha(
    img: Image.Image,
    *,
    on_missing_alpha: str = "opaque",  # "opaque" or "error"
) -> tuple[Image.Image, Image.Image]:
    rgba = ensure_rgba(img)
    if "A" not in rgba.getbands():
        if on_missing_alpha == "error":
            raise AlphaIOError("Image has no alpha channel.")
        rgb = ensure_rgb(rgba)
        alpha = Image.new("L", rgba.size, color=255)
        return rgb, alpha

    r, g, b, a = rgba.split()
    rgb = Image.merge("RGB", (r, g, b))
    return rgb, a


def split_alpha_file(
    in_path: Path,
    out_rgb_path: Path,
    out_alpha_path: Path,
    *,
    overwrite: bool = False,
    on_missing_alpha: str = "opaque",
) -> None:
    img = load_image(in_path)
    rgb, alpha = split_alpha(img, on_missing_alpha=on_missing_alpha)
    save_png(rgb, out_rgb_path, overwrite=overwrite)
    save_mask_png(alpha, out_alpha_path, overwrite=overwrite)


def split_alpha_files(
    in_paths: list[Path],
    out_dir: Path,
    *,
    rgb_suffix: str = "_rgb",
    alpha_suffix: str = "_alpha",
    overwrite: bool = False,
    on_missing_alpha: str = "opaque",
    continue_on_error: bool = True,
    progress_cb: Optional[ProgressCb] = None,
    cancel_flag=None,  # threading.Event-like; must have is_set()
) -> list[Path]:
    files = expand_inputs(in_paths)
    total = len(files)
    outputs: list[Path] = []

    for i, p in enumerate(files, start=1):
        if cancel_flag is not None and getattr(cancel_flag, "is_set", lambda: False)():
            break

        if progress_cb:
            progress_cb(i - 1, total, p, "Splitting alpha")

        out_rgb = infer_output_path(p, out_dir, suffix=rgb_suffix, ext=".png")
        out_a = infer_output_path(p, out_dir, suffix=alpha_suffix, ext=".png")
        try:
            split_alpha_file(
                p,
                out_rgb,
                out_a,
                overwrite=overwrite,
                on_missing_alpha=on_missing_alpha,
            )
            outputs.extend([out_rgb, out_a])
        except Exception:
            if not continue_on_error:
                raise
            # otherwise skip and continue
            continue

        if progress_cb:
            progress_cb(i, total, p, "Done")

    return outputs