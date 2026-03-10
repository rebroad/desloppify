"""Registry for optional language hook modules consumed by detectors."""

from __future__ import annotations

import importlib
import logging
import sys
from collections import defaultdict

logger = logging.getLogger(__name__)

_hooks: dict[str, dict[str, object]] = defaultdict(dict)


def register_lang_hooks(
    lang_name: str,
    *,
    test_coverage: object | None = None,
) -> None:
    """Register optional detector hook modules for a language."""
    hooks = _hooks[lang_name]
    if test_coverage is not None:
        hooks["test_coverage"] = test_coverage


def _bootstrap_language_module(module: object) -> None:
    """Run optional language-module bootstrap hook(s).

    Preference order:
    1) ``register_hooks`` (hook-only bootstrap, no language registry mutation)
    2) ``register`` (legacy fallback)
    """
    register_hooks_fn = getattr(module, "register_hooks", None)
    if register_hooks_fn is not None:
        if not callable(register_hooks_fn):
            raise TypeError("Language module register_hooks entrypoint must be callable")
        register_hooks_fn()
        return

    register_fn = getattr(module, "register", None)
    if register_fn is None:
        return
    if not callable(register_fn):
        raise TypeError("Language module register entrypoint must be callable")
    register_fn()


def _load_language_module(module_name: str) -> object:
    """Resolve language module from sys.modules or import it lazily."""
    module = sys.modules.get(module_name)
    if module is not None:
        return module
    return importlib.import_module(module_name)


def _get_lang_hook(
    lang_name: str | None,
    hook_name: str,
) -> object | None:
    if not lang_name:
        return None
    hook = _hooks.get(lang_name, {}).get(hook_name)
    if hook is not None:
        return hook

    module_name = f"desloppify.languages.{lang_name}"
    try:
        module = _load_language_module(module_name)
    except (ImportError, ValueError, TypeError, RuntimeError, OSError) as exc:
        logger.debug(
            "Unable to import language hook package %s: %s", lang_name, exc
        )
        return None

    # Re-run explicit register() entrypoint to repopulate hook state after
    # registry clears in tests/refresh flows. Avoid module reload side effects.
    try:
        _bootstrap_language_module(module)
    except (ImportError, ValueError, TypeError, RuntimeError, OSError) as exc:
        logger.debug(
            "Unable to bootstrap language hook package %s: %s", lang_name, exc
        )
        return None

    return _hooks.get(lang_name, {}).get(hook_name)


def get_lang_hook(
    lang_name: str | None,
    hook_name: str,
) -> object | None:
    """Get a previously-registered language hook module."""
    return _get_lang_hook(lang_name, hook_name)


def clear_lang_hooks_for_tests() -> None:
    """Clear registry (test helper)."""
    _hooks.clear()


__all__ = [
    "clear_lang_hooks_for_tests",
    "get_lang_hook",
    "register_lang_hooks",
]
