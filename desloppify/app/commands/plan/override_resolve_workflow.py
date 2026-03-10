"""Workflow-item resolution logic for `plan resolve`."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Literal

from desloppify import state as state_mod
from desloppify.app.commands.helpers.state import state_path
from desloppify.app.commands.plan.override_resolve_helpers import blocked_triage_stages
from desloppify.app.commands.plan.triage.helpers import (
    has_triage_in_queue,
    inject_triage_stages,
)
from desloppify.base.output.terminal import colorize
from desloppify.engine.plan_state import (
    load_plan,
    save_plan,
)
from desloppify.engine.plan_ops import (
    append_log_entry,
    auto_complete_steps,
    purge_ids,
)
from desloppify.engine.plan_queue import (
    WORKFLOW_CREATE_PLAN_ID,
    WORKFLOW_SCORE_CHECKPOINT_ID,
    confirmed_triage_stage_names,
)
from desloppify.engine.plan_triage import (
    triage_manual_stage_command,
    triage_runner_commands,
)

WORKFLOW_GATE_IDS = frozenset({WORKFLOW_SCORE_CHECKPOINT_ID, WORKFLOW_CREATE_PLAN_ID})


@dataclass(frozen=True)
class WorkflowResolveOutcome:
    status: Literal["handled", "blocked", "fall_through"]
    remaining_patterns: list[str]


@dataclass(frozen=True)
class StageCoaching:
    headline: str
    details: tuple[str, ...] = ()
    commands: tuple[str, ...] = ()
    footer: tuple[str, ...] = ()


STAGE_COACHING = {
    "observe": StageCoaching(
        headline="  You must analyze the findings before resolving this.",
        details=("  Start by examining themes, root causes, and contradictions:",),
        footer=("  The report must be 100+ chars describing what you found.",),
    ),
    "reflect": StageCoaching(
        headline="  Observe is done. Now compare against previously completed work:",
        footer=("  The report must mention recurring dimensions if any exist.",),
    ),
    "organize": StageCoaching(
        headline="  Reflect is done. Now create clusters and prioritize:",
        commands=(
            '    desloppify plan cluster create <name> --description "..."',
            "    desloppify plan cluster add <name> <issue-patterns>",
            '    desloppify plan cluster update <name> --steps "step1" "step2"',
            "    {organize_manual_command}",
        ),
        footer=("  All manual clusters must have descriptions and action_steps.",),
    ),
    "enrich": StageCoaching(
        headline="  Organize is done. Now enrich steps with detail and issue refs:",
        commands=(
            '    desloppify plan cluster update <name> --update-step N --detail "sub-details"',
        ),
    ),
    "commit": StageCoaching(
        headline="  Enrich is done. Finalize the execution plan:",
    ),
}


def _print_stage_runner_guidance(next_stage: str) -> None:
    print(colorize("  Preferred runners:", "yellow"))
    runner_commands = (
        triage_runner_commands()
        if next_stage == "commit"
        else triage_runner_commands(only_stages=next_stage)
    )
    for label, command in runner_commands:
        print(colorize(f"    {label}: {command}", "dim"))


def _print_stage_coaching(next_stage: str) -> None:
    coaching = STAGE_COACHING.get(next_stage)
    if coaching is None:
        return

    print(colorize(coaching.headline, "yellow"))
    for line in coaching.details:
        print(colorize(line, "dim"))
    for command in coaching.commands:
        resolved = command.format(
            organize_manual_command=triage_manual_stage_command("organize")
        )
        print(colorize(resolved, "dim"))
    if coaching.footer:
        print()
        for line in coaching.footer:
            print(colorize(line, "dim"))


def resolve_workflow_patterns(
    args: argparse.Namespace,
    *,
    synthetic_ids: list[str],
    real_patterns: list[str],
    note: str | None,
) -> WorkflowResolveOutcome:
    """Resolve synthetic workflow IDs and return whether normal resolution should continue."""
    if not synthetic_ids:
        return WorkflowResolveOutcome(status="fall_through", remaining_patterns=real_patterns)

    plan = load_plan()

    blocked_map = blocked_triage_stages(plan)
    for synthetic_id in synthetic_ids:
        if synthetic_id not in blocked_map:
            continue
        blocked_text = ", ".join(dep.replace("triage::", "") for dep in blocked_map[synthetic_id])
        print(
            colorize(
                f"  Cannot resolve {synthetic_id} — blocked by: {blocked_text}",
                "red",
            )
        )
        print(
            colorize(
                "  Complete those stages first, or use --force-resolve to override.",
                "dim",
            )
        )
        if not getattr(args, "force_resolve", False):
            return WorkflowResolveOutcome(status="blocked", remaining_patterns=[])

    gated_ids = [synthetic_id for synthetic_id in synthetic_ids if synthetic_id in WORKFLOW_GATE_IDS]
    if gated_ids:
        force = getattr(args, "force_resolve", False)
        meta = plan.get("epic_triage_meta", {})
        triage_ever_completed = bool(meta.get("last_completed_at"))
        if triage_ever_completed:
            missing: set[str] = set()
        else:
            confirmed_stages = confirmed_triage_stage_names(meta)
            required_stages = {"observe", "reflect", "organize", "enrich", "commit"}
            missing = required_stages - confirmed_stages

        if missing and not force:
            if not has_triage_in_queue(plan):
                inject_triage_stages(plan)
                meta.setdefault("triage_stages", {})
                plan["epic_triage_meta"] = meta
                save_plan(plan)

            stage_order = ["observe", "reflect", "organize", "enrich", "commit"]
            next_stage = next((stage for stage in stage_order if stage in missing), "observe")

            for workflow_id in gated_ids:
                print(colorize(f"  Cannot resolve {workflow_id} — triage not complete.", "red"))
            print()

            _print_stage_runner_guidance(next_stage)
            print(
                colorize(
                    f"  Manual fallback: {triage_manual_stage_command(next_stage)}",
                    "dim",
                )
            )
            print()

            _print_stage_coaching(next_stage)

            print()
            print(colorize(f"  Remaining stages: {', '.join(sorted(missing))}", "dim"))
            print(
                colorize(
                    "  To skip triage: --force-resolve --note 'reason for skipping triage'",
                    "dim",
                )
            )

            append_log_entry(
                plan,
                "workflow_blocked",
                issue_ids=gated_ids,
                actor="user",
                note=note,
                detail={"missing_stages": sorted(missing), "next_stage": next_stage},
            )
            save_plan(plan)
            return WorkflowResolveOutcome(status="blocked", remaining_patterns=[])

        if missing and force:
            if not note or len(note.strip()) < 50:
                print(
                    colorize(
                        "  --force-resolve still requires --note (min 50 chars) explaining "
                        "why you're skipping triage.",
                        "red",
                    )
                )
                return WorkflowResolveOutcome(status="blocked", remaining_patterns=[])
            print(colorize("  WARNING: Skipping triage requirement — this is logged.", "yellow"))
            append_log_entry(
                plan,
                "workflow_force_skip",
                issue_ids=gated_ids,
                actor="user",
                note=note,
                detail={"forced": True, "missing_stages": sorted(missing)},
            )
            save_plan(plan)

    if gated_ids:
        scan_count_at_start = plan.get("scan_count_at_plan_start")
        force = getattr(args, "force_resolve", False)
        if scan_count_at_start is not None:
            resolved_state_path = state_path(args)
            state_data = state_mod.load_state(resolved_state_path)
            current_scan_count = int(state_data.get("scan_count", 0) or 0)
            scan_ran = current_scan_count > scan_count_at_start
            scan_skipped = plan.get("scan_gate_skipped", False)

            if not scan_ran and not scan_skipped and not force:
                for workflow_id in gated_ids:
                    print(
                        colorize(
                            f"  Cannot resolve {workflow_id} — no scan has run this cycle.",
                            "red",
                        )
                    )
                print()
                print(
                    colorize(
                        "  You must run a scan before resolving workflow items:",
                        "yellow",
                    )
                )
                print(colorize("    desloppify scan", "dim"))
                print()
                print(
                    colorize(
                        f"  Scans at cycle start: {scan_count_at_start}  "
                        f"Current: {current_scan_count}",
                        "dim",
                    )
                )
                print(
                    colorize(
                        "  To skip scan requirement: desloppify plan scan-gate --skip "
                        '--note "reason for skipping scan"',
                        "dim",
                    )
                )
                print(
                    colorize(
                        "  Or use: --force-resolve --note 'reason for skipping'",
                        "dim",
                    )
                )

                append_log_entry(
                    plan,
                    "scan_gate_blocked",
                    issue_ids=gated_ids,
                    actor="user",
                    note=note,
                    detail={
                        "scan_count_at_start": scan_count_at_start,
                        "current_scan_count": current_scan_count,
                    },
                )
                save_plan(plan)
                return WorkflowResolveOutcome(status="blocked", remaining_patterns=[])

    purge_ids(plan, synthetic_ids)
    step_messages = auto_complete_steps(plan)
    for message in step_messages:
        print(colorize(message, "green"))
    append_log_entry(plan, "done", issue_ids=synthetic_ids, actor="user", note=note)
    save_plan(plan)
    for synthetic_id in synthetic_ids:
        print(colorize(f"  Resolved: {synthetic_id}", "green"))

    if not real_patterns:
        return WorkflowResolveOutcome(status="handled", remaining_patterns=[])
    return WorkflowResolveOutcome(status="fall_through", remaining_patterns=real_patterns)


__all__ = ["WorkflowResolveOutcome", "resolve_workflow_patterns"]
