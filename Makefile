.PHONY: install install-web test lint typecheck run-scenarios grade-local clean web

install:
	pip install -e '.[dev]'

install-web:
	pip install -e '.[dev,web]'

web:
	agent-lab web --config configs/lab.yaml

test:
	pytest

lint:
	ruff check src tests tests_phase12

typecheck:
	mypy src

run-scenarios:
	python -m langgraph_agent_lab.cli run-scenarios --config configs/lab.yaml --output outputs/metrics.json

grade-local:
	python -m langgraph_agent_lab.cli validate-metrics --metrics outputs/metrics.json

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov dist build *.egg-info outputs/*.json
