"""Lifecycle visibility filtering for work-queue items."""

from __future__ import annotations

from desloppify.engine.plan_queue import NON_OBJECTIVE_DETECTORS
from desloppify.engine._work_queue.types import WorkQueueItem


def _has_objective_items(items: list[WorkQueueItem]) -> bool:
    """True if any objective mechanical work items remain in the queue.

    Checks both individual issues and collapsed clusters — clusters
    contain objective issues grouped by the queue builder.
    """
    return any(
        item.get("kind") in ("issue", "cluster")
        and item.get("detector", "") not in NON_OBJECTIVE_DETECTORS
        for item in items
    )


def _has_initial_reviews(items: list[WorkQueueItem]) -> bool:
    """True if any unassessed subjective dimensions need initial review."""
    return any(
        item.get("kind") == "subjective_dimension"
        and item.get("initial_review")
        for item in items
    )


def _is_endgame_only(item: WorkQueueItem) -> bool:
    """True if this item should only appear when the objective queue is drained."""
    return (
        item.get("kind") == "subjective_dimension"
        and not item.get("initial_review")
    )


def _has_endgame_subjective(items: list[WorkQueueItem]) -> bool:
    """True if any non-initial subjective review items are pending."""
    return any(_is_endgame_only(item) for item in items)


def _has_triage_stages(items: list[WorkQueueItem]) -> bool:
    """True if any pending triage stage items are in the queue."""
    return any(
        item.get("kind") == "workflow_stage"
        and str(item.get("id", "")).startswith("triage::")
        for item in items
    )


def _is_triage_stage(item: WorkQueueItem) -> bool:
    """True when item is a triage workflow stage."""
    return (
        item.get("kind") == "workflow_stage"
        and str(item.get("id", "")).startswith("triage::")
    )


def _is_force_visible(item: WorkQueueItem) -> bool:
    """True when the item is explicitly escalated past objective gating."""
    return bool(item.get("force_visible"))


def apply_lifecycle_filter(items: list[WorkQueueItem]) -> list[WorkQueueItem]:
    """Enforce lifecycle visibility rules."""
    if _has_initial_reviews(items):
        return [
            item for item in items
            if item.get("kind") == "subjective_dimension" and item.get("initial_review")
        ]
    # Enforce fixed endgame phase order:
    #   subjective review -> score workflow -> triage
    # When non-initial subjective reruns are pending and objective work is
    # already drained, keep focus on subjective reruns and defer workflow/triage.
    if _has_endgame_subjective(items) and not _has_objective_items(items):
        return [
            item for item in items
            if _is_endgame_only(item) or _is_force_visible(item)
        ]
    if _has_triage_stages(items):
        # Triage should not block while objective queue work still exists.
        if _has_objective_items(items):
            return [
                item for item in items
                if (
                    (not _is_triage_stage(item) or _is_force_visible(item))
                    and (not _is_endgame_only(item) or _is_force_visible(item))
                )
            ]
        return [
            item for item in items
            if item.get("kind") in ("workflow_stage", "workflow_action")
        ]
    if not _has_objective_items(items):
        return items
    return [item for item in items if not _is_endgame_only(item) or _is_force_visible(item)]


__all__ = ["apply_lifecycle_filter"]
