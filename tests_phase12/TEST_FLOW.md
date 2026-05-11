# Phase 1–2 extended test flow (`tests_phase12/`)

These tests are **separate from** the lab `tests/` suite: they assume Phase 1 graph + routing + nodes and Phase 2 persistence behaviors are implemented, and they aim for **broader coverage** (routing edges, classification policy, per-node units, full `scenarios.jsonl`, SQLite wiring).

## Run

```bash
pytest tests_phase12 -q
# or with the rest of the project (pyproject includes this folder):
pytest
```

Install optional SQLite checkpointer for the persistence test:

```bash
pip install -e ".[dev,sqlite]"
```

## Layered flow (recommended mental order)

1. **`test_routing_phase12.py`** — Pure functions: every `Route` after classify (including `error → tool`), retry cap, evaluate gate, approval gate, unknown route → `clarify`.
2. **`test_classify_phase12.py`** — Keyword priority (risky beats tool), README sample queries, extra keywords (cancel/track/crash/unavailable), missing-info guard (length + pronoun).
3. **`test_nodes_phase12.py`** — Isolated node outputs: transient tool errors, evaluate, retry counter, answer grounding, events.
4. **`test_graph_phase12.py`** — Compiled LangGraph: all JSONL scenarios must satisfy `metric_from_state`, S05 retry behavior, S07 dead letter, HITL presence for risky rows, patched rejection path, optional metrics JSON roundtrip.
5. **`test_persistence_phase12.py`** — `build_checkpointer`: `none`, `memory` + `get_state`, unknown kind error, **SQLite** persistence when the extra package is installed.

`conftest.py` skips the whole package if `langgraph` is missing (same idea as the lab smoke test).
