"""Compatibility facade for TypeScript function-level smell detectors."""

from __future__ import annotations

from desloppify.languages.typescript.detectors._smell_detectors_core import (
    _find_function_start,
)
from desloppify.languages.typescript.detectors._smell_detectors_flow import (
    _detect_async_no_await,
    _detect_empty_if_chains,
    _detect_error_no_throw,
    _detect_high_cyclomatic_complexity,
    _detect_monster_functions,
    _detect_nested_closures,
    _detect_stub_functions,
)
from desloppify.languages.typescript.detectors._smell_detectors_safety import (
    _detect_catch_return_default,
    _detect_dead_useeffects,
    _detect_swallowed_errors,
    _detect_switch_no_default,
    _detect_window_globals,
)

__all__ = [
    "_detect_async_no_await",
    "_detect_catch_return_default",
    "_detect_dead_useeffects",
    "_detect_empty_if_chains",
    "_detect_error_no_throw",
    "_detect_high_cyclomatic_complexity",
    "_detect_monster_functions",
    "_detect_nested_closures",
    "_detect_stub_functions",
    "_detect_swallowed_errors",
    "_detect_switch_no_default",
    "_detect_window_globals",
    "_find_function_start",
]
