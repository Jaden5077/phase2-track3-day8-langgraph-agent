"""Checkpointer adapter."""

from __future__ import annotations

import sqlite3
from typing import Any


def build_checkpointer(kind: str = "memory", database_url: str | None = None) -> Any | None:
    """Return a LangGraph checkpointer.

    SQLite uses a long-lived :class:`sqlite3.Connection` plus :class:`SqliteSaver`; WAL and
    schema are applied on first use via the saver's ``setup()`` (see langgraph-checkpoint-sqlite).
    ``from_conn_string`` on ``SqliteSaver`` is a context manager and is not suitable as a
    return value for ``compile(checkpointer=...)``.
    """
    if kind == "none":
        return None
    if kind == "memory":
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()
    if kind == "sqlite":
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError as exc:
            raise RuntimeError("SQLite checkpointer requires: pip install langgraph-checkpoint-sqlite") from exc
        path = database_url or "checkpoints.db"
        conn = sqlite3.connect(path, check_same_thread=False)
        return SqliteSaver(conn)
    if kind == "postgres":
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
        except ImportError as exc:
            raise RuntimeError("Postgres checkpointer requires: pip install langgraph-checkpoint-postgres") from exc
        return PostgresSaver.from_conn_string(database_url or "")
    raise ValueError(f"Unknown checkpointer kind: {kind}")
