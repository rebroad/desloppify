"""Direct integration tests for scan workflow runtime + merge paths."""

from __future__ import annotations

from types import SimpleNamespace

from desloppify import state as state_mod
from desloppify.app.commands.helpers.runtime import CommandRuntime
from desloppify.app.commands.scan.workflow import (
    ScanRuntime,
    merge_scan_results,
    prepare_scan_runtime,
)
from desloppify.base.discovery.file_paths import rel
from desloppify.engine.plan_state import empty_plan, load_plan, save_plan


def test_prepare_scan_runtime_uses_real_runtime_and_resets_subjective(tmp_path):
    state = {
        "subjective_assessments": {
            "naming_quality": {
                "score": 97.0,
                "source": "manual_override",
                "provisional_override": True,
                "provisional_until_scan": 2,
            }
        }
    }
    config = {
        "zone_overrides": {"src/foo.py": "test"},
    }
    runtime = CommandRuntime(
        config=config,
        state=state,
        state_path=tmp_path / "state.json",
    )
    args = SimpleNamespace(
        path=str(tmp_path),
        runtime=runtime,
        lang=None,
        reset_subjective=True,
        skip_slow=False,
        profile=None,
    )

    scan_runtime = prepare_scan_runtime(args)

    assert scan_runtime.state_path == tmp_path / "state.json"
    assert scan_runtime.path == tmp_path
    assert scan_runtime.profile == "full"
    assert scan_runtime.effective_include_slow is True
    assert scan_runtime.zone_overrides == {"src/foo.py": "test"}
    assert scan_runtime.reset_subjective_count >= 10
    naming = scan_runtime.state["subjective_assessments"]["naming_quality"]
    assert naming["score"] == 0.0
    assert naming["source"] == "scan_reset_subjective"
    assert naming["reset_by"] == "scan_reset_subjective"


def test_merge_scan_results_persists_state_and_reconciles_plan(tmp_path):
    state_path = tmp_path / "state.json"
    plan_path = tmp_path / "plan.json"
    stale_id = "structural::src/legacy.py::legacy_large_file"

    plan = empty_plan()
    plan["queue_order"] = [stale_id]
    save_plan(plan, plan_path)

    state = state_mod.empty_state()
    state["scan_path"] = rel(str(tmp_path))
    state["strict_score"] = 82.5
    state["overall_score"] = 84.0
    state["objective_score"] = 86.0
    state["verified_strict_score"] = 82.5

    runtime = ScanRuntime(
        args=SimpleNamespace(force_resolve=False),
        state_path=state_path,
        state=state,
        path=tmp_path,
        config={
            "ignore": [],
            "needs_rescan": False,
            "holistic_max_age_days": 30,
        },
        lang=None,
        lang_label="",
        profile="full",
        effective_include_slow=True,
        zone_overrides=None,
    )

    issues = [
        state_mod.make_issue(
            "structural",
            "src/new_module.py",
            "new_large_file",
            tier=2,
            confidence="high",
            summary="Large module should be split",
            detail={"loc": 260},
        )
    ]

    merge = merge_scan_results(
        runtime,
        issues,
        potentials={"structural": 1},
        codebase_metrics={"total_files": 1},
    )

    assert merge.prev_strict == 82.5
    assert merge.diff.get("new", 0) >= 1

    persisted = state_mod.load_state(state_path)
    assert persisted["scan_path"] == rel(str(tmp_path))
    assert issues[0]["id"] in persisted["issues"]

    plan_after = load_plan(plan_path)
    assert stale_id not in plan_after.get("queue_order", [])
    assert stale_id in plan_after.get("superseded", {})
    plan_start = plan_after.get("plan_start_scores", {})
    assert isinstance(plan_start.get("strict"), float)
