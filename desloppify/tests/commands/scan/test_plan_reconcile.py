"""Direct tests for scan plan reconciliation orchestration.

Tests exercise the real reconciliation logic with realistic plan and state
data structures, mocking only at I/O boundaries (load_plan, save_plan).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import desloppify.app.commands.scan.plan_reconcile as reconcile_mod
from desloppify.engine._plan.schema import empty_plan
from desloppify.engine._plan.stale_dimensions import (
    StaleDimensionSyncResult,
    UnscoredDimensionSyncResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _runtime(*, state=None, config=None) -> SimpleNamespace:
    return SimpleNamespace(
        state=state or {},
        state_path=Path("/tmp/fake-state.json"),
        config=config or {},
    )


def _make_state(
    *,
    issues: dict | None = None,
    overall_score: float | None = None,
    objective_score: float | None = None,
    strict_score: float | None = None,
    verified_strict_score: float | None = None,
    scan_count: int = 1,
) -> dict:
    """Build a minimal but realistic state dict."""
    state: dict = {
        "issues": issues or {},
        "scan_count": scan_count,
        "dimension_scores": {},
        "subjective_assessments": {},
    }
    if overall_score is not None:
        state["overall_score"] = overall_score
    if objective_score is not None:
        state["objective_score"] = objective_score
    if strict_score is not None:
        state["strict_score"] = strict_score
    if verified_strict_score is not None:
        state["verified_strict_score"] = verified_strict_score
    return state


def _make_issue(
    detector: str = "complexity",
    file: str = "src/app.py",
    status: str = "open",
    **extra,
) -> dict:
    return {"detector": detector, "file": file, "status": status, **extra}


# ---------------------------------------------------------------------------
# Tests: _plan_has_user_content
# ---------------------------------------------------------------------------

class TestPlanHasUserContent:

    def test_empty_plan_has_no_user_content(self):
        plan = empty_plan()
        assert reconcile_mod._plan_has_user_content(plan) is False

    def test_plan_with_queue_order(self):
        plan = empty_plan()
        plan["queue_order"] = ["issue-1"]
        assert reconcile_mod._plan_has_user_content(plan) is True

    def test_plan_with_overrides(self):
        plan = empty_plan()
        plan["overrides"] = {"issue-1": {"issue_id": "issue-1"}}
        assert reconcile_mod._plan_has_user_content(plan) is True

    def test_plan_with_clusters(self):
        plan = empty_plan()
        plan["clusters"] = {"c1": {"name": "c1", "issue_ids": ["issue-1"]}}
        assert reconcile_mod._plan_has_user_content(plan) is True

    def test_plan_with_skipped(self):
        plan = empty_plan()
        plan["skipped"] = {"issue-1": {
            "issue_id": "issue-1", "kind": "temporary", "skipped_at_scan": 1,
        }}
        assert reconcile_mod._plan_has_user_content(plan) is True

    def test_empty_collections_are_falsy(self):
        """Empty queue_order, overrides, clusters, skipped all return False."""
        plan = empty_plan()
        plan["queue_order"] = []
        plan["overrides"] = {}
        plan["clusters"] = {}
        plan["skipped"] = {}
        assert reconcile_mod._plan_has_user_content(plan) is False


# ---------------------------------------------------------------------------
# Tests: _seed_plan_start_scores
# ---------------------------------------------------------------------------

class TestSeedPlanStartScores:

    def test_seeds_when_plan_start_scores_empty(self):
        plan = empty_plan()
        state = _make_state(
            strict_score=85.0, overall_score=90.0,
            objective_score=88.0, verified_strict_score=80.0,
        )
        assert reconcile_mod._seed_plan_start_scores(plan, state) is True
        assert plan["plan_start_scores"] == {
            "strict": 85.0, "overall": 90.0,
            "objective": 88.0, "verified": 80.0,
        }

    def test_does_not_reseed_when_scores_exist(self):
        plan = empty_plan()
        plan["plan_start_scores"] = {
            "strict": 70.0, "overall": 75.0,
            "objective": 72.0, "verified": 68.0,
        }
        state = _make_state(
            strict_score=85.0, overall_score=90.0,
            objective_score=88.0, verified_strict_score=80.0,
        )
        assert reconcile_mod._seed_plan_start_scores(plan, state) is False
        assert plan["plan_start_scores"]["strict"] == 70.0

    def test_reseeds_when_reset_sentinel(self):
        plan = empty_plan()
        plan["plan_start_scores"] = {"reset": True}
        state = _make_state(
            strict_score=85.0, overall_score=90.0,
            objective_score=88.0, verified_strict_score=80.0,
        )
        assert reconcile_mod._seed_plan_start_scores(plan, state) is True
        assert plan["plan_start_scores"]["strict"] == 85.0
        assert "reset" not in plan["plan_start_scores"]

    def test_returns_false_when_strict_score_is_none(self):
        plan = empty_plan()
        state = _make_state()
        assert reconcile_mod._seed_plan_start_scores(plan, state) is False
        # plan_start_scores stays empty
        assert plan["plan_start_scores"] == {}

    def test_returns_false_when_existing_is_non_dict(self):
        """Edge case: plan_start_scores set to a non-dict value."""
        plan = empty_plan()
        plan["plan_start_scores"] = "garbage"
        state = _make_state(strict_score=85.0, overall_score=90.0,
                            objective_score=88.0, verified_strict_score=80.0)
        assert reconcile_mod._seed_plan_start_scores(plan, state) is False


# ---------------------------------------------------------------------------
# Tests: _apply_plan_reconciliation
# ---------------------------------------------------------------------------

class TestApplyPlanReconciliation:

    def test_supersedes_resolved_issue(self):
        """An issue in queue_order that becomes resolved should be superseded."""
        plan = empty_plan()
        plan["queue_order"] = ["issue-1", "issue-2"]
        plan["overrides"] = {"issue-1": {"issue_id": "issue-1"}}
        state = _make_state(issues={
            "issue-1": _make_issue(status="resolved"),
            "issue-2": _make_issue(status="open"),
        })
        from desloppify.engine._plan.reconcile import reconcile_plan_after_scan
        result = reconcile_plan_after_scan(plan, state)
        assert "issue-1" in result.superseded
        assert "issue-1" in plan["superseded"]
        assert "issue-1" not in plan["queue_order"]
        assert "issue-2" in plan["queue_order"]

    def test_supersedes_disappeared_issue(self):
        """An issue in queue_order that no longer exists should be superseded."""
        plan = empty_plan()
        plan["queue_order"] = ["gone-id"]
        plan["overrides"] = {"gone-id": {"issue_id": "gone-id"}}
        state = _make_state(issues={})
        from desloppify.engine._plan.reconcile import reconcile_plan_after_scan
        result = reconcile_plan_after_scan(plan, state)
        assert "gone-id" in result.superseded

    def test_no_changes_when_all_alive(self):
        plan = empty_plan()
        plan["queue_order"] = ["issue-1"]
        plan["overrides"] = {"issue-1": {"issue_id": "issue-1"}}
        state = _make_state(issues={
            "issue-1": _make_issue(status="open"),
        })
        changed = reconcile_mod._apply_plan_reconciliation(
            plan, state, reconcile_mod.reconcile_plan_after_scan,
        )
        assert changed is False

    def test_skips_when_no_user_content(self):
        plan = empty_plan()
        state = _make_state()
        changed = reconcile_mod._apply_plan_reconciliation(
            plan, state, reconcile_mod.reconcile_plan_after_scan,
        )
        assert changed is False


# ---------------------------------------------------------------------------
# Tests: _sync_unscored_dimensions (via helper)
# ---------------------------------------------------------------------------

class TestSyncUnscoredDimensions:

    def test_injects_unscored_ids(self):
        plan = empty_plan()
        plan["queue_order"] = ["issue-1"]

        def mock_sync(p, s):
            result = UnscoredDimensionSyncResult()
            result.injected = ["subjective::naming"]
            p["queue_order"].insert(0, "subjective::naming")
            return result

        changed = reconcile_mod._sync_unscored_dimensions(plan, {}, mock_sync)
        assert changed is True
        assert plan["queue_order"][0] == "subjective::naming"

    def test_no_change_when_nothing_unscored(self):
        plan = empty_plan()
        plan["queue_order"] = ["issue-1"]
        changed = reconcile_mod._sync_unscored_dimensions(
            plan, {}, lambda p, s: UnscoredDimensionSyncResult(),
        )
        assert changed is False

    def test_prints_message_on_injection(self, capsys):
        plan = empty_plan()

        def mock_sync(p, s):
            result = UnscoredDimensionSyncResult()
            result.injected = ["subjective::naming", "subjective::docs"]
            return result

        reconcile_mod._sync_unscored_dimensions(plan, {}, mock_sync)
        captured = capsys.readouterr()
        assert "2 unscored" in captured.out


# ---------------------------------------------------------------------------
# Tests: _sync_stale_dimensions (via helper)
# ---------------------------------------------------------------------------

class TestSyncStaleDimensions:

    def test_injects_stale_ids(self):
        plan = empty_plan()
        plan["queue_order"] = ["issue-1"]

        def mock_sync(p, s):
            result = StaleDimensionSyncResult()
            result.injected = ["subjective::naming"]
            p["queue_order"].append("subjective::naming")
            return result

        changed = reconcile_mod._sync_stale_dimensions(plan, {}, mock_sync)
        assert changed is True
        assert "subjective::naming" in plan["queue_order"]

    def test_reports_pruned(self, capsys):
        plan = empty_plan()

        def mock_sync(p, s):
            result = StaleDimensionSyncResult()
            result.pruned = ["subjective::naming"]
            return result

        changed = reconcile_mod._sync_stale_dimensions(plan, {}, mock_sync)
        assert changed is True
        captured = capsys.readouterr()
        assert "refreshed" in captured.out.lower() or "removed" in captured.out.lower()

    def test_reports_injected(self, capsys):
        plan = empty_plan()

        def mock_sync(p, s):
            result = StaleDimensionSyncResult()
            result.injected = ["subjective::naming"]
            return result

        reconcile_mod._sync_stale_dimensions(plan, {}, mock_sync)
        captured = capsys.readouterr()
        assert "1 subjective" in captured.out

    def test_no_change_when_nothing_stale(self):
        plan = empty_plan()
        changed = reconcile_mod._sync_stale_dimensions(
            plan, {}, lambda p, s: StaleDimensionSyncResult(),
        )
        assert changed is False


# ---------------------------------------------------------------------------
# Tests: _sync_plan_start_scores_and_log
# ---------------------------------------------------------------------------

class TestSyncPlanStartScoresAndLog:

    def test_seeds_and_appends_log(self):
        plan = empty_plan()
        state = _make_state(
            strict_score=85.0, overall_score=90.0,
            objective_score=88.0, verified_strict_score=80.0,
        )
        changed = reconcile_mod._sync_plan_start_scores_and_log(plan, state)
        assert changed is True
        assert plan["plan_start_scores"]["strict"] == 85.0
        log_actions = [e["action"] for e in plan["execution_log"]]
        assert "seed_start_scores" in log_actions

    def test_no_change_when_already_seeded(self, monkeypatch):
        plan = empty_plan()
        plan["plan_start_scores"] = {
            "strict": 70.0, "overall": 75.0,
            "objective": 72.0, "verified": 68.0,
        }
        state = _make_state(
            strict_score=85.0, overall_score=90.0,
            objective_score=88.0, verified_strict_score=80.0,
        )
        # Stub out _clear to isolate seeding logic
        monkeypatch.setattr(
            reconcile_mod, "_clear_plan_start_scores_if_queue_empty",
            lambda state, plan: False,
        )
        changed = reconcile_mod._sync_plan_start_scores_and_log(plan, state)
        assert changed is False
        assert plan["execution_log"] == []

    def test_clears_when_queue_empty(self, monkeypatch):
        plan = empty_plan()
        plan["plan_start_scores"] = {
            "strict": 70.0, "overall": 75.0,
            "objective": 72.0, "verified": 68.0,
        }
        state = _make_state()  # no scores so seeding fails

        # Mock the queue breakdown to report empty
        monkeypatch.setattr(
            "desloppify.app.commands.helpers.queue_progress.plan_aware_queue_breakdown",
            lambda s, p: SimpleNamespace(objective_actionable=0),
        )
        changed = reconcile_mod._sync_plan_start_scores_and_log(plan, state)
        assert changed is True
        assert plan["plan_start_scores"] == {}
        assert state["_plan_start_scores_for_reveal"]["strict"] == 70.0
        log_actions = [e["action"] for e in plan["execution_log"]]
        assert "clear_start_scores" in log_actions


# ---------------------------------------------------------------------------
# Tests: _clear_plan_start_scores_if_queue_empty
# ---------------------------------------------------------------------------

class TestClearPlanStartScoresIfQueueEmpty:

    def test_returns_false_when_no_start_scores(self):
        plan = empty_plan()
        state = _make_state()
        assert reconcile_mod._clear_plan_start_scores_if_queue_empty(state, plan) is False

    def test_clears_and_copies_to_state(self, monkeypatch):
        plan = empty_plan()
        plan["plan_start_scores"] = {
            "strict": 80.0, "overall": 85.0,
            "objective": 82.0, "verified": 78.0,
        }
        state = _make_state()

        monkeypatch.setattr(
            "desloppify.app.commands.helpers.queue_progress.plan_aware_queue_breakdown",
            lambda s, p: SimpleNamespace(objective_actionable=0),
        )
        result = reconcile_mod._clear_plan_start_scores_if_queue_empty(state, plan)
        assert result is True
        assert plan["plan_start_scores"] == {}
        assert state["_plan_start_scores_for_reveal"]["strict"] == 80.0

    def test_does_not_clear_when_queue_has_items(self, monkeypatch):
        plan = empty_plan()
        plan["plan_start_scores"] = {
            "strict": 80.0, "overall": 85.0,
            "objective": 82.0, "verified": 78.0,
        }
        state = _make_state()

        monkeypatch.setattr(
            "desloppify.app.commands.helpers.queue_progress.plan_aware_queue_breakdown",
            lambda s, p: SimpleNamespace(objective_actionable=3),
        )
        result = reconcile_mod._clear_plan_start_scores_if_queue_empty(state, plan)
        assert result is False
        assert plan["plan_start_scores"]["strict"] == 80.0

    def test_clears_when_only_subjective_items_remain(self, monkeypatch):
        """Plan-start scores clear when only subjective items remain (objective_actionable=0)."""
        plan = empty_plan()
        plan["plan_start_scores"] = {
            "strict": 80.0, "overall": 85.0,
            "objective": 82.0, "verified": 78.0,
        }
        state = _make_state()

        monkeypatch.setattr(
            "desloppify.app.commands.helpers.queue_progress.plan_aware_queue_breakdown",
            lambda s, p: SimpleNamespace(objective_actionable=0),
        )
        result = reconcile_mod._clear_plan_start_scores_if_queue_empty(state, plan)
        assert result is True
        assert plan["plan_start_scores"] == {}
        assert state["_plan_start_scores_for_reveal"]["strict"] == 80.0

    def test_swallows_queue_breakdown_exception(self, monkeypatch):
        plan = empty_plan()
        plan["plan_start_scores"] = {"strict": 80.0}
        state = _make_state()

        def _raise(s, p):
            raise OSError("disk read failed")

        monkeypatch.setattr(
            "desloppify.app.commands.helpers.queue_progress.plan_aware_queue_breakdown",
            _raise,
        )
        result = reconcile_mod._clear_plan_start_scores_if_queue_empty(state, plan)
        assert result is False
        # Scores not cleared on error
        assert plan["plan_start_scores"]["strict"] == 80.0


# ---------------------------------------------------------------------------
# Tests: reconcile_plan_post_scan (full orchestration)
# ---------------------------------------------------------------------------

class TestReconcilePlanPostScan:

    def test_saves_when_superseded_issues_detected(self, monkeypatch):
        plan = empty_plan()
        plan["queue_order"] = ["issue-1", "issue-2"]
        plan["overrides"] = {"issue-1": {"issue_id": "issue-1"}}
        state = _make_state(issues={
            "issue-1": _make_issue(status="resolved"),
            "issue-2": _make_issue(status="open"),
        })

        saved: list[dict] = []
        monkeypatch.setattr(reconcile_mod, "load_plan", lambda _path=None: plan)
        monkeypatch.setattr(reconcile_mod, "save_plan", lambda p, _path=None: saved.append(p))

        reconcile_mod.reconcile_plan_post_scan(_runtime(state=state))

        assert len(saved) == 1
        assert "issue-1" in saved[0]["superseded"]
        assert "issue-1" not in saved[0]["queue_order"]
        assert "issue-2" in saved[0]["queue_order"]

    def test_does_not_save_when_nothing_changed(self, monkeypatch):
        """Plan with no actionable changes should not trigger a save.

        Pre-populate communicate-score so sync does not re-inject it.
        """
        plan = empty_plan()
        plan["queue_order"] = ["workflow::communicate-score"]
        state = _make_state()

        saved: list[dict] = []
        monkeypatch.setattr(reconcile_mod, "load_plan", lambda _path=None: plan)
        monkeypatch.setattr(reconcile_mod, "save_plan", lambda p, _path=None: saved.append(p))

        reconcile_mod.reconcile_plan_post_scan(_runtime(state=state))
        assert saved == []

    def test_swallows_load_plan_exception(self, monkeypatch):
        monkeypatch.setattr(
            reconcile_mod, "load_plan",
            lambda _path=None: (_ for _ in ()).throw(OSError("boom")),
        )
        # Should not raise
        reconcile_mod.reconcile_plan_post_scan(_runtime())

    def test_swallows_save_plan_exception(self, monkeypatch):
        plan = empty_plan()
        plan["queue_order"] = ["issue-1"]
        plan["overrides"] = {"issue-1": {"issue_id": "issue-1"}}
        state = _make_state(issues={
            "issue-1": _make_issue(status="resolved"),
        })

        monkeypatch.setattr(reconcile_mod, "load_plan", lambda _path=None: plan)
        monkeypatch.setattr(reconcile_mod, "save_plan",
                            lambda p, _path=None: (_ for _ in ()).throw(OSError("disk full")))

        # Should not raise
        reconcile_mod.reconcile_plan_post_scan(_runtime(state=state))

    def test_seeds_start_scores_on_empty_plan(self, monkeypatch):
        plan = empty_plan()
        state = _make_state(
            strict_score=85.0, overall_score=90.0,
            objective_score=88.0, verified_strict_score=80.0,
        )

        saved: list[dict] = []
        monkeypatch.setattr(reconcile_mod, "load_plan", lambda _path=None: plan)
        monkeypatch.setattr(reconcile_mod, "save_plan", lambda p, _path=None: saved.append(p))

        reconcile_mod.reconcile_plan_post_scan(_runtime(state=state))

        assert len(saved) == 1
        assert saved[0]["plan_start_scores"]["strict"] == 85.0

    def test_superseded_issue_removed_from_clusters(self, monkeypatch):
        plan = empty_plan()
        plan["queue_order"] = ["issue-1", "issue-2"]
        plan["clusters"] = {
            "my-cluster": {
                "name": "my-cluster",
                "issue_ids": ["issue-1", "issue-2"],
            }
        }
        state = _make_state(issues={
            "issue-1": _make_issue(status="resolved"),
            "issue-2": _make_issue(status="open"),
        })

        saved: list[dict] = []
        monkeypatch.setattr(reconcile_mod, "load_plan", lambda _path=None: plan)
        monkeypatch.setattr(reconcile_mod, "save_plan", lambda p, _path=None: saved.append(p))

        reconcile_mod.reconcile_plan_post_scan(_runtime(state=state))

        assert len(saved) == 1
        cluster = saved[0]["clusters"]["my-cluster"]
        assert "issue-1" not in cluster["issue_ids"]
        assert "issue-2" in cluster["issue_ids"]

    def test_superseded_issue_removed_from_skipped(self, monkeypatch):
        plan = empty_plan()
        plan["queue_order"] = []
        plan["skipped"] = {
            "issue-1": {
                "issue_id": "issue-1", "kind": "temporary",
                "skipped_at_scan": 1, "review_after": 5,
            },
        }
        state = _make_state(issues={
            "issue-1": _make_issue(status="resolved"),
        })

        saved: list[dict] = []
        monkeypatch.setattr(reconcile_mod, "load_plan", lambda _path=None: plan)
        monkeypatch.setattr(reconcile_mod, "save_plan", lambda p, _path=None: saved.append(p))

        reconcile_mod.reconcile_plan_post_scan(_runtime(state=state))

        assert len(saved) == 1
        assert "issue-1" not in saved[0]["skipped"]
        assert "issue-1" in saved[0]["superseded"]

    def test_multiple_dirty_steps_save_once(self, monkeypatch):
        """Even when multiple reconciliation steps produce changes, save happens once."""
        plan = empty_plan()
        plan["queue_order"] = ["issue-1"]
        plan["overrides"] = {"issue-1": {"issue_id": "issue-1"}}
        state = _make_state(
            issues={"issue-1": _make_issue(status="resolved")},
            strict_score=85.0, overall_score=90.0,
            objective_score=88.0, verified_strict_score=80.0,
        )

        saved: list[dict] = []
        monkeypatch.setattr(reconcile_mod, "load_plan", lambda _path=None: plan)
        monkeypatch.setattr(reconcile_mod, "save_plan", lambda p, _path=None: saved.append(p))

        reconcile_mod.reconcile_plan_post_scan(_runtime(state=state))

        assert len(saved) == 1
        assert "issue-1" in saved[0]["superseded"]
        assert saved[0]["plan_start_scores"]["strict"] == 85.0

    def test_plan_path_derived_from_state_path(self, monkeypatch):
        plan = empty_plan()
        state = _make_state()

        loaded_paths: list = []
        saved_paths: list = []

        def mock_load(path=None):
            loaded_paths.append(path)
            return plan

        def mock_save(p, path=None):
            saved_paths.append(path)

        monkeypatch.setattr(reconcile_mod, "load_plan", mock_load)
        monkeypatch.setattr(reconcile_mod, "save_plan", mock_save)

        rt = SimpleNamespace(
            state=state,
            state_path=Path("/project/.desloppify/state-python.json"),
            config={},
        )
        reconcile_mod.reconcile_plan_post_scan(rt)

        assert loaded_paths[0] == Path("/project/.desloppify/plan.json")

    def test_plan_path_none_when_state_path_none(self, monkeypatch):
        plan = empty_plan()
        state = _make_state()

        loaded_paths: list = []

        def mock_load(path=None):
            loaded_paths.append(path)
            return plan

        monkeypatch.setattr(reconcile_mod, "load_plan", mock_load)
        monkeypatch.setattr(reconcile_mod, "save_plan", lambda p, _path=None: None)

        rt = SimpleNamespace(state=state, state_path=None, config={})
        reconcile_mod.reconcile_plan_post_scan(rt)
        assert loaded_paths[0] is None

    def test_execution_log_records_reconcile(self, monkeypatch):
        plan = empty_plan()
        plan["queue_order"] = ["issue-1"]
        plan["overrides"] = {"issue-1": {"issue_id": "issue-1"}}
        state = _make_state(issues={
            "issue-1": _make_issue(status="resolved"),
        })

        saved: list[dict] = []
        monkeypatch.setattr(reconcile_mod, "load_plan", lambda _path=None: plan)
        monkeypatch.setattr(reconcile_mod, "save_plan", lambda p, _path=None: saved.append(p))

        reconcile_mod.reconcile_plan_post_scan(_runtime(state=state))

        assert len(saved) == 1
        actions = [e["action"] for e in saved[0].get("execution_log", [])]
        assert "reconcile" in actions

    def test_multiple_issues_superseded_at_once(self, monkeypatch):
        """When several queued issues disappear, all are superseded."""
        plan = empty_plan()
        plan["queue_order"] = ["a", "b", "c"]
        plan["overrides"] = {
            "a": {"issue_id": "a"},
            "b": {"issue_id": "b"},
            "c": {"issue_id": "c"},
        }
        state = _make_state(issues={
            "a": _make_issue(status="resolved"),
            "b": _make_issue(status="resolved"),
            "c": _make_issue(status="open"),
        })

        saved: list[dict] = []
        monkeypatch.setattr(reconcile_mod, "load_plan", lambda _path=None: plan)
        monkeypatch.setattr(reconcile_mod, "save_plan", lambda p, _path=None: saved.append(p))

        reconcile_mod.reconcile_plan_post_scan(_runtime(state=state))

        assert len(saved) == 1
        assert "a" in saved[0]["superseded"]
        assert "b" in saved[0]["superseded"]
        assert "a" not in saved[0]["queue_order"]
        assert "b" not in saved[0]["queue_order"]
        assert "c" in saved[0]["queue_order"]
