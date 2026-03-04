"""Plan item section rendering helpers."""

from __future__ import annotations

from collections import defaultdict

from desloppify.base.config import DEFAULT_TARGET_STRICT_SCORE
from desloppify.engine._work_queue.core import QueueBuildOptions, build_work_queue
from desloppify.engine.planning.types import PlanState


def plan_item_sections(issues: dict, *, state: PlanState | None = None) -> list[str]:
    """Build per-file sections from the shared work-queue backend."""
    queue_state: PlanState | dict = state or {"issues": issues}
    raw_target = (
        (state or {}).get("config", {}).get(
            "target_strict_score", DEFAULT_TARGET_STRICT_SCORE
        )
        if isinstance(state, dict)
        else DEFAULT_TARGET_STRICT_SCORE
    )
    try:
        subjective_threshold = float(raw_target)
    except (TypeError, ValueError):
        subjective_threshold = DEFAULT_TARGET_STRICT_SCORE
    subjective_threshold = max(0.0, min(100.0, subjective_threshold))
    if "issues" not in queue_state:
        queue_state = {**queue_state, "issues": issues}

    queue = build_work_queue(
        queue_state,
        options=QueueBuildOptions(
            count=None,
            status="open",
            include_subjective=True,
            subjective_threshold=subjective_threshold,
        ),
    )
    open_items = queue.get("items", [])
    by_file: dict[str, list] = defaultdict(list)
    for item in open_items:
        by_file[item.get("file", ".")].append(item)

    lines: list[str] = []
    total_count = len(open_items)
    if not open_items:
        return lines

    lines.extend(
        [
            "---",
            f"## Open Items ({total_count})",
            "",
        ]
    )

    sorted_files = sorted(by_file.items(), key=lambda item: (-len(item[1]), item[0]))
    for filepath, file_items in sorted_files:
        display_path = "Codebase-wide" if filepath == "." else filepath
        lines.append(f"### `{display_path}` ({len(file_items)} issues)")
        lines.append("")
        for item in file_items:
            if item.get("kind") == "subjective_dimension":
                lines.append(f"- [ ] [subjective] {item.get('summary', '')}")
                lines.append(f"      `{item.get('id', '')}`")
                if item.get("primary_command"):
                    lines.append(f"      action: `{item['primary_command']}`")
                continue

            conf_badge = f"[{item.get('confidence', 'medium')}]"
            lines.append(f"- [ ] {conf_badge} {item.get('summary', '')}")
            lines.append(f"      `{item.get('id', '')}`")
        lines.append("")

    return lines


__all__ = ["plan_item_sections"]
