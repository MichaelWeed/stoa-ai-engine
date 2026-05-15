"""Planner — the single AI call that produces a compiled workflow plan.

The LLM is given a task description and a schema. It returns a structured
plan: a typed Python script and a list of tool calls it needs. The script
is then validated, sandboxed, and executed deterministically — without
calling the AI again.

This is the core of Stoa's cost savings: pay once to plan, pay nothing
to execute N times.
"""

from __future__ import annotations

import json
import textwrap
from typing import Any

from pydantic import BaseModel, Field

from stoa.providers.client import PlannerClient

SYSTEM_PROMPT = textwrap.dedent("""
    You are a workflow compiler. You receive a task description and produce a
    deterministic execution plan as a JSON object.

    Rules you must follow:
    1. All arithmetic, aggregation, sorting, and data transformation must be
       expressed as Python code — never as inline AI reasoning. Numbers must
       come from code, not from you.
    2. The generated Python script must not use: eval(), exec(), __import__(),
       subprocess, os.system, or any shell invocation.
    3. Every external data source the script needs must be declared in
       `required_tools`. Do not access URLs or files that are not declared.
    4. The script must be self-contained: no imports beyond the standard
       library and the packages listed in `required_packages`.
    5. Return ONLY valid JSON matching the schema below. No prose, no markdown
       fences, no explanation outside the JSON.

    Output schema:
    {
      "task_summary": "one sentence describing what this workflow does",
      "steps": [
        {
          "step_id": "unique string",
          "description": "plain English description of this step",
          "type": "tool_call | compute | output",
          "tool": "tool name if type is tool_call, else null",
          "tool_args": { ... },
          "code": "Python snippet if type is compute, else null",
          "output_key": "variable name this step writes to"
        }
      ],
      "required_tools": ["list of tool names needed"],
      "required_packages": ["list of pip packages needed beyond stdlib"],
      "output_schema": { "field": "type description" }
    }
""").strip()


class PlanStep(BaseModel):
    step_id: str
    description: str
    type: str  # tool_call | compute | output
    tool: str | None = None
    tool_args: dict[str, Any] = Field(default_factory=dict)
    code: str | None = None
    output_key: str


class WorkflowPlan(BaseModel):
    task_summary: str
    steps: list[PlanStep]
    required_tools: list[str] = Field(default_factory=list)
    required_packages: list[str] = Field(default_factory=list)
    output_schema: dict[str, str] = Field(default_factory=dict)
    # Populated after the planning call
    prompt_tokens: int = 0
    completion_tokens: int = 0
    planning_cost_usd: float = 0.0
    planning_latency_ms: float = 0.0


class Planner:
    def __init__(self) -> None:
        self._client = PlannerClient()

    def plan(self, task_description: str, context: dict[str, Any] | None = None) -> WorkflowPlan:
        """Call the AI once and return a validated WorkflowPlan."""
        user_prompt = task_description
        if context:
            user_prompt += f"\n\nContext:\n{json.dumps(context, indent=2)}"

        result = self._client.complete(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.0,
        )

        try:
            raw = json.loads(result.content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Planner returned invalid JSON. "
                f"Raw response (first 500 chars):\n{result.content[:500]}"
            ) from exc

        plan = WorkflowPlan(**raw)
        plan.prompt_tokens = result.prompt_tokens
        plan.completion_tokens = result.completion_tokens
        plan.planning_latency_ms = result.latency_ms

        from stoa.providers.pricing import tokens_to_usd
        plan.planning_cost_usd = tokens_to_usd(
            self._client.model, result.prompt_tokens, result.completion_tokens
        )

        return plan
