# src/alpha_core/__init__.py
"""
alpha_core: headless core library for alpha-image operations (split/combine/validate/generate).

This package is designed to be called from a GUI (e.g., PySide6 app) and/or CLI.
"""

from .naming import PairingRule, default_rule, build_pairs, list_images
from .ops_split import split_alpha, split_alpha_file, split_alpha_files
from .ops_combine import combine_alpha, combine_alpha_file, combine_alpha_files
from .ops_validate import (
    AlphaStats,
    ValidationRules,
    AlphaValidationResult,
    validate_alpha_file,
    validate_alpha_files,
    results_to_csv,
    results_to_json,
)
from .ops_generate import (
    GenerateOptions,
    generate_alpha_luminance,
    generate_alpha_threshold,
    generate_alpha_colorkey,
    generate_alpha_file,
    generate_alpha_files,
)

__all__ = [
    # naming
    "PairingRule",
    "default_rule",
    "build_pairs",
    "list_images",
    # split
    "split_alpha",
    "split_alpha_file",
    "split_alpha_files",
    # combine
    "combine_alpha",
    "combine_alpha_file",
    "combine_alpha_files",
    # validate
    "AlphaStats",
    "ValidationRules",
    "AlphaValidationResult",
    "validate_alpha_file",
    "validate_alpha_files",
    "results_to_csv",
    "results_to_json",
    # generate
    "GenerateOptions",
    "generate_alpha_luminance",
    "generate_alpha_threshold",
    "generate_alpha_colorkey",
    "generate_alpha_file",
    "generate_alpha_files",
]

__version__ = "0.1.0"