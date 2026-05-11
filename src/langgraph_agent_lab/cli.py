"""CLI for the lab."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml

from .graph import build_graph
from .metrics import MetricsReport, metric_from_state, summarize_metrics, write_metrics
from .persistence import build_checkpointer
from .report import write_report
from .scenarios import load_scenarios
from .state import initial_state

app = typer.Typer(no_args_is_help=True)


@app.command("run-scenarios")
def run_scenarios(
    config: Annotated[Path, typer.Option("--config")],
    output: Annotated[Path, typer.Option("--output")],
) -> None:
    """Run all grading scenarios and write metrics JSON."""
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    scenarios = load_scenarios(cfg["scenarios_path"])
    checkpointer = build_checkpointer(cfg.get("checkpointer", "memory"), cfg.get("database_url"))
    graph = build_graph(checkpointer=checkpointer)
    metrics = []
    for scenario in scenarios:
        state = initial_state(scenario)
        run_config = {"configurable": {"thread_id": state["thread_id"]}}
        final_state = graph.invoke(state, config=run_config)
        metrics.append(
            metric_from_state(
                final_state,
                scenario.expected_route.value,
                scenario.requires_approval,
            )
        )
    report = summarize_metrics(metrics)
    write_metrics(report, output)
    if cfg.get("report_path"):
        write_report(report, cfg["report_path"])
    typer.echo(f"Wrote metrics to {output}")


@app.command("web")
def web(
    host: Annotated[str, typer.Option("--host", help="Bind address")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="HTTP port")] = 8765,
    config: Annotated[
        Path,
        typer.Option("--config", help="Lab YAML (scenarios_path, checkpointer)"),
    ] = Path("configs/lab.yaml"),
) -> None:
    """Web UI: step-by-step routing per scenario (requires pip install -e '.[web]')."""
    try:
        import uvicorn  # type: ignore[import-not-found]
    except ImportError:
        typer.secho("Missing deps. Run: pip install -e '.[web]'", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None

    scenarios_path = Path("data/sample/scenarios.jsonl")
    checkpointer_kind = "memory"
    database_url: str | None = None
    if config.exists():
        cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
        scenarios_path = Path(cfg["scenarios_path"])
        checkpointer_kind = str(cfg.get("checkpointer", "memory"))
        database_url = cfg.get("database_url")

    from .web_demo import create_app

    resolved = scenarios_path if scenarios_path.is_absolute() else Path.cwd() / scenarios_path
    if not resolved.exists():
        typer.secho(f"Scenarios file not found: {resolved}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    app = create_app(
        resolved,
        checkpointer_kind=checkpointer_kind,
        database_url=database_url,
    )
    typer.echo(f"Open http://{host}:{port}/ (scenarios: {resolved})")
    uvicorn.run(app, host=host, port=port)


@app.command("validate-metrics")
def validate_metrics(metrics: Annotated[Path, typer.Option("--metrics")]) -> None:
    """Validate metrics JSON schema for grading."""
    payload = json.loads(metrics.read_text(encoding="utf-8"))
    report = MetricsReport.model_validate(payload)
    if report.total_scenarios < 6:
        raise typer.BadParameter("Expected at least 6 scenarios")
    typer.echo(f"Metrics valid. success_rate={report.success_rate:.2%}")


if __name__ == "__main__":
    app()
