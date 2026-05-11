"""Generate ``reports/lab_report.md`` from :class:`MetricsReport` (lab rubric sections)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .metrics import MetricsReport, ScenarioMetric


def _md_escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _scenario_results_table(metrics: MetricsReport) -> str:
    headers = [
        "Scenario",
        "Expected route",
        "Actual route",
        "Success",
        "Retries",
        "Interrupts",
        "Approval req.",
        "Errors (summary)",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in metrics.scenario_metrics:
        r: ScenarioMetric = row
        err = "; ".join(r.errors[:3]) if r.errors else "—"
        if len(r.errors) > 3:
            err += "…"
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_escape_cell(r.scenario_id),
                    _md_escape_cell(r.expected_route),
                    _md_escape_cell(r.actual_route or "—"),
                    "✓" if r.success else "✗",
                    str(r.retry_count),
                    str(r.interrupt_count),
                    "yes" if r.approval_required else "no",
                    _md_escape_cell(err),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _state_schema_table() -> str:
    rows = [
        ("thread_id, scenario_id, query", "overwrite", "Nhận diện luồng / nội dung ticket"),
        ("route, risk_level", "overwrite", "Kết quả classify"),
        ("attempt, max_attempts, should_retry", "overwrite", "Vòng retry + cấu hình scenario"),
        ("final_answer, pending_question, proposed_action", "overwrite", "Đầu ra / HITL"),
        ("approval, evaluation_result", "overwrite", "Quyết định approval & cổng evaluate"),
        ("messages, tool_results, errors, events", "append (add)", "Append-only audit & tool"),
    ]
    out = ["| Field group | Cách ghi | Ghi chú |", "|---|---|---|"]
    for cells in rows:
        out.append("| " + " | ".join(_md_escape_cell(c) for c in cells) + " |")
    return "\n".join(out)


def render_report(metrics: MetricsReport) -> str:
    """Build markdown report: rubric sections + bảng metrics + mô tả kiến trúc đã implement."""
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    summary = "\n".join(
        [
            f"- **Tổng scenario**: {metrics.total_scenarios}",
            f"- **Success rate**: {metrics.success_rate:.2%}",
            f"- **Trung bình số event (nodes visited)**: {metrics.avg_nodes_visited:.2f}",
            f"- **Tổng lần vào node retry**: {metrics.total_retries}",
            f"- **Tổng lần vào node approval (HITL / interrupt path)**: {metrics.total_interrupts}",
            f"- **resume_success** (mở rộng): {metrics.resume_success}",
        ]
    )

    arch = """Luồng **LangGraph** (``graph.py``):

1. ``START → intake → classify`` (chuẩn hóa query, gán route bằng keyword theo README: risky > tool > missing_info > error > simple).
2. **Nhánh**: ``simple → answer``; ``tool → evaluate``; ``missing_info → clarify``; ``risky → risky_action → approval``; **error → tool** (không nhảy thẳng vào retry) rồi ``evaluate`` và vòng ``retry`` có giới hạn ``max_attempts``.
3. **Retry / dead letter**: ``route_after_retry`` chuyển ``dead_letter`` khi hết hạn; ``dead_letter`` và các nhánh khác đều về ``finalize → END``.
4. **Persistence**: ``persistence.build_checkpointer`` — ``memory`` / ``none`` / ``sqlite`` (``sqlite3`` + ``SqliteSaver``) / Postgres tùy cấu hình.
5. **Web demo** (optional ``[web]``): FastAPI + Cytoscape topology tĩnh, animation theo ``transitions``, gradient node, export PNG (``full`` + ``scale``). HITL: ``LANGGRAPH_INTERRUPT=true`` + ``POST /api/run`` với ``use_hitl`` và ``POST /api/run/resume`` với ``Command(resume=…)``; graph biên dịch một lần trong lifespan để checkpoint resume."""

    failures = """1. **Lỗi tool tạm thời (S05)**: ``tool_node`` giả lập ERROR theo ``should_retry`` và ``max_attempts``; ``evaluate_node`` đặt ``needs_retry``; ``retry_or_fallback_node`` tăng ``attempt``; khi đủ số lần thì mock tool thành công hoặc ``dead_letter`` (S07, ``max_attempts: 1``).
2. **Hành động rủi ro (S04/S06)**: đi qua ``approval``; mock mặc định duyệt; với interrupt thật thì dừng tại ``interrupt()`` cho đến khi client resume."""

    persistence = """Dùng **checkpointer** trên cùng một ``CompiledGraph`` khi chạy web HITL (``thread_id`` ổn định / ``web-hitl-…``). CLI ``run-scenarios`` gắn ``thread_id`` từ ``initial_state``. SQLite (Phase 2) dùng file DB + ``check_same_thread=False`` theo gợi ý langgraph-checkpoint-sqlite."""

    extensions = """- **Giao diện web**: đồ thị Cytoscape, minh hoạ từng cạnh, tiếp tục animation sau resume HITL, export PNG HD.
- **HITL thật**: ``approval_node`` + ``interrupt()`` khi ``LANGGRAPH_INTERRUPT=true``; resume qua API.
- **Bộ test mở rộng**: ``tests_phase12/`` (tách khỏi ``tests/`` lab)."""

    improvements = """- Thay heuristic classify bằng LLM có guardrail; logging có cấu trúc (OpenTelemetry).
- SQLite / Postgres cho production + chứng minh time-travel; UI approval lưu reviewer LDAP."""

    return f"""# Day 08 Lab Report

> Bản báo cáo được sinh/đồng bộ từ ``report.render_report()`` khi chạy ``make run-scenarios`` (``write_report``). Điền thêm mục 1 (team) thủ công nếu cần.

## 1. Team / student

- **Name**: *(điền)*
- **Repo/commit**: *(điền)*
- **Date (generated)**: {now}

## 2. Architecture

{arch}

## 3. State schema

{_state_schema_table()}

## 4. Scenario results

Nguồn: ``outputs/metrics.json`` (lần chạy ``run-scenarios`` gần nhất).

### Tóm tắt

{summary}

### Bảng theo scenario

{_scenario_results_table(metrics)}

## 5. Failure analysis

{failures}

## 6. Persistence / recovery evidence

{persistence}

## 7. Extension work

{extensions}

## 8. Improvement plan

{improvements}
"""


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
