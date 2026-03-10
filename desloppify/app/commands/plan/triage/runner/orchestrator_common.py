"""Shared helpers for triage runner orchestrators."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from desloppify.engine.plan_triage import TRIAGE_STAGE_IDS

from ..helpers import has_triage_in_queue, inject_triage_stages
from ..lifecycle import (
    TriageLifecycleDeps,
    TriageStartRequest,
    ensure_triage_started as ensure_triage_started_with_lifecycle,
)
from ..services import TriageServices

STAGES: tuple[str, ...] = ("observe", "reflect", "organize", "enrich", "sense-check")


def parse_only_stages(raw: str | None) -> list[str]:
    """Parse --only-stages comma-separated string into validated stage list."""
    if not raw:
        return list(STAGES)
    stages = [s.strip().lower() for s in raw.split(",") if s.strip()]
    for stage in stages:
        if stage not in STAGES:
            raise ValueError(f"Unknown stage: {stage!r}. Valid: {', '.join(STAGES)}")
    return stages


def run_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def ensure_triage_started(
    plan: dict[str, Any],
    services: TriageServices,
    *,
    runner: str | None = None,
    state: dict[str, Any] | None = None,
    attestation: str | None = None,
) -> dict[str, Any]:
    """Auto-start triage if not started. Returns updated plan."""
    ensure_triage_started_with_lifecycle(
        plan,
        services=services,
        request=TriageStartRequest(
            state=state,
            attestation=attestation,
            log_action="triage_auto_start",
            log_actor="system",
            log_detail={
                "source": "runner_auto_start",
                "runner": runner,
                "injected_stage_ids": list(TRIAGE_STAGE_IDS),
            },
            start_message="  Planning mode auto-started.",
        ),
        deps=TriageLifecycleDeps(
            has_triage_in_queue=has_triage_in_queue,
            inject_triage_stages=inject_triage_stages,
        ),
    )
    return plan
