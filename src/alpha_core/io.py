# load/save helpers
# src/alpha_core/io.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image


SUPPORTED_IMAGE_EXTS = {".png", ".tga", ".tif", ".tiff", ".bmp", ".webp", ".jpg", ".jpeg"}


class AlphaIOError(RuntimeError):
    pass


def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def is_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTS


def load_image(path: Path) -> Image.Image:
    try:
        img = Image.open(path)
        img.load()
        return img
    except Exception as e:
        raise AlphaIOError(f"Failed to load image: {path} ({e})") from e


def ensure_rgba(img: Image.Image) -> Image.Image:
    if img.mode == "RGBA":
        return img
    if img.mode == "P":
        return img.convert("RGBA")
    return img.convert("RGBA")


def ensure_rgb(img: Image.Image) -> Image.Image:
    if img.mode == "RGB":
        return img
    if img.mode == "RGBA":
        return img.convert("RGB")
    if img.mode == "P":
        return img.convert("RGB")
    return img.convert("RGB")


def ensure_l(img: Image.Image) -> Image.Image:
    """Ensure 8-bit grayscale."""
    if img.mode == "L":
        return img
    if img.mode == "RGBA":
        return img.convert("RGB").convert("L")
    if img.mode == "RGB":
        return img.convert("L")
    return img.convert("L")


def save_png(img: Image.Image, path: Path, *, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise AlphaIOError(f"Refusing to overwrite existing file: {path}")
    safe_mkdir(path.parent)
    try:
        img.save(path, format="PNG")
    except Exception as e:
        raise AlphaIOError(f"Failed to save PNG: {path} ({e})") from e


def save_mask_png(mask: Image.Image, path: Path, *, overwrite: bool = False) -> None:
    mask_l = ensure_l(mask)
    save_png(mask_l, path, overwrite=overwrite)


def infer_output_path(
    in_path: Path,
    out_dir: Path,
    *,
    suffix: str = "",
    ext: str = ".png",
) -> Path:
    stem = in_path.stem
    return out_dir / f"{stem}{suffix}{ext}"


def expand_inputs(paths: Iterable[Path]) -> list[Path]:
    """Expand directories into contained images; return sorted unique list."""
    out: list[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if is_image_file(child):
                    out.append(child)
        elif is_image_file(p):
            out.append(p)
    # unique (stable)
    seen = set()
    uniq: list[Path] = []
    for p in out:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq