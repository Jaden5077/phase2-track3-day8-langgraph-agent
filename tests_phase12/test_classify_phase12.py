"""Classify heuristics: priority, sample scenarios, and non–scenario-id coupling."""

from __future__ import annotations

import pytest

from langgraph_agent_lab.nodes import classify_node
from langgraph_agent_lab.state import Route


def _route_for(query: str) -> str:
    state = {"query": query, "scenario_id": "synthetic", "thread_id": "t"}
    return classify_node(state)["route"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("How do I reset my password?", Route.SIMPLE.value),
        ("Please lookup order status for order 12345", Route.TOOL.value),
        ("Can you fix it?", Route.MISSING_INFO.value),
        ("Refund this customer and send confirmation email", Route.RISKY.value),
        ("Timeout failure while processing request", Route.ERROR.value),
        ("Delete customer account after support verification", Route.RISKY.value),
        ("System failure cannot recover after multiple attempts", Route.ERROR.value),
    ],
)
def test_classify_matches_documented_sample_queries(query: str, expected: str) -> None:
    assert _route_for(query) == expected


def test_risky_beats_tool_when_both_keywords_present() -> None:
    assert _route_for("Please refund order 9999") == Route.RISKY.value


def test_tool_keywords_extended() -> None:
    assert _route_for("Can you track my package") == Route.TOOL.value
    assert _route_for("Search the knowledge base for wifi") == Route.TOOL.value


def test_risky_keywords_extended() -> None:
    assert _route_for("Cancel my subscription immediately") == Route.RISKY.value
    assert _route_for("Remove access and revoke tokens") == Route.RISKY.value


def test_error_keywords_extended() -> None:
    assert _route_for("The service crashed during upgrade") == Route.ERROR.value
    assert _route_for("API unavailable in region east") == Route.ERROR.value


def test_missing_info_requires_short_query_and_pronoun() -> None:
    assert _route_for("Can you fix it?") == Route.MISSING_INFO.value
    assert _route_for("This is broken") == Route.MISSING_INFO.value
    long_vague = " ".join(["word"] * 10) + " it"
    assert _route_for(long_vague) == Route.SIMPLE.value
