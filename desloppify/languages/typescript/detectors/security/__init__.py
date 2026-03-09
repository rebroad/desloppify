"""TypeScript security detector package."""

from __future__ import annotations

from .detector import _detect_ts_security_result, detect_ts_security

__all__ = [
    "_detect_ts_security_result",
    "detect_ts_security",
]
