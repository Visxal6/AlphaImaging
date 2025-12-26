# file pairing rules

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from .io import expand_inputs, is_image_file


PairingMode = Literal["suffix", "folder", "exact"]


@dataclass(frozen=True)
class PairingRule:
    mode: PairingMode = "suffix"
    # suffix mode: foo.png <-> foo_alpha.png
    alpha_suffix: str = "_alpha"
    rgb_suffix: str = ""  # optional; usually empty
    # folder mode: rgb/foo.png <-> alpha/foo.png
    rgb_dir_name: str = "rgb"
    alpha_dir_name: str = "alpha"
    # general
    case_sensitive: bool = False


def default_rule() -> PairingRule:
    return PairingRule()


def _norm(s: str, *, case_sensitive: bool) -> str:
    return s if case_sensitive else s.lower()


def list_images(paths: Iterable[Path]) -> list[Path]:
    return expand_inputs([Path(p) for p in paths])


def _key_for_path(p: Path, rule: PairingRule, *, is_alpha: bool) -> str:
    stem = p.stem
    if rule.mode == "suffix":
        # remove suffixes to get the "base" key
        s = stem
        if is_alpha and rule.alpha_suffix and s.endswith(rule.alpha_suffix):
            s = s[: -len(rule.alpha_suffix)]
        if (not is_alpha) and rule.rgb_suffix and s.endswith(rule.rgb_suffix):
            s = s[: -len(rule.rgb_suffix)]
        return _norm(s, case_sensitive=rule.case_sensitive)

    if rule.mode == "folder":
        # key is relative path under rgb/alpha, without extension
        parts = list(p.parts)
        # find rgb_dir_name / alpha_dir_name occurrence (best effort)
        dir_name = rule.alpha_dir_name if is_alpha else rule.rgb_dir_name
        try:
            idx = parts.index(dir_name)
            rel = Path(*parts[idx + 1 :]).with_suffix("")
        except ValueError:
            rel = p.with_suffix("").name  # fallback: just name
        return _norm(str(rel), case_sensitive=rule.case_sensitive)

    # exact
    return _norm(stem, case_sensitive=rule.case_sensitive)


def build_pairs(
    rgb_paths: list[Path],
    alpha_paths: list[Path],
    rule: PairingRule,
) -> tuple[list[tuple[Path, Path]], list[Path], list[Path]]:
    """
    Returns:
      pairs: list[(rgb_path, alpha_path)]
      unpaired_rgb: rgb files that couldn't find a match
      unpaired_alpha: alpha files that were not used
    """
    rgb_map: dict[str, Path] = {}
    alpha_map: dict[str, Path] = {}

    for p in rgb_paths:
        if is_image_file(p):
            k = _key_for_path(Path(p), rule, is_alpha=False)
            rgb_map.setdefault(k, Path(p))

    for p in alpha_paths:
        if is_image_file(p):
            k = _key_for_path(Path(p), rule, is_alpha=True)
            alpha_map.setdefault(k, Path(p))

    pairs: list[tuple[Path, Path]] = []
    used_alpha: set[str] = set()

    for k, rgb_p in rgb_map.items():
        a = alpha_map.get(k)
        if a is not None:
            pairs.append((rgb_p, a))
            used_alpha.add(k)

    unpaired_rgb = [p for k, p in rgb_map.items() if k not in used_alpha and k not in alpha_map]
    unpaired_alpha = [p for k, p in alpha_map.items() if k not in used_alpha]

    pairs.sort(key=lambda t: str(t[0]))
    unpaired_rgb.sort(key=lambda p: str(p))
    unpaired_alpha.sort(key=lambda p: str(p))
    return pairs, unpaired_rgb, unpaired_alpha