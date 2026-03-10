"""Enrich and sense-check triage confirmation handlers."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from desloppify.base.output.terminal import colorize
from desloppify.base.output.user_message import print_user_message

from .basic import MIN_ATTESTATION_LEN, validate_attestation
from .shared import (
    StageConfirmationRequest,
    ensure_stage_is_confirmable,
    finalize_stage_confirmation,
)
from ..services import TriageServices, default_triage_services


@dataclass(frozen=True)
class _ConfirmationCheckIssue:
    code: str
    total: int
    rows: list[tuple]


@dataclass(frozen=True)
class _ConfirmationCheckReport:
    failures: list[_ConfirmationCheckIssue]
    warnings: list[_ConfirmationCheckIssue]

    def failure(self, code: str) -> _ConfirmationCheckIssue | None:
        for issue in self.failures:
            if issue.code == code:
                return issue
        return None

    def warning(self, code: str) -> _ConfirmationCheckIssue | None:
        for issue in self.warnings:
            if issue.code == code:
                return issue
        return None


def _collect_enrich_level_confirmation_checks(
    plan: dict,
    *,
    include_stale_issue_ref_warning: bool,
) -> _ConfirmationCheckReport:
    from ..validation.core import (
        _steps_missing_issue_refs,
        _steps_referencing_skipped_issues,
        _steps_with_bad_paths,
        _steps_with_vague_detail,
        _steps_without_effort,
        _underspecified_steps,
    )
    from desloppify.base.discovery.paths import get_project_root

    repo_root = get_project_root()

    failures: list[_ConfirmationCheckIssue] = []
    warnings: list[_ConfirmationCheckIssue] = []

    underspec = _underspecified_steps(plan)
    if underspec:
        failures.append(
            _ConfirmationCheckIssue(
                code="underspecified",
                total=sum(n for _, n, _ in underspec),
                rows=underspec,
            )
        )

    bad_paths = _steps_with_bad_paths(plan, repo_root)
    if bad_paths:
        failures.append(
            _ConfirmationCheckIssue(
                code="bad_paths",
                total=sum(len(paths) for _, _, paths in bad_paths),
                rows=bad_paths,
            )
        )

    missing_effort = _steps_without_effort(plan)
    if missing_effort:
        failures.append(
            _ConfirmationCheckIssue(
                code="missing_effort",
                total=sum(n for _, n, _ in missing_effort),
                rows=missing_effort,
            )
        )

    missing_refs = _steps_missing_issue_refs(plan)
    if missing_refs:
        failures.append(
            _ConfirmationCheckIssue(
                code="missing_issue_refs",
                total=sum(n for _, n, _ in missing_refs),
                rows=missing_refs,
            )
        )

    vague_detail = _steps_with_vague_detail(plan, repo_root)
    if vague_detail:
        failures.append(
            _ConfirmationCheckIssue(
                code="vague_detail",
                total=len(vague_detail),
                rows=vague_detail,
            )
        )

    if include_stale_issue_ref_warning:
        stale_refs = _steps_referencing_skipped_issues(plan)
        if stale_refs:
            warnings.append(
                _ConfirmationCheckIssue(
                    code="stale_issue_refs",
                    total=sum(len(ids) for _, _, ids in stale_refs),
                    rows=stale_refs,
                )
            )

    return _ConfirmationCheckReport(failures=failures, warnings=warnings)


def confirm_enrich(
    args: argparse.Namespace,
    plan: dict,
    stages: dict,
    attestation: str | None,
    *,
    services: TriageServices | None = None,
) -> None:
    """Show enrich summary and record confirmation if attestation is valid."""
    resolved_services = services or default_triage_services()
    if not ensure_stage_is_confirmable(stages, stage="enrich"):
        return

    checks = _collect_enrich_level_confirmation_checks(
        plan,
        include_stale_issue_ref_warning=True,
    )

    print(colorize("  Stage: ENRICH — Make steps executor-ready (detail, refs)", "bold"))
    print(colorize("  " + "─" * 54, "dim"))

    underspec = checks.failure("underspecified")
    if underspec:
        print(colorize(f"  Cannot confirm: {underspec.total} step(s) still lack detail or issue_refs.", "red"))
        for name, bare, total in underspec.rows[:5]:
            print(colorize(f"    {name}: {bare}/{total} steps", "yellow"))
        print()
        print(colorize("  Every step needs --detail (sub-points) or --issue-refs (for auto-completion).", "dim"))
        print(colorize("  Fix:", "dim"))
        print(colorize('    desloppify plan cluster update <name> --update-step N --detail "sub-details"', "dim"))
        return

    print(colorize("  All steps have detail or issue_refs.", "green"))

    bad_paths = checks.failure("bad_paths")
    if bad_paths:
        print(colorize(f"\n  Cannot confirm: {bad_paths.total} file path(s) in step details don't exist on disk.", "red"))
        for name, step_num, paths in bad_paths.rows:
            for path_str in paths:
                print(colorize(f"    {name} step {step_num}: {path_str}", "yellow"))
        print(colorize("  Fix paths with: desloppify plan cluster update <name> --update-step N --detail '...'", "dim"))
        return

    missing_effort = checks.failure("missing_effort")
    if missing_effort:
        print(colorize(f"\n  Cannot confirm: {missing_effort.total} step(s) have no effort tag.", "red"))
        for name, missing, total in missing_effort.rows[:5]:
            print(colorize(f"    {name}: {missing}/{total} steps missing effort", "yellow"))
        print(colorize("  Every step needs --effort (trivial/small/medium/large).", "dim"))
        print(colorize("  Fix: desloppify plan cluster update <name> --update-step N --effort small", "dim"))
        return

    missing_refs = checks.failure("missing_issue_refs")
    if missing_refs:
        print(colorize(f"\n  Cannot confirm: {missing_refs.total} step(s) have no issue_refs.", "red"))
        for name, missing, total in missing_refs.rows[:5]:
            print(colorize(f"    {name}: {missing}/{total} steps missing refs", "yellow"))
        print(colorize("  Every step needs --issue-refs linking it to the review issue(s) it addresses.", "dim"))
        print(colorize("  Fix: desloppify plan cluster update <name> --update-step N --issue-refs <hash1> <hash2>", "dim"))
        return

    vague_detail = checks.failure("vague_detail")
    if vague_detail:
        print(colorize(f"\n  Cannot confirm: {vague_detail.total} step(s) have vague detail (< 80 chars, no file paths).", "red"))
        for name, step_num, title in vague_detail.rows[:5]:
            print(colorize(f"    {name} step {step_num}: {title}", "yellow"))
        print(colorize("  Executor-ready means: someone with zero context knows which file to open and what to change.", "dim"))
        print(colorize("  Add file paths and specific instructions to each step's --detail.", "dim"))
        return

    stale_refs = checks.warning("stale_issue_refs")
    if stale_refs:
        print(colorize(f"\n  Warning: {stale_refs.total} step issue_ref(s) point to skipped/wontfixed issues.", "yellow"))
        for name, step_num, ids in stale_refs.rows[:5]:
            print(colorize(f"    {name} step {step_num}: {', '.join(ids[:3])}", "yellow"))
        print(colorize("  Consider removing stale refs or removing the step if it's no longer needed.", "dim"))

    enrich_clusters = [n for n in plan.get("clusters", {}) if not plan["clusters"][n].get("auto")]

    if not finalize_stage_confirmation(
        plan=plan,
        stages=stages,
        request=StageConfirmationRequest(
            stage="enrich",
            attestation=attestation,
            min_attestation_len=MIN_ATTESTATION_LEN,
            command_hint='desloppify plan triage --confirm enrich --attestation "Steps are executor-ready..."',
            validation_stage="enrich",
            validate_attestation_fn=validate_attestation,
            validation_kwargs={"cluster_names": enrich_clusters},
            log_action="triage_confirm_enrich",
        ),
        services=resolved_services,
    ):
        return
    print_user_message(
        "Hey — enrich is confirmed. Run `desloppify plan triage"
        " --stage sense-check --report \"...\"` to verify step"
        " accuracy and cross-cluster dependencies."
    )


def confirm_sense_check(
    args: argparse.Namespace,
    plan: dict,
    stages: dict,
    attestation: str | None,
    *,
    services: TriageServices | None = None,
) -> None:
    """Show sense-check summary and record confirmation if attestation is valid."""
    resolved_services = services or default_triage_services()
    if not ensure_stage_is_confirmable(stages, stage="sense-check"):
        return

    checks = _collect_enrich_level_confirmation_checks(
        plan,
        include_stale_issue_ref_warning=False,
    )

    print(colorize("  Stage: SENSE-CHECK — Verify accuracy & cross-cluster deps", "bold"))
    print(colorize("  " + "─" * 57, "dim"))

    underspec = checks.failure("underspecified")
    if underspec:
        print(colorize(f"  Cannot confirm: {underspec.total} step(s) still lack detail or issue_refs.", "red"))
        for name, bare, total in underspec.rows[:5]:
            print(colorize(f"    {name}: {bare}/{total} steps", "yellow"))
        return

    bad_paths = checks.failure("bad_paths")
    if bad_paths:
        print(colorize(f"\n  Cannot confirm: {bad_paths.total} file path(s) in step details don't exist on disk.", "red"))
        for name, step_num, paths in bad_paths.rows:
            for path_str in paths:
                print(colorize(f"    {name} step {step_num}: {path_str}", "yellow"))
        return

    missing_effort = checks.failure("missing_effort")
    if missing_effort:
        print(colorize(f"\n  Cannot confirm: {missing_effort.total} step(s) have no effort tag.", "red"))
        return

    missing_refs = checks.failure("missing_issue_refs")
    if missing_refs:
        print(colorize(f"\n  Cannot confirm: {missing_refs.total} step(s) have no issue_refs.", "red"))
        return

    vague_detail = checks.failure("vague_detail")
    if vague_detail:
        print(colorize(f"\n  Cannot confirm: {vague_detail.total} step(s) have vague detail.", "red"))
        return

    print(colorize("  All enrich-level checks pass.", "green"))

    sense_check_clusters = [n for n in plan.get("clusters", {}) if not plan["clusters"][n].get("auto")]

    if not finalize_stage_confirmation(
        plan=plan,
        stages=stages,
        request=StageConfirmationRequest(
            stage="sense-check",
            attestation=attestation,
            min_attestation_len=MIN_ATTESTATION_LEN,
            command_hint='desloppify plan triage --confirm sense-check --attestation "Content and structure verified..."',
            validation_stage="sense-check",
            validate_attestation_fn=validate_attestation,
            validation_kwargs={"cluster_names": sense_check_clusters},
            log_action="triage_confirm_sense_check",
        ),
        services=resolved_services,
    ):
        return
    print_user_message(
        "Hey — sense-check is confirmed. Run `desloppify plan triage"
        " --complete --strategy \"...\"` to finish triage."
    )


__all__ = ["confirm_enrich", "confirm_sense_check"]
