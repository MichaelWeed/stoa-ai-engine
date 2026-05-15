"""Tests for the benchmark runner — verifies it produces valid output."""

from pathlib import Path
import tempfile

from benchmarks.runner import BenchmarkRunner


def test_benchmark_produces_summary():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = BenchmarkRunner(output_dir=Path(tmpdir))
        results = runner.run(workflows=["csv_aggregation"], runs_per_workflow=10)

    assert len(results) == 1
    s = results[0]
    assert s["workflow"] == "csv_aggregation"
    assert "raw" in s
    assert "stoa" in s
    assert "savings" in s

    raw = s["raw"]
    stoa = s["stoa"]
    savings = s["savings"]

    # Stoa should always be cheaper after the first run
    assert stoa["avg_cost_usd"] < raw["avg_cost_usd"]
    # Stoa latency should be dramatically lower
    assert stoa["median_latency_ms"] < raw["median_latency_ms"]
    # Stoa determinism should be 100%
    assert stoa["determinism_pct"] == 100.0
    # Break-even should be a small positive integer
    assert 1 <= savings["break_even_runs"] <= 50


def test_charts_are_written():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        BenchmarkRunner(output_dir=output_dir).run(
            workflows=["csv_aggregation"], runs_per_workflow=5
        )
        for chart in ["cost_comparison", "break_even", "latency_distribution", "determinism"]:
            assert (output_dir / f"{chart}.png").exists(), f"{chart}.png not generated"
