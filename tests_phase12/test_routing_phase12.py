"""Extended routing coverage (boundaries, unknown routes, full route enum)."""

from __future__ import annotations

import pytest

from langgraph_agent_lab.routing import (
    route_after_approval,
    route_after_classify,
    route_after_evaluate,
    route_after_retry,
)
from langgraph_agent_lab.state import Route


@pytest.mark.parametrize(
    ("route", "expected"),
    [
        (Route.SIMPLE.value, "answer"),
        (Route.TOOL.value, "tool"),
        (Route.MISSING_INFO.value, "clarify"),
        (Route.RISKY.value, "risky_action"),
        (Route.ERROR.value, "tool"),
    ],
)
def test_route_after_classify_all_known_routes(route: str, expected: str) -> None:
    assert route_after_classify({"route": route}) == expected


def test_route_after_classify_unknown_route_goes_to_clarify() -> None:
    assert route_after_classify({"route": "not_a_real_route"}) == "clarify"


def test_route_after_classify_defaults_when_route_missing() -> None:
    assert route_after_classify({}) == "answer"


@pytest.mark.parametrize(
    ("attempt", "max_attempts", "expected"),
    [
        (0, 3, "tool"),
        (1, 3, "tool"),
        (2, 3, "tool"),
        (3, 3, "dead_letter"),
        (0, 1, "tool"),
        (1, 1, "dead_letter"),
    ],
)
def test_route_after_retry_dead_letter_threshold(attempt: int, max_attempts: int, expected: str) -> None:
    assert route_after_retry({"attempt": attempt, "max_attempts": max_attempts}) == expected


def test_route_after_retry_defaults_max_attempts() -> None:
    assert route_after_retry({"attempt": 99}) == "dead_letter"


@pytest.mark.parametrize(
    ("evaluation", "expected"),
    [
        ("success", "answer"),
        ("needs_retry", "retry"),
        (None, "answer"),
        ("", "answer"),
    ],
)
def test_route_after_evaluate(evaluation: str | None, expected: str) -> None:
    assert route_after_evaluate({"evaluation_result": evaluation}) == expected


@pytest.mark.parametrize(
    ("approval", "expected"),
    [
        ({"approved": True}, "tool"),
        ({"approved": False}, "clarify"),
        (None, "clarify"),
        ({}, "clarify"),
    ],
)
def test_route_after_approval(approval: dict | None, expected: str) -> None:
    assert route_after_approval({"approval": approval}) == expected
