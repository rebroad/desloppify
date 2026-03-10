"""Language registration API plus compatibility exports for legacy callers.

Runtime code should prefer ``desloppify.languages.framework`` for framework
access; this module focuses on registration and language lookup.

Compatibility owner: language-framework
Removal target (legacy module exports): 2026-06-30
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from desloppify.languages.framework import (
    LangConfig,
    auto_detect_lang,
    available_langs,
    get_lang,
    make_lang_config,
)
from desloppify.languages._framework import discovery as _discovery_mod
from desloppify.languages._framework import registry_state as _registry_state_mod
from desloppify.languages._framework import resolution as _resolution_mod
from desloppify.languages._framework import runtime as _runtime_mod
from desloppify.languages._framework.contract_validation import validate_lang_contract
from desloppify.languages._framework.policy import REQUIRED_DIRS, REQUIRED_FILES
from desloppify.languages._framework.registration import register_lang_class_with
from desloppify.languages._framework.structure_validation import validate_lang_structure

T = TypeVar("T")

# Backward-compatible module aliases for callers still importing them here.
discovery = _discovery_mod
registry_state = _registry_state_mod
resolution = _resolution_mod
runtime = _runtime_mod


def register_lang(name: str) -> Callable[[T], T]:
    """Decorator to register a language config class.

    Validates structure, instantiates the class, validates the contract,
    and stores the *instance* in the registry.
    """

    def decorator(cls: T) -> T:
        register_lang_class_with(
            name,
            cls,
            validate_lang_structure_fn=validate_lang_structure,
        )
        return cls

    return decorator


def register_generic_lang(name: str, cfg: LangConfig) -> None:
    """Register a pre-built language plugin instance (no package structure required)."""
    validate_lang_contract(name, cfg)
    registry_state.register(name, cfg)


def reload_lang_plugins() -> list[str]:
    """Force plugin rediscovery and return refreshed language names."""
    discovery.load_all(force_reload=True)
    return sorted(registry_state.all_keys())


__all__ = [
    "REQUIRED_FILES",
    "REQUIRED_DIRS",
    "register_lang",
    "register_generic_lang",
    "reload_lang_plugins",
    "get_lang",
    "available_langs",
    "auto_detect_lang",
    "make_lang_config",
    "validate_lang_structure",
    "validate_lang_contract",
]
