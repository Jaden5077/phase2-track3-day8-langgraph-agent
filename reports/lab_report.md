# Day 08 Lab Report

> Bản báo cáo được sinh/đồng bộ từ `report.render_report()` khi chạy `make run-scenarios` (`write_report`). Điền thêm mục 1 (team) thủ công nếu cần.

## 1. Team / student

- **Name**: Nguyễn Đức Dũng
- **Repo/commit**: this repo
- **Date (generated)**: 2026-05-11 08:39 UTC

## 2. Architecture

Luồng **LangGraph** (`graph.py`):

1. `START → intake → classify` (chuẩn hóa query, gán route bằng keyword theo README: risky > tool > missing_info > error > simple).
2. **Nhánh**: `simple → answer`; `tool → evaluate`; `missing_info → clarify`; `risky → risky_action → approval`; **error → tool** (không nhảy thẳng vào retry) rồi `evaluate` và vòng `retry` có giới hạn `max_attempts`.
3. **Retry / dead letter**: `route_after_retry` chuyển `dead_letter` khi hết hạn; `dead_letter` và các nhánh khác đều về `finalize → END`.
4. **Persistence**: `persistence.build_checkpointer` — `memory` / `none` / `sqlite` (`sqlite3` + `SqliteSaver`) / Postgres tùy cấu hình.
5. **Web demo** (optional `[web]`): FastAPI + Cytoscape topology tĩnh, animation theo `transitions`, gradient node, export PNG (`full` + `scale`). HITL: `LANGGRAPH_INTERRUPT=true` + `POST /api/run` với `use_hitl` và `POST /api/run/resume` với `Command(resume=…)`; graph biên dịch một lần trong lifespan để checkpoint resume.

## 3. State schema

| Field group                                     | Cách ghi     | Ghi chú                             |
| ----------------------------------------------- | ------------ | ----------------------------------- |
| thread_id, scenario_id, query                   | overwrite    | Nhận diện luồng / nội dung ticket   |
| route, risk_level                               | overwrite    | Kết quả classify                    |
| attempt, max_attempts, should_retry             | overwrite    | Vòng retry + cấu hình scenario      |
| final_answer, pending_question, proposed_action | overwrite    | Đầu ra / HITL                       |
| approval, evaluation_result                     | overwrite    | Quyết định approval & cổng evaluate |
| messages, tool_results, errors, events          | append (add) | Append-only audit & tool            |

## 4. Scenario results

Nguồn: `outputs/metrics.json` (lần chạy `run-scenarios` gần nhất).

### Tóm tắt

- **Tổng scenario**: 7
- **Success rate**: 100.00%
- **Trung bình số event (nodes visited)**: 7.00
- **Tổng lần vào node retry**: 3
- **Tổng lần vào node approval (HITL / interrupt path)**: 2
- **resume_success** (mở rộng): False

### Bảng theo scenario

| Scenario        | Expected route | Actual route | Success | Retries | Interrupts | Approval req. | Errors (summary)                                         |
| --------------- | -------------- | ------------ | ------- | ------- | ---------- | ------------- | -------------------------------------------------------- |
| S01_simple      | simple         | simple       | ✓       | 0       | 0          | no            | —                                                        |
| S02_tool        | tool           | tool         | ✓       | 0       | 0          | no            | —                                                        |
| S03_missing     | missing_info   | missing_info | ✓       | 0       | 0          | no            | —                                                        |
| S04_risky       | risky          | risky        | ✓       | 0       | 1          | yes           | —                                                        |
| S05_error       | error          | error        | ✓       | 2       | 0          | no            | transient failure attempt=1; transient failure attempt=2 |
| S06_delete      | risky          | risky        | ✓       | 0       | 1          | yes           | —                                                        |
| S07_dead_letter | error          | error        | ✓       | 1       | 0          | no            | transient failure attempt=1                              |

## 5. Failure analysis

1. **Lỗi tool tạm thời (S05)**: `tool_node` giả lập ERROR theo `should_retry` và `max_attempts`; `evaluate_node` đặt `needs_retry`; `retry_or_fallback_node` tăng `attempt`; khi đủ số lần thì mock tool thành công hoặc `dead_letter` (S07, `max_attempts: 1`).
2. **Hành động rủi ro (S04/S06)**: đi qua `approval`; mock mặc định duyệt; với interrupt thật thì dừng tại `interrupt()` cho đến khi client resume.

## 6. Persistence / recovery evidence

Dùng **checkpointer** trên cùng một `CompiledGraph` khi chạy web HITL (`thread_id` ổn định / `web-hitl-…`). CLI `run-scenarios` gắn `thread_id` từ `initial_state`. SQLite (Phase 2) dùng file DB + `check_same_thread=False` theo gợi ý langgraph-checkpoint-sqlite.

## 7. Extension work

- **Giao diện web**: đồ thị Cytoscape, minh hoạ từng cạnh, tiếp tục animation sau resume HITL, export PNG HD.
- **HITL thật**: `approval_node` + `interrupt()` khi `LANGGRAPH_INTERRUPT=true`; resume qua API.
- **Bộ test mở rộng**: `tests_phase12/` (tách khỏi `tests/` lab).

## 8. Improvement plan

- Thay heuristic classify bằng LLM có guardrail; logging có cấu trúc (OpenTelemetry).
- SQLite / Postgres cho production + chứng minh time-travel; UI approval lưu reviewer LDAP.
