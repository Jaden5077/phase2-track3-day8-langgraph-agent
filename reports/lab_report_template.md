# Day 08 Lab Report — template & rubric

Khi chạy `make run-scenarios`, CLI gọi `write_report()` trong `src/langgraph_agent_lab/report.py` và **ghi đè** `reports/lab_report.md` với bảng metrics và các mục kiến trúc cố định. Giữ file này làm **mục lục / hướng dẫn**; nội dung số liệu luôn lấy từ `outputs/metrics.json` sau mỗi lần chạy scenario.

## 1. Team / student *(điền thủ công — không ghi đè bởi `report.py`)*

- Name:
- Repo/commit:
- Date (local):

## 2. Architecture *(được điền tự động trong `lab_report.md`)*

Mô tả đồng bộ với code hiện tại:

- `intake` → `classify` (keyword: risky > tool > missing_info > error > simple).
- Nhánh error: **tool trước**, rồi `evaluate` / `retry` có giới hạn `max_attempts`; không vào `retry` trước lần gọi tool đầu.
- Risky: `risky_action` → `approval` → `tool` hoặc `clarify`.
- `finalize` → END; `dead_letter` khi hết retry.

## 3. State schema *(bảng trong `report.py` → `lab_report.md`)*

Các trường chính trong `AgentState`: scalar ghi đè; `messages`, `tool_results`, `errors`, `events` dùng reducer `add`.

## 4. Scenario results *(tự động)*

- Tóm tắt: `total_scenarios`, `success_rate`, `avg_nodes_visited`, `total_retries`, `total_interrupts`.
- Bảng từng dòng: `scenario_metrics` (expected vs actual route, success, retries, interrupts, approval, lỗi rút gọn).

## 5. Failure analysis *(đoạn văn cố định trong `report.py` — có thể chỉnh trong code)*

- Retry / tool failure (S05, S07).
- Risky / approval (S04, S06) và HITL với `interrupt()`.

## 6. Persistence / recovery *(đoạn văn cố định + chứng cứ thực tế do bạn bổ sung)*

- `build_checkpointer`: memory / none / sqlite / postgres.
- `thread_id` trên CLI; web HITL dùng graph + checkpointer singleton và `Command(resume=…)`.

## 7. Extension work *(cập nhật theo repo này)*

- Web: FastAPI, topology Cytoscape, animation `transitions`, gradient node, **Export PNG** (`full` + `scale` cao).
- HITL: `LANGGRAPH_INTERRUPT`, `POST /api/run` + `use_hitl`, `POST /api/run/resume`; `agent-lab web --hitl`.
- Tests: `tests_phase12/` (routing, graph, persistence, …).

## 8. Improvement plan *(đoạn văn gợi ý trong `report.py`)*

- LLM classify, observability, SQLite/time-travel chứng minh thêm.

---

### Lệnh hữu ích

```bash
make run-scenarios    # → outputs/metrics.json + cập nhật reports/lab_report.md
make grade-local
make web              # hoặc make web-hitl
```
