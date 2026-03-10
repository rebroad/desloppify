"""Sync subdomain for plan queue reconciliation helpers.

This package groups sync concerns that were previously in the flat
``engine._plan`` namespace:
- ``context``: shared cycle/objective backlog predicates
- ``dimensions``: subjective dimension queue sync
- ``triage``: triage-stage queue sync
- ``workflow``: workflow gate queue sync
- ``auto_prune``: auto-cluster stale pruning helper
"""

__all__ = [
    "auto_prune",
    "context",
    "dimensions",
    "triage",
    "workflow",
]
