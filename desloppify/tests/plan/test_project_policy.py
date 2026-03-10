"""Tests for project policy storage and prompt rendering."""

from __future__ import annotations

from pathlib import Path

from desloppify.engine._plan.policy.project import (
    add_rule,
    load_policy,
    remove_rule,
    render_policy_block,
    save_policy,
)


def test_load_policy_missing_file(tmp_path: Path) -> None:
    policy = load_policy(tmp_path / "nonexistent.json")
    assert policy == {"rules": []}


def test_add_save_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "policy.json"
    policy = load_policy(path)
    idx = add_rule(policy, "No re-export facades")
    assert idx == 1
    idx2 = add_rule(policy, "No backward-compat aliases")
    assert idx2 == 2
    save_policy(policy, path)

    loaded = load_policy(path)
    assert len(loaded["rules"]) == 2
    assert loaded["rules"][0]["text"] == "No re-export facades"
    assert loaded["rules"][1]["text"] == "No backward-compat aliases"
    assert "created_at" in loaded["rules"][0]


def test_remove_rule(tmp_path: Path) -> None:
    path = tmp_path / "policy.json"
    policy = {"rules": [
        {"text": "Rule A", "created_at": "2026-01-01"},
        {"text": "Rule B", "created_at": "2026-01-02"},
    ]}
    save_policy(policy, path)

    loaded = load_policy(path)
    removed = remove_rule(loaded, 1)
    assert removed == "Rule A"
    assert len(loaded["rules"]) == 1
    assert loaded["rules"][0]["text"] == "Rule B"

    assert remove_rule(loaded, 99) is None


def test_render_policy_block_empty() -> None:
    assert render_policy_block({"rules": []}) == ""
    assert render_policy_block({}) == ""


def test_render_policy_block_with_rules() -> None:
    policy = {"rules": [
        {"text": "No re-export facades"},
        {"text": "No dependency injection explosion"},
    ]}
    block = render_policy_block(policy)
    assert "## Project Policy" in block
    assert "1. No re-export facades" in block
    assert "2. No dependency injection explosion" in block
    assert "MUST be respected" in block


def test_sense_check_prompt_includes_policy() -> None:
    from desloppify.app.commands.plan.triage.runner.stage_prompts_sense import (
        build_sense_check_content_prompt,
    )

    plan = {
        "clusters": {
            "test-cluster": {
                "issue_ids": ["id1"],
                "action_steps": [{"title": "Fix it", "detail": "Do the fix"}],
            }
        }
    }
    policy_block = "## Project Policy\n\n1. No facades\n"

    prompt_with = build_sense_check_content_prompt(
        cluster_name="test-cluster",
        plan=plan,
        repo_root=Path("/tmp/repo"),
        policy_block=policy_block,
    )
    prompt_without = build_sense_check_content_prompt(
        cluster_name="test-cluster",
        plan=plan,
        repo_root=Path("/tmp/repo"),
    )

    assert "Project Policy" in prompt_with
    assert "No facades" in prompt_with
    assert "Project Policy" not in prompt_without
