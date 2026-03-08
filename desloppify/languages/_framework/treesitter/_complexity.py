"""AST-based complexity signals using tree-sitter.

Compatibility facade that re-exports metric builders from focused modules.
"""

from __future__ import annotations

from ._complexity_callbacks import make_callback_depth_compute
from ._complexity_function_metrics import (
    make_cyclomatic_complexity_compute,
    make_long_functions_compute,
    make_max_params_compute,
)
from ._complexity_nesting import compute_nesting_depth_ts, make_nesting_depth_compute

__all__ = [
    "compute_nesting_depth_ts",
    "make_callback_depth_compute",
    "make_cyclomatic_complexity_compute",
    "make_long_functions_compute",
    "make_max_params_compute",
    "make_nesting_depth_compute",
]
