# alpha statistics and rules

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Optional, Literal

import numpy as np
from PIL import Image

from .io import ensure_rgba, load_image

ProgressCb = Callable[[int, int, Path, str], None]
Status = Literal["PASS", "WARN", "FAIL"]


@dataclass(frozen=True)
class AlphaStats:
    width: int
    height: int
    min: int
    max: int
    mean: float
    std: float
    pct_zero: float
    pct_255: float
    pct_mid: float  # 1..254


@dataclass(frozen=True)
class ValidationRules:
    warn_pct_255: float = 99.9
    warn_pct_zero: float = 99.9
    warn_std_lt: float = 1.0
    warn_range_le: int = 2  # max-min <= this -> likely constant
    fail_no_alpha: bool = False  # set True if your workflow requires alpha


@dataclass(frozen=True)
class AlphaValidationResult:
    path: str
    has_alpha: bool
    status: Status
    messages: list[str]
    stats: Optional[AlphaStats]


def _alpha_array(img: Image.Image) -> Optional[np.ndarray]:
    rgba = ensure_rgba(img)
    bands = rgba.getbands()
    if "A" not in bands:
        return None
    a = rgba.split()[3]
    arr = np.asarray(a, dtype=np.uint8)
    return arr


def compute_alpha_stats(alpha_arr: np.ndarray) -> AlphaStats:
    h, w = alpha_arr.shape[:2]
    mn = int(alpha_arr.min())
    mx = int(alpha_arr.max())
    mean = float(alpha_arr.mean())
    std = float(alpha_arr.std())

    total = alpha_arr.size
    pct_zero = float((alpha_arr == 0).sum() * 100.0 / total)
    pct_255 = float((alpha_arr == 255).sum() * 100.0 / total)
    pct_mid = float(((alpha_arr > 0) & (alpha_arr < 255)).sum() * 100.0 / total)

    return AlphaStats(
        width=w,
        height=h,
        min=mn,
        max=mx,
        mean=mean,
        std=std,
        pct_zero=pct_zero,
        pct_255=pct_255,
        pct_mid=pct_mid,
    )


def validate_alpha_file(path: Path, *, rules: ValidationRules = ValidationRules()) -> AlphaValidationResult:
    img = load_image(path)
    alpha_arr = _alpha_array(img)
    if alpha_arr is None:
        status: Status = "FAIL" if rules.fail_no_alpha else "WARN"
        msg = "No alpha channel."
        return AlphaValidationResult(
            path=str(path),
            has_alpha=False,
            status=status,
            messages=[msg],
            stats=None,
        )

    stats = compute_alpha_stats(alpha_arr)
    messages: list[str] = []
    status: Status = "PASS"

    if stats.pct_255 >= rules.warn_pct_255:
        messages.append(f"Alpha is ~all opaque ({stats.pct_255:.2f}% == 255).")
        status = "WARN"
    if stats.pct_zero >= rules.warn_pct_zero:
        messages.append(f"Alpha is ~all transparent ({stats.pct_zero:.2f}% == 0).")
        status = "WARN"
    if stats.std < rules.warn_std_lt and (stats.max - stats.min) <= rules.warn_range_le:
        messages.append(
            f"Alpha is near-constant (std={stats.std:.3f}, range={stats.max - stats.min})."
        )
        status = "WARN"

    # If it has alpha but it is truly useless, you might choose FAIL in your GUI later.
    return AlphaValidationResult(
        path=str(path),
        has_alpha=True,
        status=status,
        messages=messages,
        stats=stats,
    )


def validate_alpha_files(
    paths: list[Path],
    *,
    rules: ValidationRules = ValidationRules(),
    continue_on_error: bool = True,
    progress_cb: Optional[ProgressCb] = None,
    cancel_flag=None,
) -> list[AlphaValidationResult]:
    files = list(paths)
    total = len(files)
    results: list[AlphaValidationResult] = []

    for i, p in enumerate(files, start=1):
        if cancel_flag is not None and getattr(cancel_flag, "is_set", lambda: False)():
            break

        if progress_cb:
            progress_cb(i - 1, total, p, "Validating alpha")

        try:
            res = validate_alpha_file(p, rules=rules)
            results.append(res)
        except Exception as e:
            if not continue_on_error:
                raise
            results.append(
                AlphaValidationResult(
                    path=str(p),
                    has_alpha=False,
                    status="FAIL",
                    messages=[f"Error reading/processing file: {e}"],
                    stats=None,
                )
            )

        if progress_cb:
            progress_cb(i, total, p, "Done")

    return results


def results_to_json(results: list[AlphaValidationResult], out_path: Path) -> None:
    import json

    payload = []
    for r in results:
        d = {
            "path": r.path,
            "has_alpha": r.has_alpha,
            "status": r.status,
            "messages": r.messages,
            "stats": asdict(r.stats) if r.stats else None,
        }
        payload.append(d)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def results_to_csv(results: list[AlphaValidationResult], out_path: Path) -> None:
    import csv

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "path",
                "status",
                "has_alpha",
                "width",
                "height",
                "min",
                "max",
                "mean",
                "std",
                "pct_zero",
                "pct_255",
                "pct_mid",
                "messages",
            ]
        )
        for r in results:
            if r.stats:
                s = r.stats
                row = [
                    r.path,
                    r.status,
                    r.has_alpha,
                    s.width,
                    s.height,
                    s.min,
                    s.max,
                    f"{s.mean:.4f}",
                    f"{s.std:.4f}",
                    f"{s.pct_zero:.4f}",
                    f"{s.pct_255:.4f}",
                    f"{s.pct_mid:.4f}",
                    " | ".join(r.messages),
                ]
            else:
                row = [r.path, r.status, r.has_alpha] + [""] * 9 + [" | ".join(r.messages)]
            w.writerow(row)