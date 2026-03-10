"""Project policy — persistent project-specific rules for triage and review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from desloppify.base.discovery.file_paths import safe_write_text
from desloppify.base.discovery.paths import get_project_root
from desloppify.engine._state.schema import utc_now


def _default_policy_path() -> Path:
    return get_project_root() / ".desloppify" / "project_policy.json"


def load_policy(path: Path | None = None) -> dict[str, Any]:
    p = path or _default_policy_path()
    if not p.exists():
        return {"rules": []}
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {"rules": []}
    if not isinstance(data, dict):
        return {"rules": []}
    data.setdefault("rules", [])
    return data


def save_policy(policy: dict[str, Any], path: Path | None = None) -> None:
    p = path or _default_policy_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    safe_write_text(p, json.dumps(policy, indent=2) + "\n")


def add_rule(policy: dict[str, Any], text: str) -> int:
    """Add a rule, return its 1-based index."""
    rules = policy.setdefault("rules", [])
    rules.append({"text": text, "created_at": utc_now()})
    return len(rules)


def remove_rule(policy: dict[str, Any], index: int) -> str | None:
    """Remove a rule by 1-based index, return its text or None."""
    rules = policy.get("rules", [])
    if 1 <= index <= len(rules):
        return rules.pop(index - 1)["text"]
    return None


def render_policy_block(policy: dict[str, Any]) -> str:
    """Render rules as a prompt section. Returns empty string if no rules."""
    rules = policy.get("rules", [])
    if not rules:
        return ""
    lines = [
        "## Project Policy\n",
        "The following project-specific rules MUST be respected.",
        "Do NOT suggest or implement changes that violate these rules.",
        "Flag any action step or suggestion that would violate them.\n",
    ]
    for i, rule in enumerate(rules, 1):
        lines.append(f"{i}. {rule['text']}")
    return "\n".join(lines) + "\n"


__all__ = [
    "add_rule",
    "load_policy",
    "remove_rule",
    "render_policy_block",
    "save_policy",
]
