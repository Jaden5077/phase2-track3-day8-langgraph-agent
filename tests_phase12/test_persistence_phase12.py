"""Checkpointer factory: memory/none/sqlite wiring and failure modes."""

from __future__ import annotations

import pytest

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import Route, Scenario, initial_state

try:
    import langgraph.checkpoint.sqlite as _sqlite_mod  # noqa: F401

    HAS_SQLITE_SAVER = True
except ImportError:
    HAS_SQLITE_SAVER = False


def test_build_checkpointer_none() -> None:
    assert build_checkpointer("none") is None


def test_build_checkpointer_memory_is_usable_with_graph() -> None:
    cp = build_checkpointer("memory")
    graph = build_graph(checkpointer=cp)
    scenario = Scenario(id="p1", query="hello world", expected_route=Route.SIMPLE)
    state = initial_state(scenario)
    cfg = {"configurable": {"thread_id": state["thread_id"]}}
    graph.invoke(state, config=cfg)
    snap = graph.get_state(cfg)
    assert snap.values is not None


def test_build_checkpointer_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown checkpointer"):
        build_checkpointer("not-a-kind")


@pytest.mark.skipif(not HAS_SQLITE_SAVER, reason="langgraph-checkpoint-sqlite not installed")
def test_sqlite_checkpointer_persists_thread_state(tmp_path: Path) -> None:
    db = tmp_path / "cp.db"
    cp = build_checkpointer("sqlite", str(db))
    graph = build_graph(checkpointer=cp)
    scenario = Scenario(id="sqlite-flow", query="lookup order 1", expected_route=Route.TOOL)
    state = initial_state(scenario)
    cfg = {"configurable": {"thread_id": "thread-sqlite-flow"}}
    final = graph.invoke(state, config=cfg)
    assert final.get("route") == Route.TOOL.value
    assert db.exists()
    snap = graph.get_state(cfg)
    assert snap.values.get("route") == Route.TOOL.value
