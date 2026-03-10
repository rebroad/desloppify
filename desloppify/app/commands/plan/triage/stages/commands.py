"""Stage command entrypoints for triage flow, grouped under triage stages."""

from __future__ import annotations

import argparse

from desloppify.base.output.terminal import colorize
from desloppify.base.output.user_message import print_user_message

from ..helpers import (
    has_triage_in_queue,
    inject_triage_stages,
    print_cascade_clear_feedback,
)
from ..services import TriageServices
from ..stage_flow_enrich import EnrichStageDeps, run_stage_enrich
from ..stage_flow_observe_reflect_organize import (
    _cmd_stage_observe as _cmd_stage_observe_impl,
)
from ..stage_flow_observe_reflect_organize import (
    _cmd_stage_organize,
    _cmd_stage_reflect,
    cmd_stage_organize,
    cmd_stage_reflect,
)
from ..stage_flow_sense_check import (
    SenseCheckStageDeps,
    run_stage_sense_check,
)
from ..validation.core import (
    _enrich_report_or_error,
    _require_organize_stage_for_enrich,
    _steps_missing_issue_refs,
    _steps_with_bad_paths,
    _steps_with_vague_detail,
    _steps_without_effort,
    _underspecified_steps,
)
from .records import (
    record_enrich_stage,
    record_sense_check_stage,
    resolve_reusable_report,
)


def _cmd_stage_observe(
    args: argparse.Namespace,
    *,
    services: TriageServices | None = None,
) -> None:
    _cmd_stage_observe_impl(
        args,
        services=services,
        has_triage_in_queue_fn=has_triage_in_queue,
        inject_triage_stages_fn=inject_triage_stages,
    )


def _cmd_stage_enrich(
    args: argparse.Namespace,
    *,
    services: TriageServices | None = None,
) -> None:
    run_stage_enrich(
        args,
        services=services,
        deps=EnrichStageDeps(
            has_triage_in_queue=has_triage_in_queue,
            require_organize_stage_for_enrich=_require_organize_stage_for_enrich,
            underspecified_steps=_underspecified_steps,
            steps_with_bad_paths=_steps_with_bad_paths,
            steps_without_effort=_steps_without_effort,
            enrich_report_or_error=_enrich_report_or_error,
            resolve_reusable_report=resolve_reusable_report,
            record_enrich_stage=record_enrich_stage,
            colorize=colorize,
            print_user_message=print_user_message,
            print_cascade_clear_feedback=print_cascade_clear_feedback,
        ),
    )


def _cmd_stage_sense_check(
    args: argparse.Namespace,
    *,
    services: TriageServices | None = None,
) -> None:
    run_stage_sense_check(
        args,
        services=services,
        deps=SenseCheckStageDeps(
            has_triage_in_queue=has_triage_in_queue,
            resolve_reusable_report=resolve_reusable_report,
            record_sense_check_stage=record_sense_check_stage,
            colorize=colorize,
            print_cascade_clear_feedback=print_cascade_clear_feedback,
            underspecified_steps=_underspecified_steps,
            steps_missing_issue_refs=_steps_missing_issue_refs,
            steps_with_bad_paths=_steps_with_bad_paths,
            steps_with_vague_detail=_steps_with_vague_detail,
            steps_without_effort=_steps_without_effort,
        ),
    )


def cmd_stage_enrich(
    args: argparse.Namespace,
    *,
    services: TriageServices | None = None,
) -> None:
    _cmd_stage_enrich(args, services=services)


def cmd_stage_sense_check(
    args: argparse.Namespace,
    *,
    services: TriageServices | None = None,
) -> None:
    _cmd_stage_sense_check(args, services=services)


def cmd_stage_observe(
    args: argparse.Namespace,
    *,
    services: TriageServices | None = None,
) -> None:
    _cmd_stage_observe(args, services=services)


__all__ = [
    "cmd_stage_enrich",
    "cmd_stage_observe",
    "cmd_stage_organize",
    "cmd_stage_reflect",
    "cmd_stage_sense_check",
    "_cmd_stage_enrich",
    "_cmd_stage_observe",
    "_cmd_stage_organize",
    "_cmd_stage_reflect",
    "_cmd_stage_sense_check",
]
