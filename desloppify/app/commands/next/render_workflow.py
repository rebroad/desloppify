"""Workflow item rendering helpers for next terminal output."""

from __future__ import annotations

from desloppify.engine.plan_triage import (
    triage_manual_stage_command,
    triage_run_stages_command,
)


def step_text(step: str | dict) -> str:
    if isinstance(step, dict):
        return step.get("title", str(step))
    return str(step)


def _print_runner_commands(detail: dict, *, colorize_fn) -> None:
    runner_commands = detail.get("runner_commands", []) if isinstance(detail, dict) else []
    if isinstance(runner_commands, list) and runner_commands:
        print(colorize_fn("  Runners:", "dim"))
        for idx, runner_entry in enumerate(runner_commands, 1):
            if not isinstance(runner_entry, dict):
                continue
            label = str(runner_entry.get("label", "")).strip()
            command = str(runner_entry.get("command", "")).strip()
            if label and command:
                print(colorize_fn(f"  {idx}. {label}: {command}", "dim"))

    manual_fallback = detail.get("manual_fallback", "") if isinstance(detail, dict) else ""
    if manual_fallback:
        print(colorize_fn(f"  Manual fallback: {manual_fallback}", "dim"))


def render_workflow_stage(item: dict, *, colorize_fn, workflow_stage_name_fn) -> None:
    """Render a triage workflow stage item."""
    blocked = item.get("is_blocked", False)
    detail = item.get("detail", {})
    stage = workflow_stage_name_fn(item)
    tag = " [blocked]" if blocked else ""
    style = "dim" if blocked else "bold"
    print(colorize_fn(f"  (Planning stage: {stage}{tag})", style))
    print(colorize_fn("  " + "─" * 60, "dim"))
    print(f"  {colorize_fn(item.get('summary', ''), 'yellow')}")
    total = detail.get("total_review_issues", 0)
    if total:
        print(colorize_fn(f"  {total} review issues to analyze", "dim"))
    if blocked:
        blocked_by = item.get("blocked_by", [])
        deps = ", ".join(dep.replace("triage::", "") for dep in blocked_by)
        print(colorize_fn(f"  Blocked by: {deps}", "dim"))
        first_dep = blocked_by[0] if blocked_by else ""
        dep_name = first_dep.replace("triage::", "")
        if dep_name:
            print(
                colorize_fn(
                    f"  Next step: {triage_run_stages_command(only_stages=dep_name)}",
                    "dim",
                )
            )
            print(
                colorize_fn(
                    f"  Alt runner: {triage_run_stages_command(runner='claude', only_stages=dep_name)}",
                    "dim",
                )
            )
            print(
                colorize_fn(
                    f"  Manual fallback: {triage_manual_stage_command(dep_name)}",
                    "dim",
                )
            )
    else:
        print(colorize_fn(f"\n  Action: {item.get('primary_command', '')}", "cyan"))
        _print_runner_commands(detail, colorize_fn=colorize_fn)


def render_workflow_action(item: dict, *, colorize_fn) -> None:
    print(colorize_fn("  (Workflow step)", "bold"))
    print(colorize_fn("  " + "─" * 60, "dim"))
    print(f"  {colorize_fn(item.get('summary', ''), 'yellow')}")
    detail = item.get("detail", {})
    planning_tools = detail.get("planning_tools", []) if isinstance(detail, dict) else []
    if isinstance(planning_tools, list) and planning_tools:
        print(colorize_fn("\n  Planning tools:", "dim"))
        for idx, tool in enumerate(planning_tools, 1):
            if not isinstance(tool, dict):
                continue
            label = str(tool.get("label", "")).strip()
            command = str(tool.get("command", "")).strip()
            if label and command:
                print(colorize_fn(f"  {idx}. {label}: {command}", "dim"))
            elif command:
                print(colorize_fn(f"  {idx}. {command}", "dim"))
            elif label:
                print(colorize_fn(f"  {idx}. {label}", "dim"))

    options = detail.get("decision_options", []) if isinstance(detail, dict) else []
    if isinstance(options, list) and options:
        print(colorize_fn("\n  Decision options:", "dim"))
        for idx, option in enumerate(options, 1):
            if not isinstance(option, dict):
                continue
            label = str(option.get("label", "")).strip()
            command = str(option.get("command", "")).strip()
            if label and command:
                print(colorize_fn(f"  {idx}. {label}: {command}", "dim"))
            elif command:
                print(colorize_fn(f"  {idx}. {command}", "dim"))
            elif label:
                print(colorize_fn(f"  {idx}. {label}", "dim"))
    print(colorize_fn(f"\n  Action: {item.get('primary_command', '')}", "cyan"))


__all__ = ["render_workflow_action", "render_workflow_stage", "step_text"]
