"""Shared fixtures for Phase 1–2 extended tests (separate from lab ``tests/``)."""

from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("langgraph") is None,
    reason="langgraph not installed",
)
