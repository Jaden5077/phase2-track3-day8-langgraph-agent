# Cần làm:

## Phase 1: Sửa files

| File         | Vai trò                                                 |
| ------------ | ------------------------------------------------------- |
| `state.py`   | Schema state, reducer append-only, v.v.                 |
| `nodes.py`   | Logic từng node (classify, tool, evaluate, approval, …) |
| `routing.py` | Hàm route sau classify / evaluate / retry               |
| `graph.py`   | Nối node và cạnh trong LangGraph                        |

## Phase 2: Sửa files

| `persistence.py` | Factory checkpointer (memory / sqlite / …) |

## Phase 3: Viết báo cáo

| `report.py` | Sinh/nội dung báo cáo (thay skeleton) |

# Ghi chú:

## File ngoài `src` mà lab yêu cầu hoàn thành nội dung

| File                    | Ghi chú                                                                                                               |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `reports/lab_report.md` | README checklist: điền báo cáo (thường copy từ `reports/lab_report_template.md` nếu chưa có file tên `lab_report.md`) |

---

**Mặc định “không sửa”** (boilerplate / hạ tầng lab): ví dụ `cli.py`, `scenarios.py`, `__init__.py`, toàn bộ `tests/`, `configs/lab.yaml`, `data/`, `.github/workflows/`, `docker-compose.yml`, `docs/` (trừ khi giảng viên cho phép), `pyproject.toml`, v.v.

**Ngoại lệ thực tế** (thường vẫn được phép để tự kiểm tra, không nằm trong danh sách “core” trên):

- `tests/*.py` — comment trong `routing.py` nhắc “update tests for edge cases”.
- `data/sample/scenarios.jsonl` — README cho phép thêm scenario tự test.
- `configs/lab.yaml` — README Phase 2 đổi persistence (ví dụ `sqlite`).

Nếu bạn áp quy tắc **chỉ sửa đúng các file trong bảng đầu + `reports/lab_report.md` (+ tùy chọn `metrics.py`)** thì mọi thứ khác coi như **cố định** là hợp với tinh thần starter lab; mở rộng test/data/config là tùy chọn khi cần.

---

**User đã thực hiện:** cài dependencies vào `/venv` bằng lệnh `pip install -e ".[dev,sqlite]"`
