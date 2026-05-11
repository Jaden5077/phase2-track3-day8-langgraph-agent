"""FastAPI UI: graph visualization, routing steps, optional real HITL (interrupt/resume)."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from importlib import resources
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from starlette.requests import Request

from .graph import build_graph
from .persistence import build_checkpointer
from .routing import route_after_approval, route_after_classify, route_after_evaluate, route_after_retry
from .scenarios import load_scenarios
from .state import AgentState, initial_state


def hitl_interrupt_env_enabled() -> bool:
    return os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true"


def _merge_state_for_preview(base: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    reducers = {"messages", "tool_results", "errors", "events"}
    out = dict(base)
    for key, val in delta.items():
        if key in reducers and isinstance(val, list):
            out[key] = list(out.get(key) or []) + val
        else:
            out[key] = val
    return out


def _routing_hint_after_node(node: str, merged: dict[str, Any]) -> str | None:
    if node == "classify":
        return route_after_classify(merged)  # type: ignore[arg-type]
    if node == "evaluate":
        return route_after_evaluate(merged)  # type: ignore[arg-type]
    if node == "retry":
        return route_after_retry(merged)  # type: ignore[arg-type]
    if node == "approval":
        return route_after_approval(merged)  # type: ignore[arg-type]
    if node == "intake":
        return "classify"
    if node == "tool":
        return "evaluate"
    if node in ("answer", "clarify", "dead_letter"):
        return "finalize"
    if node == "finalize":
        return "END"
    if node == "risky_action":
        return "approval"
    return None


def _normalize_stream_chunk(chunk: Any) -> dict[str, Any]:
    if isinstance(chunk, tuple) and len(chunk) == 2:
        payload = chunk[1]
        return payload if isinstance(payload, dict) else {}
    if isinstance(chunk, dict):
        return chunk
    return {}


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def _edge_id(source: str, target: str) -> str:
    return f"{source}__{target}"


def graph_topology_elements() -> list[dict[str, Any]]:
    """Static workflow graph (nodes + edges) for the lab graph; positions are preset for cytoscape."""
    nodes: list[tuple[str, str, float, float]] = [
        ("START", "START", 40, 240),
        ("intake", "intake", 160, 240),
        ("classify", "classify", 300, 240),
        ("answer", "answer", 480, 80),
        ("tool", "tool", 480, 240),
        ("clarify", "clarify", 480, 400),
        ("risky_action", "risky_action", 480, 560),
        ("evaluate", "evaluate", 660, 240),
        ("retry", "retry", 820, 360),
        ("approval", "approval", 660, 560),
        ("dead_letter", "dead_letter", 980, 400),
        ("finalize", "finalize", 1140, 240),
        ("END", "END", 1260, 240),
    ]
    pairs: list[tuple[str, str, str | None]] = [
        ("START", "intake", None),
        ("intake", "classify", None),
        ("classify", "answer", "simple"),
        ("classify", "tool", "tool / error"),
        ("classify", "clarify", "missing_info"),
        ("classify", "risky_action", "risky"),
        ("tool", "evaluate", None),
        ("evaluate", "answer", "ok"),
        ("evaluate", "retry", "needs_retry"),
        ("retry", "tool", "retry"),
        ("retry", "dead_letter", "max attempts"),
        ("answer", "finalize", None),
        ("clarify", "finalize", None),
        ("risky_action", "approval", None),
        ("approval", "tool", "approved"),
        ("approval", "clarify", "rejected"),
        ("dead_letter", "finalize", None),
        ("finalize", "END", None),
    ]
    elements: list[dict[str, Any]] = []
    for nid, label, x, y in nodes:
        elements.append(
            {
                "data": {"id": nid, "label": label},
                "position": {"x": x, "y": y},
            }
        )
    for src, tgt, lbl in pairs:
        elements.append(
            {
                "data": {
                    "id": _edge_id(src, tgt),
                    "source": src,
                    "target": tgt,
                    "label": lbl or "",
                }
            }
        )
    return elements


def _transitions_from_steps(steps: list[dict[str, Any]]) -> list[list[str]]:
    nodes_order = [str(s["node"]) for s in steps if isinstance(s.get("node"), str)]
    if not nodes_order:
        return []
    out: list[list[str]] = [["START", nodes_order[0]]]
    for i in range(1, len(nodes_order)):
        prev, curr = nodes_order[i - 1], nodes_order[i]
        if prev != curr:
            out.append([prev, curr])
    if nodes_order[-1] == "finalize":
        out.append(["finalize", "END"])
    return out


def _interrupts_list(snap: Any) -> list[Any]:
    raw = getattr(snap, "interrupts", None)
    if not raw:
        return []
    return list(raw)


def _interrupt_first_value(snap: Any) -> Any | None:
    items = _interrupts_list(snap)
    if not items:
        return None
    first = items[0]
    return getattr(first, "value", first)


def _interrupt_from_snapshot_or_values(snap: Any, values: dict[str, Any] | None) -> Any | None:
    """Prefer snapshot.interrupts; some versions expose ``__interrupt__`` on state values."""
    v = _interrupt_first_value(snap)
    if v is not None:
        return v
    if not values:
        return None
    raw = values.get("__interrupt__")
    if not raw:
        return None
    if isinstance(raw, list) and raw:
        item = raw[0]
        return getattr(item, "value", item)
    return raw


def collect_stream_updates(
    graph: Any,
    stream_input: Any,
    config: dict[str, Any],
    merged_start: dict[str, Any],
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run one stream segment; mutates ``steps`` and returns merged state dict."""
    merged = dict(merged_start)
    for raw in graph.stream(stream_input, config, stream_mode="updates"):
        chunk = _normalize_stream_chunk(raw)
        for node_name, delta in chunk.items():
            if not isinstance(node_name, str) or node_name.startswith("__"):
                continue
            if not isinstance(delta, dict):
                continue
            merged = _merge_state_for_preview(merged, delta)
            hint = _routing_hint_after_node(node_name, merged)
            steps.append(
                {
                    "node": node_name,
                    "delta": _json_safe(delta),
                    "state_snapshot": {
                        "route": merged.get("route"),
                        "attempt": merged.get("attempt"),
                        "max_attempts": merged.get("max_attempts"),
                        "should_retry": merged.get("should_retry"),
                        "evaluation_result": merged.get("evaluation_result"),
                        "approval": merged.get("approval"),
                        "final_answer": merged.get("final_answer"),
                        "pending_question": merged.get("pending_question"),
                        "events_count": len(merged.get("events") or []),
                        "tool_results_count": len(merged.get("tool_results") or []),
                    },
                    "routing_hint": hint,
                }
            )
    return merged


def _scenario_meta(scenario: Any) -> dict[str, Any]:
    return {
        "id": scenario.id,
        "query": scenario.query,
        "expected_route": scenario.expected_route.value,
        "requires_approval": scenario.requires_approval,
        "should_retry": scenario.should_retry,
        "max_attempts": scenario.max_attempts,
        "tags": scenario.tags,
    }


def run_scenario_graph(
    graph: Any,
    scenario_id: str,
    scenarios_path: Path,
    *,
    use_hitl: bool,
) -> dict[str, Any]:
    scenarios = load_scenarios(scenarios_path)
    scenario = next((s for s in scenarios if s.id == scenario_id), None)
    if scenario is None:
        raise KeyError(f"Unknown scenario_id: {scenario_id}")

    state: AgentState = initial_state(scenario)
    if use_hitl and hitl_interrupt_env_enabled():
        state = {**state, "thread_id": f"web-hitl-{uuid.uuid4().hex[:16]}"}

    config: dict[str, Any] = {"configurable": {"thread_id": state["thread_id"]}}
    steps: list[dict[str, Any]] = []
    collect_stream_updates(graph, state, config, dict(state), steps)
    snap = graph.get_state(config)
    merged_snap = dict(snap.values) if snap.values else merged

    intr = _interrupt_from_snapshot_or_values(snap, merged_snap if isinstance(merged_snap, dict) else None)
    if use_hitl and hitl_interrupt_env_enabled() and intr is not None:
        return {
            "status": "interrupt",
            "thread_id": state["thread_id"],
            "interrupt": _json_safe(intr),
            "scenario": _scenario_meta(scenario),
            "steps": steps,
            "transitions": _transitions_from_steps(steps),
            "merged_preview": _json_safe(merged_snap),
        }

    return {
        "status": "done",
        "thread_id": state["thread_id"],
        "scenario": _scenario_meta(scenario),
        "steps": steps,
        "transitions": _transitions_from_steps(steps),
        "final_state": _json_safe(merged_snap),
    }


def resume_scenario_graph(
    graph: Any,
    thread_id: str,
    approved: bool,
    reviewer: str,
    comment: str,
) -> dict[str, Any]:
    from langgraph.types import Command

    config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    snap = graph.get_state(config)
    if (snap.values is None or snap.values == {}) and not _interrupts_list(snap):
        raise KeyError(f"No checkpoint or interrupt for thread_id={thread_id}")

    resume_payload: dict[str, Any] = {
        "approved": approved,
        "reviewer": reviewer,
        "comment": comment,
    }
    base = dict(snap.values) if snap.values else {}
    steps: list[dict[str, Any]] = []
    merged = collect_stream_updates(graph, Command(resume=resume_payload), config, base, steps)
    snap2 = graph.get_state(config)
    merged_snap = dict(snap2.values) if snap2.values else merged

    intr2 = _interrupt_from_snapshot_or_values(
        snap2, merged_snap if isinstance(merged_snap, dict) else None
    )
    if intr2 is not None:
        return {
            "status": "interrupt",
            "thread_id": thread_id,
            "interrupt": _json_safe(intr2),
            "steps": steps,
            "transitions": _transitions_from_steps(steps),
            "merged_preview": _json_safe(merged_snap),
        }

    return {
        "status": "done",
        "thread_id": thread_id,
        "steps": steps,
        "transitions": _transitions_from_steps(steps),
        "final_state": _json_safe(merged_snap),
    }


class RunRequest(BaseModel):
    scenario_id: str = Field(min_length=1)
    use_hitl: bool = False


class ResumeRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    approved: bool
    reviewer: str = "web-user"
    comment: str = ""


def create_app(
    scenarios_path: Path | None = None,
    *,
    checkpointer_kind: str = "memory",
    database_url: str | None = None,
) -> Any:
    try:
        from fastapi import FastAPI, HTTPException  # type: ignore[import-not-found]
        from fastapi.responses import HTMLResponse  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install web dependencies: pip install -e '.[web]'") from exc

    path = scenarios_path or Path("data/sample/scenarios.jsonl")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        cp = build_checkpointer(checkpointer_kind, database_url)
        app.state.lab_graph = build_graph(checkpointer=cp)
        yield

    app = FastAPI(title="LangGraph lab routing demo", version="0.1.0", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        pkg = __package__ or "langgraph_agent_lab"
        return resources.files(pkg).joinpath("routing_demo.html").read_text(encoding="utf-8")

    @app.get("/api/graph-topology")
    def graph_topology() -> dict[str, Any]:
        return {"elements": graph_topology_elements()}

    @app.get("/api/hitl")
    def hitl_status() -> dict[str, bool]:
        return {"interrupt_env": hitl_interrupt_env_enabled()}

    @app.get("/api/scenarios")
    def list_scenarios() -> list[dict[str, Any]]:
        resolved = path if path.is_absolute() else Path.cwd() / path
        if not resolved.exists():
            raise HTTPException(status_code=500, detail=f"Scenarios file not found: {resolved}")
        items = load_scenarios(resolved)
        return [
            {
                "id": s.id,
                "query": s.query,
                "expected_route": s.expected_route.value,
                "requires_approval": s.requires_approval,
                "should_retry": s.should_retry,
                "max_attempts": s.max_attempts,
                "tags": s.tags,
            }
            for s in items
        ]

    @app.post("/api/run")
    def run_body(body: RunRequest, request: Request) -> dict[str, Any]:
        resolved = path if path.is_absolute() else Path.cwd() / path
        if not resolved.exists():
            raise HTTPException(status_code=500, detail=f"Scenarios file not found: {resolved}")
        if body.use_hitl and not hitl_interrupt_env_enabled():
            raise HTTPException(
                status_code=400,
                detail="use_hitl requires LANGGRAPH_INTERRUPT=true (e.g. agent-lab web --hitl).",
            )
        try:
            return run_scenario_graph(
                request.app.state.lab_graph,
                body.scenario_id,
                resolved,
                use_hitl=body.use_hitl,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/run/resume")
    def resume_body(body: ResumeRequest, request: Request) -> dict[str, Any]:
        if not hitl_interrupt_env_enabled():
            raise HTTPException(
                status_code=400,
                detail="Resume requires LANGGRAPH_INTERRUPT=true on the server.",
            )
        try:
            return resume_scenario_graph(
                request.app.state.lab_graph,
                body.thread_id,
                body.approved,
                body.reviewer,
                body.comment,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app
