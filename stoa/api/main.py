"""FastAPI application — HTTP interface to the Stoa execution engine."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from stoa.providers.pricing import savings_projection
from stoa.runner import WorkflowResult, WorkflowRunner
from stoa.telemetry.ledger import LearningsLedger

app = FastAPI(
    title="Stoa",
    description="Deterministic, zero-trust execution framework for AI agents",
    version="0.1.0",
)


class RunRequest(BaseModel):
    name: str
    task: str
    inputs: dict[str, Any] = {}
    policy: str | None = None


class SavingsRequest(BaseModel):
    monthly_spend_usd: float
    workflow_type: str = "repeated"
    model: str = "gpt-4o"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/plan")
def plan_workflow(req: RunRequest) -> dict:
    """Generate a plan for a workflow without executing it (dry run)."""
    spec = {"name": req.name, "task": req.task, "inputs": req.inputs}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(spec, f)
        tmp = Path(f.name)

    runner = WorkflowRunner()
    result = runner.run(tmp, dry_run=True)
    tmp.unlink(missing_ok=True)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return {
        "task_id": result.task_id,
        "plan": result.output,
        "tokens_used": result.tokens_used,
        "cost_usd": result.cost_usd,
    }


@app.post("/run")
def run_workflow(req: RunRequest) -> dict:
    """Run a workflow to completion."""
    spec = {"name": req.name, "task": req.task, "inputs": req.inputs}
    if req.policy:
        spec["policy"] = req.policy

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(spec, f)
        tmp = Path(f.name)

    runner = WorkflowRunner()
    result: WorkflowResult = runner.run(tmp)
    tmp.unlink(missing_ok=True)

    if not result.success:
        raise HTTPException(
            status_code=500,
            detail={"error": result.error, "fsm_trace": result.fsm_trace},
        )

    return {
        "task_id": result.task_id,
        "output": result.output,
        "steps_executed": result.steps_executed,
        "tokens_used": result.tokens_used,
        "cost_usd": result.cost_usd,
        "fsm_trace": result.fsm_trace,
    }


@app.get("/trace/{task_id}")
def get_trace(task_id: str) -> dict:
    """Return the FSM execution trace for a completed task."""
    # In the open-source version, traces are returned inline from /run.
    # A persistent trace store is part of the enterprise roadmap.
    return {"task_id": task_id, "note": "Traces are returned inline from /run in this version."}


@app.get("/budget")
def get_budget_config() -> dict:
    """Return the active budget limits."""
    from stoa.config import get_config
    cfg = get_config()
    return {
        "max_steps": cfg.max_steps,
        "token_budget": cfg.token_budget,
        "step_timeout_seconds": cfg.step_timeout_seconds,
        "sandbox": cfg.sandbox,
    }


@app.post("/savings")
def calculate_savings(req: SavingsRequest) -> dict:
    """Estimate how much Stoa would save on a given monthly API spend."""
    profiles = {
        "repeated": {"runs": 1000, "prompt_tokens": 8000, "completion_tokens": 2000},
        "mixed":    {"runs": 200,  "prompt_tokens": 8000, "completion_tokens": 2000},
        "one-shot": {"runs": 20,   "prompt_tokens": 8000, "completion_tokens": 2000},
    }
    p = profiles.get(req.workflow_type, profiles["repeated"])
    proj = savings_projection(req.model, p["prompt_tokens"], p["completion_tokens"], p["runs"])

    cost_with = req.monthly_spend_usd * (1 - proj["savings_pct"] / 100)
    return {
        "monthly_spend_usd": req.monthly_spend_usd,
        "estimated_with_stoa_usd": round(cost_with, 2),
        "projected_savings_usd": round(req.monthly_spend_usd - cost_with, 2),
        "savings_pct": proj["savings_pct"],
        "break_even_runs": proj["break_even_runs"],
        "workflow_type": req.workflow_type,
    }


@app.get("/learnings")
def get_learnings() -> dict:
    """Return entries from the learnings ledger."""
    ledger = LearningsLedger()
    return {"entries": ledger.entries(), "total": len(ledger.entries())}
