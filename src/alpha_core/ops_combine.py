# combine rgb + mask into rgba

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Literal

from PIL import Image

from .io import (
    AlphaIOError,
    ensure_l,
    ensure_rgb,
    infer_output_path,
    load_image,
    save_png,
)

ProgressCb = Callable[[int, int, Path, str], None]
ResizeMode = Literal["error", "resize"]
ResampleMode = Literal["nearest", "bilinear"]


def _resample_to_pil(resample: ResampleMode) -> int:
    if resample == "bilinear":
        return Image.Resampling.BILINEAR
    return Image.Resampling.NEAREST


def combine_alpha(
    rgb_img: Image.Image,
    alpha_mask: Image.Image,
    *,
    invert: bool = False,
    resize_mode: ResizeMode = "error",
    resample: ResampleMode = "nearest",
) -> Image.Image:
    rgb = ensure_rgb(rgb_img)
    mask = ensure_l(alpha_mask)

    if mask.size != rgb.size:
        if resize_mode == "error":
            raise AlphaIOError(
                f"Mask size {mask.size} does not match RGB size {rgb.size}."
            )
        mask = mask.resize(rgb.size, resample=_resample_to_pil(resample))

    if invert:
        mask = Image.eval(mask, lambda v: 255 - v)

    r, g, b = rgb.split()
    rgba = Image.merge("RGBA", (r, g, b, mask))
    return rgba


def combine_alpha_file(
    rgb_path: Path,
    alpha_path: Path,
    out_path: Path,
    *,
    invert: bool = False,
    resize_mode: ResizeMode = "error",
    resample: ResampleMode = "nearest",
    overwrite: bool = False,
) -> None:
    rgb = load_image(rgb_path)
    a = load_image(alpha_path)
    out = combine_alpha(rgb, a, invert=invert, resize_mode=resize_mode, resample=resample)
    save_png(out, out_path, overwrite=overwrite)


def combine_alpha_files(
    pairs: list[tuple[Path, Path]],
    out_dir: Path,
    *,
    out_suffix: str = "_rgba",
    invert: bool = False,
    resize_mode: ResizeMode = "error",
    resample: ResampleMode = "nearest",
    overwrite: bool = False,
    continue_on_error: bool = True,
    progress_cb: Optional[ProgressCb] = None,
    cancel_flag=None,
) -> list[Path]:
    total = len(pairs)
    outputs: list[Path] = []

    for i, (rgb_p, a_p) in enumerate(pairs, start=1):
        if cancel_flag is not None and getattr(cancel_flag, "is_set", lambda: False)():
            break

        if progress_cb:
            progress_cb(i - 1, total, rgb_p, "Combining alpha")

        out_path = infer_output_path(rgb_p, out_dir, suffix=out_suffix, ext=".png")

        try:
            combine_alpha_file(
                rgb_p,
                a_p,
                out_path,
                invert=invert,
                resize_mode=resize_mode,
                resample=resample,
                overwrite=overwrite,
            )
            outputs.append(out_path)
        except Exception:
            if not continue_on_error:
                raise
            continue

        if progress_cb:
            progress_cb(i, total, rgb_p, "Done")

    return outputs