"""Post-import plan sync for review importing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from desloppify import state as state_mod
from desloppify.app.commands.helpers.display import short_issue_id
from desloppify.base.exception_sets import PLAN_LOAD_EXCEPTIONS
from desloppify.base.output.terminal import colorize
from desloppify.engine.plan import (
    TRIAGE_CMD_RUN_STAGES_CLAUDE,
    TRIAGE_CMD_RUN_STAGES_CODEX,
)

if TYPE_CHECKING:
    from desloppify.engine.plan import ReviewImportSyncResult


def _print_review_import_sync(
    state: dict,
    result: ReviewImportSyncResult,
    *,
    workflow_injected: bool,
) -> None:
    """Print summary of plan changes after review import sync."""
    new_ids = result.new_ids
    print(colorize(
        f"\n  Plan updated: {len(new_ids)} new review issue(s) added to queue.",
        "bold",
    ))
    issues = state.get("issues", {})
    for finding_id in sorted(new_ids)[:10]:
        finding = issues.get(finding_id, {})
        print(f"    * [{short_issue_id(finding_id)}] {finding.get('summary', '')}")
    if len(new_ids) > 10:
        print(colorize(f"    ... and {len(new_ids) - 10} more", "dim"))
    print()
    print(colorize(
        "  Review issues were added to the queue. Workflow follow-up may be front-loaded.",
        "dim",
    ))
    print()
    print(colorize("  View queue:            desloppify plan queue", "dim"))
    print(colorize("  View newest first:     desloppify plan queue --sort recent", "dim"))
    print()
    print(colorize("  NEXT STEP:", "yellow"))
    print(colorize("    Run:    desloppify next", "yellow"))
    if result.triage_injected and not workflow_injected:
        print(colorize(f"    Codex:  {TRIAGE_CMD_RUN_STAGES_CODEX}", "dim"))
        print(colorize(f"    Claude: {TRIAGE_CMD_RUN_STAGES_CLAUDE}", "dim"))
        print(colorize("    Manual dashboard: desloppify plan triage", "dim"))
    print(colorize(
        "  (Follow the queue in order; score communication and planning come before triage.)",
        "dim",
    ))


def sync_plan_after_import(state: dict, diff: dict, assessment_mode: str) -> None:
    """Apply issue/workflow syncs after import in one load/save cycle."""
    try:
        from desloppify.engine.plan import (
            ScoreSnapshot,
            append_log_entry,
            current_unscored_ids,
            has_living_plan,
            load_plan,
            purge_ids,
            save_plan,
            sync_communicate_score_needed,
            sync_create_plan_needed,
            sync_import_scores_needed,
            sync_plan_after_review_import,
        )

        if not has_living_plan():
            return

        plan = load_plan()
        dirty = False
        workflow_injected_ids: list[str] = []

        snapshot = state_mod.score_snapshot(state)
        current_scores = ScoreSnapshot(
            strict=snapshot.strict,
            overall=snapshot.overall,
            objective=snapshot.objective,
            verified=snapshot.verified,
        )
        trusted_score_import = assessment_mode in {"trusted_internal", "attested_external"}

        communicate_result = sync_communicate_score_needed(
            plan,
            state,
            scores_just_imported=trusted_score_import,
            current_scores=current_scores,
        )
        if communicate_result.changes:
            dirty = True
            workflow_injected_ids.append("workflow::communicate-score")

        has_new_issues = (
            int(diff.get("new", 0) or 0) > 0
            or int(diff.get("reopened", 0) or 0) > 0
        )
        import_result = None
        covered_ids: list[str] = []

        injected_parts: list[str] = []
        if communicate_result.changes:
            injected_parts.append("`workflow::communicate-score`")

        import_scores_result = sync_import_scores_needed(
            plan,
            state,
            assessment_mode=assessment_mode,
        )
        if import_scores_result.changes:
            dirty = True
            workflow_injected_ids.append("workflow::import-scores")
            injected_parts.append("`workflow::import-scores`")

        create_plan_result = sync_create_plan_needed(plan, state)
        if create_plan_result.changes:
            dirty = True
            workflow_injected_ids.append("workflow::create-plan")
            injected_parts.append("`workflow::create-plan`")

        if has_new_issues:
            import_result = sync_plan_after_review_import(plan, state)
            if import_result is not None:
                dirty = True

            still_unscored = current_unscored_ids(state)
            order = plan.get("queue_order", [])
            covered_ids = [
                finding_id for finding_id in order
                if finding_id.startswith("subjective::") and finding_id not in still_unscored
            ]
            if covered_ids:
                purge_ids(plan, covered_ids)
                dirty = True

        if dirty:
            if communicate_result.changes:
                append_log_entry(
                    plan,
                    "sync_communicate_score",
                    actor="system",
                    detail={"trigger": "review_import", "injected": True},
                )
            if import_scores_result.changes:
                append_log_entry(
                    plan,
                    "sync_import_scores",
                    actor="system",
                    detail={"trigger": "review_import", "injected": True},
                )
            if create_plan_result.changes:
                append_log_entry(
                    plan,
                    "sync_create_plan",
                    actor="system",
                    detail={"trigger": "review_import", "injected": True},
                )
            if import_result is not None or workflow_injected_ids or covered_ids:
                append_log_entry(
                    plan,
                    "review_import_sync",
                    actor="system",
                    detail={
                        "trigger": "review_import",
                        "new_ids": sorted(import_result.new_ids) if import_result is not None else [],
                        "added_to_queue": (
                            import_result.added_to_queue if import_result is not None else []
                        ),
                        "workflow_injected_ids": workflow_injected_ids,
                        "triage_injected": (
                            import_result.triage_injected if import_result is not None else False
                        ),
                        "triage_injected_ids": (
                            import_result.triage_injected_ids if import_result is not None else []
                        ),
                        "triage_deferred": (
                            import_result.triage_deferred if import_result is not None else False
                        ),
                        "diff_new": diff.get("new", 0),
                        "diff_reopened": diff.get("reopened", 0),
                        "covered_subjective": covered_ids,
                    },
                )
            save_plan(plan)

        if import_result is not None:
            _print_review_import_sync(
                state,
                import_result,
                workflow_injected=bool(workflow_injected_ids),
            )
        if injected_parts:
            print(colorize(
                f"  Plan: {' and '.join(injected_parts)} queued. Run `desloppify next`.",
                "cyan",
            ))
    except PLAN_LOAD_EXCEPTIONS as exc:
        print(
            colorize(
                f"  Note: skipped plan sync after review import ({exc}).",
                "dim",
            )
        )


__all__ = ["sync_plan_after_import"]
