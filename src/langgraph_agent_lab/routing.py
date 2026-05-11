"""Routing functions for conditional edges."""

from __future__ import annotations

from .state import AgentState, Route


def route_after_classify(state: AgentState) -> str:
    """Map classified route to the next graph node.

    Error path must enter the tool first, then evaluate/retry forms the loop (see README).
    Unknown route values fall back to clarification instead of guessing an answer.
    """
    route = state.get("route", Route.SIMPLE.value)
    mapping = {
        Route.SIMPLE.value: "answer",
        Route.TOOL.value: "tool",
        Route.MISSING_INFO.value: "clarify",
        Route.RISKY.value: "risky_action",
        Route.ERROR.value: "tool",
    }
    return mapping.get(route, "clarify")


def route_after_retry(state: AgentState) -> str:
    """Decide whether to retry, fallback, or dead-letter."""
    if int(state.get("attempt", 0)) >= int(state.get("max_attempts", 3)):
        return "dead_letter"
    return "tool"


def route_after_evaluate(state: AgentState) -> str:
    """Decide whether tool result is satisfactory or needs retry (the loop gate)."""
    if state.get("evaluation_result") == "needs_retry":
        return "retry"
    return "answer"


def route_after_approval(state: AgentState) -> str:
    """Continue to tool if approved; otherwise return to clarification."""
    approval = state.get("approval") or {}
    return "tool" if approval.get("approved") else "clarify"
