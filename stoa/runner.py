"""WorkflowRunner — ties all Stoa modules together for a single task run.

Execution order:
  1. Load workflow YAML
  2. Check idempotency cache (skip if already done with same inputs)
  3. Start FSM: PENDING → PLANNING
  4. Call planner (AI, once)
  5. Validate plan steps against AST safety checker
  6. Check policy gateway for required tools
  7. FSM: PLANNING → EXECUTING
  8. For each step:
     a. Record step against budget enforcer (raises if limit exceeded)
     b. If tool_call: authorize via policy gateway, then call tool
     c. If compute: run code in sandbox
  9. FSM: EXECUTING → VERIFYING
  10. Validate output schema
  11. FSM: VERIFYING → COMPLETE (or → RECOVERING on failure)
  12. Write idempotency record
  13. Return WorkflowResult
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from stoa.budget.enforcer import BudgetEnforcer, BudgetExceeded
from stoa.compiler.planner import Planner
from stoa.compiler.validator import ASTValidator, ValidationError
from stoa.config import get_config
from stoa.db import check_idempotency, idempotency_key, record_idempotency
from stoa.executor.sandbox import Sandbox
from stoa.fsm.engine import State, WorkflowFSM
from stoa.policy.gateway import PolicyDenied, PolicyGateway, ToolCall
from stoa.telemetry.ledger import LearningsLedger
from stoa.telemetry.reflexion import FailureType, ReflexionEngine, classify_failure


@dataclass
class WorkflowResult:
    success: bool
    task_id: str
    workflow_name: str
    output: Any = None
    output_path: Path | None = None
    steps_executed: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0
    fsm_trace: list[dict] = field(default_factory=list)
    error: str | None = None


class WorkflowRunner:
    def __init__(self, verbose: bool = False) -> None:
        self._verbose = verbose
        self._config = get_config()
        self._planner = Planner()
        self._validator = ASTValidator()
        self._sandbox = Sandbox()
        self._ledger = LearningsLedger()
        self._reflexion = ReflexionEngine(
            planner_client=self._planner._client,
            validator=self._validator,
            ledger=self._ledger,
        )

    def run(self, workflow_path: Path, dry_run: bool = False) -> WorkflowResult:
        spec = yaml.safe_load(workflow_path.read_text())
        workflow_name = spec.get("name", workflow_path.stem)
        task_description = spec.get("task", "")
        inputs = spec.get("inputs", {})
        policy_file = spec.get("policy")
        task_id = str(uuid.uuid4())[:8]

        idem_key = idempotency_key(workflow_name, inputs)
        cached = check_idempotency(idem_key)
        if cached:
            return WorkflowResult(
                success=True, task_id=task_id, workflow_name=workflow_name,
                output=cached, steps_executed=0, tokens_used=0, cost_usd=0.0,
            )

        fsm = WorkflowFSM(task_id=task_id)
        budget = BudgetEnforcer(model=self._config.model)
        policy = PolicyGateway(
            policy_path=Path(policy_file) if policy_file else None
        )

        # Inject learnings from past runs into planning context
        learnings = self._ledger.read()
        if learnings:
            inputs["_past_learnings"] = learnings[:2000]  # cap to avoid token bloat

        try:
            fsm.transition(State.PLANNING, "starting planning")
            budget.record_step()

            plan = self._planner.plan(task_description, context=inputs)
            budget.record_step(
                prompt_tokens=plan.prompt_tokens,
                completion_tokens=plan.completion_tokens,
            )

            # Validate all compute steps before execution begins
            for step in plan.steps:
                if step.code:
                    self._validator.validate_or_raise(step.code)

            # Check policy for all required tools up front
            for tool_name in plan.required_tools:
                policy.authorize(ToolCall(tool=tool_name))

            if dry_run:
                return WorkflowResult(
                    success=True, task_id=task_id, workflow_name=workflow_name,
                    output={"plan": plan.task_summary, "steps": len(plan.steps)},
                    tokens_used=plan.prompt_tokens + plan.completion_tokens,
                    cost_usd=plan.planning_cost_usd,
                    fsm_trace=fsm.trace(),
                )

            fsm.transition(State.EXECUTING, "plan validated")
            context: dict[str, Any] = {**inputs}

            for step in plan.steps:
                budget.record_step()

                if step.type == "tool_call" and step.tool:
                    policy.authorize(ToolCall(tool=step.tool, args=step.tool_args))
                    result = self._execute_tool(step.tool, step.tool_args, context)
                    context[step.output_key] = result

                elif step.type == "compute" and step.code:
                    sandbox_result = self._sandbox.run(step.code, inputs=context)

                    if not sandbox_result.success:
                        failure_type = classify_failure(sandbox_result.error or "")
                        if failure_type == FailureType.STRUCTURAL:
                            fsm.transition(State.RECOVERING, f"step {step.step_id} failed: {sandbox_result.error}")
                            fixed_code = self._reflexion.repair_structural(
                                workflow_name=workflow_name,
                                step_id=step.step_id,
                                broken_code=step.code,
                                error=sandbox_result.error or "",
                                context=context,
                            )
                            sandbox_result = self._sandbox.run(fixed_code, inputs=context)
                            fsm.transition(State.EXECUTING, f"step {step.step_id} recovered")

                        if not sandbox_result.success:
                            raise RuntimeError(f"Step {step.step_id} failed: {sandbox_result.error}")

                    context[step.output_key] = sandbox_result.output

                elif step.type == "output":
                    context[step.output_key] = context.get(step.output_key)

            fsm.transition(State.VERIFYING, "all steps completed")
            final_output = context.get("result", context)
            fsm.transition(State.COMPLETE, "output verified")

            record_idempotency(idem_key, final_output)
            snap = budget.snapshot()

            return WorkflowResult(
                success=True,
                task_id=task_id,
                workflow_name=workflow_name,
                output=final_output,
                steps_executed=snap.steps_used,
                tokens_used=snap.tokens_used,
                cost_usd=snap.cost_usd,
                fsm_trace=fsm.trace(),
            )

        except BudgetExceeded as exc:
            fsm.transition(State.FAILED, f"budget: {exc}")
            snap = budget.snapshot()
            return WorkflowResult(
                success=False, task_id=task_id, workflow_name=workflow_name,
                steps_executed=snap.steps_used, tokens_used=snap.tokens_used,
                cost_usd=snap.cost_usd, fsm_trace=fsm.trace(), error=str(exc),
            )

        except (PolicyDenied, ValidationError) as exc:
            fsm.transition(State.FAILED, f"security: {exc}")
            return WorkflowResult(
                success=False, task_id=task_id, workflow_name=workflow_name,
                fsm_trace=fsm.trace(), error=str(exc),
            )

        except Exception as exc:
            try:
                fsm.transition(State.FAILED, str(exc))
            except Exception:
                pass
            snap = budget.snapshot()
            return WorkflowResult(
                success=False, task_id=task_id, workflow_name=workflow_name,
                steps_executed=snap.steps_used, tokens_used=snap.tokens_used,
                cost_usd=snap.cost_usd, fsm_trace=fsm.trace(), error=str(exc),
            )

    def run_inline(
        self, name: str, task: str, inputs: dict[str, Any] = {}, policy: str | None = None
    ) -> WorkflowResult:
        """Run a task definition directly without a YAML file on disk."""
        import tempfile

        spec = {"name": name, "task": task, "inputs": inputs}
        if policy:
            spec["policy"] = policy

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(spec, f)
            tmp = Path(f.name)

        try:
            return self.run(tmp)
        finally:
            tmp.unlink(missing_ok=True)


    def _execute_tool(self, tool: str, args: dict, context: dict) -> Any:
        """Dispatch tool calls to the built-in tool registry."""
        if tool == "http_get":
            import httpx
            url = args.get("url", "")
            response = httpx.get(url, timeout=10)
            response.raise_for_status()
            return response.json() if "json" in response.headers.get("content-type", "") else response.text

        if tool == "read_file":
            path = Path(args.get("path", ""))
            return path.read_text()

        raise NotImplementedError(f"Tool '{tool}' is not implemented in this version. "
                                  f"See ROADMAP.md for the tool extension guide.")
