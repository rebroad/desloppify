"""Tests for reflect dashboard rendering helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from desloppify.app.commands.plan.triage.reflect_dashboard import (
    _print_completed_clusters,
    _print_recurring_patterns,
    _print_reflect_dashboard,
    _print_resolved_issues,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cluster(
    name: str = "naming-cleanup",
    issue_ids: list[str] | None = None,
    thesis: str = "",
    action_steps: list[str] | None = None,
) -> dict:
    c: dict = {"name": name, "issue_ids": issue_ids or []}
    if thesis:
        c["thesis"] = thesis
    if action_steps is not None:
        c["action_steps"] = action_steps
    return c


def _make_issue(
    status: str = "resolved",
    summary: str = "Bad name",
    dimension: str = "naming",
) -> dict:
    return {
        "status": status,
        "summary": summary,
        "detail": {"dimension": dimension},
    }


# ---------------------------------------------------------------------------
# _print_completed_clusters
# ---------------------------------------------------------------------------


class TestPrintCompletedClusters:
    def test_empty_list_prints_nothing(self, capsys):
        _print_completed_clusters([])
        assert capsys.readouterr().out == ""

    def test_single_cluster_name_and_count(self, capsys):
        cluster = _make_cluster(name="type-safety", issue_ids=["a", "b", "c"])
        _print_completed_clusters([cluster])
        out = capsys.readouterr().out
        assert "type-safety" in out
        assert "3 issues" in out

    def test_thesis_printed(self, capsys):
        cluster = _make_cluster(thesis="Fix all naming smells")
        _print_completed_clusters([cluster])
        out = capsys.readouterr().out
        assert "Fix all naming smells" in out

    def test_no_thesis_key_still_works(self, capsys):
        cluster = {"name": "x", "issue_ids": []}
        _print_completed_clusters([cluster])
        out = capsys.readouterr().out
        assert "x" in out

    def test_action_steps_shown(self, capsys):
        cluster = _make_cluster(action_steps=["step one", "step two"])
        _print_completed_clusters([cluster])
        out = capsys.readouterr().out
        assert "step one" in out
        assert "step two" in out

    def test_action_steps_capped_at_three(self, capsys):
        steps = ["s1", "s2", "s3", "s4"]
        cluster = _make_cluster(action_steps=steps)
        _print_completed_clusters([cluster])
        out = capsys.readouterr().out
        assert "s3" in out
        assert "s4" not in out

    def test_more_than_ten_clusters_shows_overflow(self, capsys):
        clusters = [_make_cluster(name=f"c-{i}") for i in range(13)]
        _print_completed_clusters(clusters)
        out = capsys.readouterr().out
        # First 10 shown
        assert "c-9" in out
        # 11th not shown by name
        assert "c-10" not in out
        # Overflow message
        assert "3 more" in out

    def test_exactly_ten_clusters_no_overflow(self, capsys):
        clusters = [_make_cluster(name=f"c-{i}") for i in range(10)]
        _print_completed_clusters(clusters)
        out = capsys.readouterr().out
        assert "more" not in out

    def test_missing_name_falls_back_to_question_mark(self, capsys):
        _print_completed_clusters([{"issue_ids": ["x"]}])
        out = capsys.readouterr().out
        assert "?" in out
        assert "1 issues" in out


# ---------------------------------------------------------------------------
# _print_resolved_issues
# ---------------------------------------------------------------------------


class TestPrintResolvedIssues:
    def test_empty_dict_prints_nothing(self, capsys):
        _print_resolved_issues({})
        assert capsys.readouterr().out == ""

    def test_single_issue_shown(self, capsys):
        issues = {"f-1": _make_issue(status="resolved", summary="Bad var name", dimension="naming")}
        _print_resolved_issues(issues)
        out = capsys.readouterr().out
        assert "1" in out  # count
        assert "[resolved]" in out
        assert "[naming]" in out
        assert "Bad var name" in out
        assert "f-1" in out

    def test_sorted_order(self, capsys):
        issues = {
            "z-issue": _make_issue(summary="Z"),
            "a-issue": _make_issue(summary="A"),
        }
        _print_resolved_issues(issues)
        out = capsys.readouterr().out
        pos_a = out.index("a-issue")
        pos_z = out.index("z-issue")
        assert pos_a < pos_z

    def test_overflow_after_ten(self, capsys):
        issues = {f"f-{i:02d}": _make_issue(summary=f"Issue {i}") for i in range(12)}
        _print_resolved_issues(issues)
        out = capsys.readouterr().out
        assert "2 more" in out

    def test_non_dict_detail_falls_back(self, capsys):
        issue = {"status": "resolved", "summary": "X", "detail": "not-a-dict"}
        _print_resolved_issues({"id-1": issue})
        out = capsys.readouterr().out
        # dimension should be empty string, but line still prints
        assert "[resolved]" in out
        assert "X" in out

    def test_missing_detail_key(self, capsys):
        issue = {"status": "fixed", "summary": "No detail"}
        _print_resolved_issues({"id-1": issue})
        out = capsys.readouterr().out
        assert "[fixed]" in out
        assert "No detail" in out


# ---------------------------------------------------------------------------
# _print_recurring_patterns
# ---------------------------------------------------------------------------


class TestPrintRecurringPatterns:
    def test_no_recurring_returns_false(self, capsys):
        result = _print_recurring_patterns({}, {})
        assert result is False
        assert capsys.readouterr().out == ""

    def test_recurring_dimension_shown(self, capsys):
        open_issues = {
            "o-1": _make_issue(status="open", dimension="naming"),
        }
        resolved = {
            "r-1": _make_issue(status="resolved", dimension="naming"),
        }
        result = _print_recurring_patterns(open_issues, resolved)
        assert result is True
        out = capsys.readouterr().out
        assert "naming" in out
        assert "1 resolved" in out
        assert "1 still open" in out

    def test_potential_loop_label_when_open_gte_resolved(self, capsys):
        open_issues = {
            "o-1": _make_issue(status="open", dimension="naming"),
            "o-2": _make_issue(status="open", dimension="naming"),
        }
        resolved = {
            "r-1": _make_issue(status="resolved", dimension="naming"),
        }
        _print_recurring_patterns(open_issues, resolved)
        out = capsys.readouterr().out
        assert "potential loop" in out

    def test_root_cause_label_when_open_lt_resolved(self, capsys):
        open_issues = {
            "o-1": _make_issue(status="open", dimension="naming"),
        }
        resolved = {
            "r-1": _make_issue(status="resolved", dimension="naming"),
            "r-2": _make_issue(status="resolved", dimension="naming"),
        }
        _print_recurring_patterns(open_issues, resolved)
        out = capsys.readouterr().out
        assert "root cause unaddressed" in out

    def test_disjoint_dimensions_not_recurring(self, capsys):
        open_issues = {"o-1": _make_issue(status="open", dimension="naming")}
        resolved = {"r-1": _make_issue(status="resolved", dimension="error-handling")}
        result = _print_recurring_patterns(open_issues, resolved)
        assert result is False


# ---------------------------------------------------------------------------
# _print_reflect_dashboard (orchestrator)
# ---------------------------------------------------------------------------


class TestPrintReflectDashboard:
    def test_first_triage_message_when_all_empty(self, capsys):
        si = SimpleNamespace(completed_clusters=[], resolved_issues={}, open_issues={})
        _print_reflect_dashboard(si, {})
        out = capsys.readouterr().out
        assert "First triage" in out
        assert "strategy" in out

    def test_no_first_triage_message_when_completed_present(self, capsys):
        si = SimpleNamespace(
            completed_clusters=[_make_cluster()],
            resolved_issues={},
            open_issues={},
        )
        _print_reflect_dashboard(si, {})
        out = capsys.readouterr().out
        assert "First triage" not in out

    def test_no_first_triage_message_when_resolved_present(self, capsys):
        si = SimpleNamespace(
            completed_clusters=[],
            resolved_issues={"f-1": _make_issue()},
            open_issues={},
        )
        _print_reflect_dashboard(si, {})
        out = capsys.readouterr().out
        assert "First triage" not in out

    def test_missing_attrs_default_gracefully(self, capsys):
        """si with no attributes at all should not crash."""
        si = SimpleNamespace()
        _print_reflect_dashboard(si, {})
        out = capsys.readouterr().out
        assert "First triage" in out

    def test_recurring_suppresses_first_triage(self, capsys):
        """When recurring patterns exist, the first-triage block is skipped."""
        si = SimpleNamespace(
            completed_clusters=[],
            resolved_issues={"r-1": _make_issue(dimension="naming")},
            open_issues={"o-1": _make_issue(status="open", dimension="naming")},
        )
        _print_reflect_dashboard(si, {})
        out = capsys.readouterr().out
        assert "Recurring patterns" in out
        assert "First triage" not in out
