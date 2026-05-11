"""Unit-level node behavior: side effects and append-only list updates."""

from __future__ import annotations

from langgraph_agent_lab.nodes import (
    answer_node,
    evaluate_node,
    finalize_node,
    intake_node,
    retry_or_fallback_node,
    tool_node,
)
from langgraph_agent_lab.state import Route, make_event


def test_intake_strips_and_appends_message() -> None:
    out = intake_node({"query": "  hello world  "})
    assert out["query"] == "hello world"
    assert out["messages"] and "intake:" in out["messages"][0]
    assert out["events"]


def test_tool_node_error_route_transient_then_success() -> None:
    base = {
        "route": Route.ERROR.value,
        "scenario_id": "x",
        "should_retry": True,
        "max_attempts": 3,
    }
    r0 = tool_node({**base, "attempt": 0})
    assert "ERROR" in r0["tool_results"][-1]
    r1 = tool_node({**base, "attempt": 1})
    assert "ERROR" in r1["tool_results"][-1]
    r2 = tool_node({**base, "attempt": 2})
    assert "mock-tool-result" in r2["tool_results"][-1]


def test_tool_node_error_dead_letter_cap_always_transient() -> None:
    base = {
        "route": Route.ERROR.value,
        "scenario_id": "S07",
        "should_retry": True,
        "max_attempts": 1,
    }
    assert "ERROR" in tool_node({**base, "attempt": 0})["tool_results"][-1]


def test_tool_node_error_without_should_retry_no_transient() -> None:
    out = tool_node(
        {
            "route": Route.ERROR.value,
            "attempt": 0,
            "scenario_id": "x",
            "should_retry": False,
            "max_attempts": 3,
        }
    )
    assert "mock-tool-result" in out["tool_results"][-1]


def test_evaluate_node_retry_vs_success() -> None:
    needs = evaluate_node({"tool_results": ["ERROR: boom"]})
    assert needs["evaluation_result"] == "needs_retry"
    ok = evaluate_node({"tool_results": ["ok"]})
    assert ok["evaluation_result"] == "success"


def test_retry_increments_attempt_and_records_error() -> None:
    out = retry_or_fallback_node({"attempt": 2})
    assert out["attempt"] == 3
    assert out["errors"]


def test_answer_prefers_last_tool_result() -> None:
    out = answer_node({"tool_results": ["a", "b"], "route": Route.TOOL.value})
    assert "b" in (out.get("final_answer") or "")


def test_finalize_emits_event() -> None:
    out = finalize_node({"scenario_id": "z"})
    assert any(e.get("node") == "finalize" for e in out.get("events", []))


def test_make_event_includes_metadata() -> None:
    e = make_event("n", "t", "m", foo=1)
    assert e["node"] == "n" and e["metadata"].get("foo") == 1
