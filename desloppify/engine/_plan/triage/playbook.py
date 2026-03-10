"""Canonical shared triage workflow labels and command snippets."""

from __future__ import annotations

TRIAGE_STAGE_LABELS: tuple[tuple[str, str], ...] = (
    ("observe", "Analyse issues & spot contradictions"),
    ("reflect", "Form strategy & present to user"),
    ("organize", "Defer contradictions, cluster, & prioritize"),
    ("enrich", "Make steps executor-ready (detail, refs)"),
    ("sense-check", "Verify accuracy & cross-cluster deps"),
    ("commit", "Write strategy & confirm"),
)

_TRIAGE_STAGE_DEPENDENCY_ITEMS: tuple[tuple[str, set[str]], ...] = (
    ("observe", set()),
    ("reflect", {"observe"}),
    ("organize", {"reflect"}),
    ("enrich", {"organize"}),
    ("sense-check", {"enrich"}),
    ("commit", {"sense-check"}),
)

TRIAGE_STAGE_DEPENDENCIES: dict[str, set[str]] = dict(_TRIAGE_STAGE_DEPENDENCY_ITEMS)
TRIAGE_RUNNERS: tuple[str, str] = ("codex", "claude")

TRIAGE_CMD_OBSERVE = (
    'desloppify plan triage --stage observe --report '
    '"analysis of themes and root causes..."'
)
TRIAGE_CMD_REFLECT = (
    'desloppify plan triage --stage reflect --report '
    '"comparison against completed work..."'
)
TRIAGE_CMD_ORGANIZE = (
    'desloppify plan triage --stage organize --report '
    '"summary of organization and priorities..."'
)
TRIAGE_CMD_ENRICH = (
    'desloppify plan triage --stage enrich --report '
    '"summary of enrichment work done..."'
)
TRIAGE_CMD_SENSE_CHECK = (
    'desloppify plan triage --stage sense-check --report '
    '"summary of sense-check findings..."'
)
TRIAGE_CMD_COMPLETE = 'desloppify plan triage --complete --strategy "execution plan..."'
TRIAGE_CMD_COMPLETE_VERBOSE = (
    "desloppify plan triage --complete --strategy "
    '"execution plan with priorities and verification..."'
)
TRIAGE_CMD_CONFIRM_EXISTING = (
    'desloppify plan triage --confirm-existing --note "..." --strategy "..."'
)
TRIAGE_CMD_CLUSTER_CREATE = 'desloppify plan cluster create <name> --description "..."'
TRIAGE_CMD_CLUSTER_ADD = "desloppify plan cluster add <name> <issue-patterns>"
TRIAGE_CMD_CLUSTER_ENRICH = (
    'desloppify plan cluster update <name> --description "..." --steps '
    '"step 1" "step 2"'
)
TRIAGE_CMD_CLUSTER_ENRICH_COMPACT = (
    'desloppify plan cluster update <name> --description "..." --steps '
    '"step1" "step2"'
)
TRIAGE_CMD_CLUSTER_STEPS = (
    'desloppify plan cluster update <name> --steps "step 1" "step 2"'
)
TRIAGE_CMD_RUN_STAGES_CODEX = "desloppify plan triage --run-stages --runner codex"
TRIAGE_CMD_RUN_STAGES_CLAUDE = "desloppify plan triage --run-stages --runner claude"

_RUNNER_STAGE_NAMES = frozenset(
    stage_name for stage_name, _label in TRIAGE_STAGE_LABELS if stage_name != "commit"
)
_MANUAL_STAGE_COMMANDS: dict[str, str] = {
    "observe": TRIAGE_CMD_OBSERVE,
    "reflect": TRIAGE_CMD_REFLECT,
    "organize": TRIAGE_CMD_ORGANIZE,
    "enrich": TRIAGE_CMD_ENRICH,
    "sense-check": TRIAGE_CMD_SENSE_CHECK,
    "commit": TRIAGE_CMD_COMPLETE,
}


def triage_run_stages_command(
    *,
    runner: str = "codex",
    only_stages: str | tuple[str, ...] | list[str] | None = None,
) -> str:
    """Return the canonical staged triage runner command."""
    resolved_runner = str(runner).strip().lower()
    if resolved_runner not in TRIAGE_RUNNERS:
        supported = ", ".join(TRIAGE_RUNNERS)
        raise ValueError(f"Unsupported triage runner: {runner!r}. Valid: {supported}")

    command = f"desloppify plan triage --run-stages --runner {resolved_runner}"
    if only_stages is None:
        return command

    if isinstance(only_stages, str):
        stages = [only_stages]
    else:
        stages = [str(stage).strip().lower() for stage in only_stages if str(stage).strip()]

    invalid = [stage for stage in stages if stage not in _RUNNER_STAGE_NAMES]
    if invalid:
        supported = ", ".join(sorted(_RUNNER_STAGE_NAMES))
        bad = ", ".join(sorted(set(invalid)))
        raise ValueError(f"Unsupported triage stage(s): {bad}. Valid: {supported}")

    return f"{command} --only-stages {','.join(stages)}"


def triage_runner_commands(
    *,
    only_stages: str | tuple[str, ...] | list[str] | None = None,
) -> tuple[tuple[str, str], tuple[str, str]]:
    """Return the preferred staged-runner commands for Codex and Claude."""
    return (
        ("Codex", triage_run_stages_command(runner="codex", only_stages=only_stages)),
        ("Claude", triage_run_stages_command(runner="claude", only_stages=only_stages)),
    )


def triage_manual_stage_command(stage: str) -> str:
    """Return the manual fallback command for a triage stage."""
    resolved_stage = str(stage).strip().lower()
    if resolved_stage not in _MANUAL_STAGE_COMMANDS:
        supported = ", ".join(sorted(_MANUAL_STAGE_COMMANDS))
        raise ValueError(f"Unsupported triage stage: {stage!r}. Valid: {supported}")
    return _MANUAL_STAGE_COMMANDS[resolved_stage]


__all__ = [
    "TRIAGE_STAGE_DEPENDENCIES",
    "TRIAGE_STAGE_LABELS",
    "TRIAGE_CMD_CLUSTER_ADD",
    "TRIAGE_CMD_CLUSTER_CREATE",
    "TRIAGE_CMD_CLUSTER_ENRICH",
    "TRIAGE_CMD_CLUSTER_ENRICH_COMPACT",
    "TRIAGE_CMD_CLUSTER_STEPS",
    "TRIAGE_CMD_COMPLETE",
    "TRIAGE_CMD_SENSE_CHECK",
    "TRIAGE_CMD_COMPLETE_VERBOSE",
    "TRIAGE_CMD_CONFIRM_EXISTING",
    "TRIAGE_CMD_ENRICH",
    "TRIAGE_CMD_OBSERVE",
    "TRIAGE_CMD_ORGANIZE",
    "TRIAGE_CMD_REFLECT",
    "TRIAGE_CMD_RUN_STAGES_CLAUDE",
    "TRIAGE_CMD_RUN_STAGES_CODEX",
    "TRIAGE_RUNNERS",
    "triage_manual_stage_command",
    "triage_run_stages_command",
    "triage_runner_commands",
]
