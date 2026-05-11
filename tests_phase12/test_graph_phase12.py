"""End-to-end graph flows: every sample scenario + HITL rejection + checkpoint smoke."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.metrics import metric_from_state
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.scenarios import load_scenarios
from langgraph_agent_lab.state import Route, Scenario, initial_state

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_SCENARIOS = REPO_ROOT / "data" / "sample" / "scenarios.jsonl"


def _invoke(scenario: Scenario, *, checkpointer_kind: str = "memory", database_url: str | None = None):
    cp = build_checkpointer(checkpointer_kind, database_url)
    graph = build_graph(checkpointer=cp)
    state = initial_state(scenario)
    cfg = {"configurable": {"thread_id": state["thread_id"]}}
    return graph, graph.invoke(state, config=cfg)


def test_all_sample_scenarios_match_expected_route_and_metric_success() -> None:
    scenarios = load_scenarios(str(SAMPLE_SCENARIOS))
    assert len(scenarios) >= 7
    for scenario in scenarios:
        _, final = _invoke(scenario)
        m = metric_from_state(final, scenario.expected_route.value, scenario.requires_approval)
        assert m.success, (
            f"{scenario.id}: route={final.get('route')} approval={final.get('approval')} "
            f"answer={final.get('final_answer')!r} pending={final.get('pending_question')!r}"
        )
        assert final.get("route") == scenario.expected_route.value


def test_error_scenario_s05_eventually_succeeds_after_retries() -> None:
    scenario = next(s for s in load_scenarios(str(SAMPLE_SCENARIOS)) if s.id == "S05_error")
    _, final = _invoke(scenario)
    assert final.get("route") == Route.ERROR.value
    assert final.get("final_answer")
    nodes = [e.get("node") for e in final.get("events", [])]
    assert nodes.count("retry") >= 1


def test_dead_letter_s07_max_attempts_one() -> None:
    scenario = next(s for s in load_scenarios(str(SAMPLE_SCENARIOS)) if s.id == "S07_dead_letter")
    _, final = _invoke(scenario)
    assert "dead_letter" in [e.get("node") for e in final.get("events", [])]
    assert final.get("final_answer")
    assert "manual review" in (final.get("final_answer") or "").lower()


def test_risky_paths_record_approval_when_required() -> None:
    for sid in ("S04_risky", "S06_delete"):
        scenario = next(s for s in load_scenarios(str(SAMPLE_SCENARIOS)) if s.id == sid)
        _, final = _invoke(scenario)
        assert final.get("approval") is not None
        nodes = [e.get("node") for e in final.get("events", [])]
        assert "approval" in nodes


def test_hitl_rejection_routes_to_clarify() -> None:
    def fake_approval(_state):
        return {
            "approval": {"approved": False, "reviewer": "test", "comment": "denied"},
            "events": [{"node": "approval", "event_type": "completed", "message": "n", "metadata": {}}],
        }

    with patch("langgraph_agent_lab.graph.approval_node", side_effect=fake_approval):
        scenario = Scenario(
            id="reject_hitl",
            query="Refund all customers immediately",
            expected_route=Route.RISKY,
            requires_approval=True,
        )
        _, final = _invoke(scenario)
        assert final.get("pending_question") or final.get("final_answer")
        assert any(e.get("node") == "clarify" for e in final.get("events", []))


@pytest.mark.skipif(not SAMPLE_SCENARIOS.exists(), reason="sample scenarios missing")
def test_metrics_json_schema_roundtrip_after_run(tmp_path: Path) -> None:
    """Mirrors CLI run-scenarios metric aggregation without invoking Typer."""
    from langgraph_agent_lab.metrics import MetricsReport, summarize_metrics, write_metrics

    scenarios = load_scenarios(str(SAMPLE_SCENARIOS))
    items = []
    for scenario in scenarios:
        _, final = _invoke(scenario)
        items.append(metric_from_state(final, scenario.expected_route.value, scenario.requires_approval))
    report = summarize_metrics(items)
    out = tmp_path / "metrics.json"
    write_metrics(report, out)
    loaded = MetricsReport.model_validate(json.loads(out.read_text(encoding="utf-8")))
    assert loaded.total_scenarios == len(scenarios)
    assert loaded.success_rate == 1.0
