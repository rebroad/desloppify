"""Compatibility bridge to grouped tree-sitter namespace module.

Canonical implementation now lives in desloppify.languages._framework.treesitter.analysis.smells.
"""

from __future__ import annotations

from importlib import import_module

_IMPL = import_module("desloppify.languages._framework.treesitter.analysis.smells")
_EXPORTS = [name for name in dir(_IMPL) if not name.startswith("__")]
globals().update({name: getattr(_IMPL, name) for name in _EXPORTS})
_PUBLIC = getattr(_IMPL, "__all__", None)
if _PUBLIC is None:
    _PUBLIC = [name for name in _EXPORTS if not name.startswith("_")]
__all__ = list(_PUBLIC)
