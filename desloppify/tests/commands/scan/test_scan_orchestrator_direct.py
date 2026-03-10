"""Direct behavior tests for scan orchestrator forwarding."""

from __future__ import annotations

from types import SimpleNamespace

from desloppify.app.commands.scan.orchestrator import ScanOrchestrator
from desloppify.app.commands.scan.workflow import ScanMergeResult, ScanNoiseSnapshot


def test_scan_orchestrator_forwards_runtime_and_payloads() -> None:
    runtime = SimpleNamespace(state={"issues": {}}, config={"issue_noise_budget": 10})
    calls: dict[str, object] = {}

    def _generate(rt):
        calls["generate"] = rt
        return ([{"id": "a"}], {"potential": 1}, {"loc": 10})

    def _merge(rt, issues, potentials, metrics):
        calls["merge"] = (rt, issues, potentials, metrics)
        return ScanMergeResult(
            diff={"open_delta": 1},
            prev_overall=80.0,
            prev_objective=95.0,
            prev_strict=75.0,
            prev_verified=70.0,
            prev_dim_scores={},
        )

    def _noise_snapshot(state, config):
        calls["noise"] = (state, config)
        return ScanNoiseSnapshot(
            noise_budget=10,
            global_noise_budget=0,
            budget_warning=None,
            hidden_by_detector={"smells": 1},
            hidden_total=1,
        )

    def _persist(rt, narrative):
        calls["persist"] = (rt, narrative)

    orchestrator = ScanOrchestrator(
        runtime=runtime,
        run_scan_generation_fn=_generate,
        merge_scan_results_fn=_merge,
        resolve_noise_snapshot_fn=_noise_snapshot,
        persist_reminder_history_fn=_persist,
    )

    issues, potentials, metrics = orchestrator.generate()
    assert issues == [{"id": "a"}]
    assert potentials == {"potential": 1}
    assert metrics == {"loc": 10}
    assert calls["generate"] is runtime

    merge_result = orchestrator.merge(issues, potentials, metrics)
    assert merge_result.diff == {"open_delta": 1}
    assert calls["merge"] == (runtime, issues, potentials, metrics)

    noise_snapshot = orchestrator.noise_snapshot()
    assert noise_snapshot.hidden_total == 1
    assert calls["noise"] == (runtime.state, runtime.config)

    reminder_payload = {"messages": ["re-run stale review dimensions"]}
    orchestrator.persist_reminders(reminder_payload)
    assert calls["persist"] == (runtime, reminder_payload)
