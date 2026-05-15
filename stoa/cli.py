"""Stoa command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="stoa",
    help="Deterministic, zero-trust execution framework for AI agents.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def init(
    directory: Path = typer.Argument(default=Path("."), help="Target directory"),
) -> None:
    """Set up a new Stoa project with config files and an example workflow."""
    target_env = directory / ".env"

    if target_env.exists():
        console.print("[yellow].env already exists — skipping[/yellow]")
    else:
        # importlib.resources works whether running from the repo or a pip install
        try:
            from importlib.resources import files
            env_text = files("stoa").joinpath("_data/.env.example").read_text()
        except (FileNotFoundError, TypeError):
            # Fall back to repo-relative path for development installs
            env_example = Path(__file__).parent.parent / ".env.example"
            env_text = env_example.read_text() if env_example.exists() else ""

        if env_text:
            target_env.write_text(env_text)
            console.print("[green]Created .env — add your API key to get started[/green]")
        else:
            console.print("[yellow]Could not find .env.example — create .env manually from .env.example[/yellow]")

    policy_dir = directory / "policies"
    policy_dir.mkdir(exist_ok=True)
    _write_default_policy(policy_dir / "default.yaml")

    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Edit [cyan].env[/cyan] and add your API key")
    console.print("  2. Run [cyan]stoa run examples/csv_aggregation/workflow.yaml[/cyan]")
    console.print("  3. Run [cyan]stoa savings --monthly-spend 500[/cyan] to see projected savings")


@app.command()
def run(
    workflow: Path = typer.Argument(..., help="Path to workflow YAML file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only, do not execute"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run a workflow YAML file through Stoa."""
    if not workflow.exists():
        console.print(f"[red]Workflow file not found: {workflow}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Running workflow:[/bold] {workflow}")

    # Import here to avoid slow startup for --help
    from stoa.runner import WorkflowRunner

    runner = WorkflowRunner(verbose=verbose)
    result = runner.run(workflow, dry_run=dry_run)

    if result.success:
        console.print(f"\n[green]✓ Completed[/green]  {result.steps_executed} steps  "
                      f"{result.tokens_used:,} tokens  ${result.cost_usd:.4f}")
        if result.output_path:
            console.print(f"  Output: {result.output_path}")
    else:
        console.print(f"\n[red]✗ Failed:[/red] {result.error}")
        raise typer.Exit(1)


@app.command()
def savings(
    prompt_tokens: int = typer.Option(8000, "--prompt-tokens", help="Avg prompt tokens per task run"),
    completion_tokens: int = typer.Option(2000, "--completion-tokens", help="Avg completion tokens per task run"),
    model: str = typer.Option("gpt-4o", "--model", help="Model name (see pricing.py for list)"),
) -> None:
    """Show the savings formula and a projection table at common run volumes.

    Uses your actual token counts for honest math. Run `stoa bench` first
    to measure your real token usage, then plug those numbers in here.

    Example:
        stoa savings --prompt-tokens 12000 --completion-tokens 3000 --model gpt-4o
    """
    from stoa.providers.pricing import cost_formula, savings_at_n_runs, REAL_WORLD_HAIRCUT

    formula = cost_formula(model, prompt_tokens, completion_tokens)
    cost_per_run = formula["cost_per_run_usd"]

    # ── Formula display ────────────────────────────────────────────────────────
    console.print()
    console.print("[bold]The formula[/bold]")
    console.print(f"  Cost per run  = {formula['formula']}")
    console.print(f"               = [red]${cost_per_run:.6f}[/red] per run")
    console.print()
    console.print("  Without Stoa: cost = cost_per_run × [bold]N[/bold]")
    console.print("  With Stoa:    cost = cost_per_run × [bold]1[/bold]  (plan once, run free)")
    console.print("  Theoretical savings = cost_per_run × (N − 1) / N")
    console.print()

    # ── Projection table ───────────────────────────────────────────────────────
    console.print("[bold]Projected savings at common run volumes[/bold]")
    console.print(f"  Model: {model}  |  {prompt_tokens:,} prompt tokens + {completion_tokens:,} completion tokens per run")
    console.print()

    table = Table(show_header=True, box=None, padding=(0, 3))
    table.add_column("Runs / month", style="dim")
    table.add_column("Without Stoa", justify="right")
    table.add_column("With Stoa", justify="right")
    table.add_column("Theoretical saving", justify="right")
    table.add_column("Real-world saving *", justify="right", style="green")

    for n in [10, 50, 100, 500, 1000, 5000]:
        p = savings_at_n_runs(model, prompt_tokens, completion_tokens, n)
        table.add_row(
            f"{n:,}",
            f"${p['cost_without_stoa_usd']:.4f}",
            f"${p['cost_with_stoa_usd']:.4f}",
            f"${p['theoretical_savings_usd']:.4f}  ({p['theoretical_savings_pct']:.1f}%)",
            f"${p['real_world_savings_usd']:.4f}  ({p['real_world_savings_pct']:.1f}%)",
        )

    console.print(table)
    console.print()
    console.print(
        f"[dim]* Real-world saving applies a {REAL_WORLD_HAIRCUT*100:.0f}% reduction to the theoretical figure.\n"
        f"  This accounts for: Reflexion recovery calls (~5% of runs trigger an extra AI call),\n"
        f"  one-off tasks mixed into your workflow volume (~5%), and re-planning when inputs\n"
        f"  change significantly (~5%). Subtract more if your workflows are mostly non-repeating.[/dim]"
    )
    console.print()
    console.print(
        "[dim]These numbers use list-price API costs. Your actual costs may differ based on "
        "volume discounts, prompt caching, or batching. Run [cyan]make bench[/cyan][dim] to measure "
        "real token usage on your specific workflows before making budget decisions.[/dim]"
    )


@app.command()
def bench(
    workflows: list[str] = typer.Option(
        ["csv_aggregation", "api_extraction", "multi_step_research"],
        "--workflow",
        "-w",
        help="Which example workflows to benchmark",
    ),
    runs: int = typer.Option(50, "--runs", help="Runs per workflow per mode"),
    output_dir: Path = typer.Option(Path("benchmarks/results"), "--output"),
) -> None:
    """Run the benchmark suite and produce cost/latency charts."""
    console.print(f"[bold]Running benchmark:[/bold] {runs} runs × {len(workflows)} workflows")
    console.print("[yellow]This uses your API key and costs approximately $0.30–$0.60[/yellow]")

    from benchmarks.runner import BenchmarkRunner

    runner = BenchmarkRunner(output_dir=output_dir)
    runner.run(workflows=workflows, runs_per_workflow=runs)

    console.print(f"\n[green]✓ Results written to {output_dir}/[/green]")
    console.print("  summary.json — raw numbers")
    console.print("  *.png        — charts (also linked in README)")


@app.command()
def dashboard() -> None:
    """Open the local Stoa dashboard in your browser."""
    import subprocess

    console.print("[bold]Starting Stoa dashboard at http://localhost:8501[/bold]")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "dashboard/app.py"],
        check=True,
    )


def _write_default_policy(path: Path) -> None:
    if path.exists():
        return
    path.write_text(
        "# Default Stoa tool permission policy\n"
        "# Deny everything not explicitly allowed.\n\n"
        "version: '1'\n"
        "default: deny\n\n"
        "rules:\n"
        "  - tool: http_get\n"
        "    allow: true\n"
        "    description: Read-only HTTP requests\n"
        "  - tool: read_file\n"
        "    allow: true\n"
        "    description: Read local files\n"
        "  - tool: write_file\n"
        "    allow: false\n"
        "    description: Disabled by default — enable explicitly\n"
        "  - tool: shell\n"
        "    allow: false\n"
        "    description: Never granted to agents\n"
    )


if __name__ == "__main__":
    app()
