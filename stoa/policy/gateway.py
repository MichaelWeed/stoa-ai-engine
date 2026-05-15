"""Pre-action authorization gateway.

Every tool call the agent wants to make passes through this gateway first.
The check happens in deterministic code — not in the AI's judgment.

This is the answer to prompt injection: even if a malicious document tricks
the agent into requesting a forbidden tool call (like exporting a database),
the gateway denies it before anything executes. The AI's "intent" is
irrelevant. The policy file is the authority.

Policy files are YAML. The default policy is deny-all except http_get and
read_file. You must explicitly allow anything else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class PolicyDenied(Exception):
    """Raised when a tool call is denied by the active policy."""


@dataclass
class ToolCall:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    requested_by: str = "agent"


@dataclass
class PolicyRule:
    tool: str
    allow: bool
    description: str = ""


class PolicyGateway:
    """Loads a YAML policy and enforces it on every tool call.

    Default behavior when no rule matches: DENY.
    This is the zero-trust principle: deny unless explicitly allowed.
    """

    def __init__(self, policy_path: Path | None = None) -> None:
        self._rules: dict[str, PolicyRule] = {}
        self._default = "deny"

        if policy_path and policy_path.exists():
            self._load(policy_path)
        else:
            self._load_defaults()

    def _load(self, path: Path) -> None:
        data = yaml.safe_load(path.read_text())
        self._default = data.get("default", "deny")
        for rule_data in data.get("rules", []):
            rule = PolicyRule(
                tool=rule_data["tool"],
                allow=rule_data.get("allow", False),
                description=rule_data.get("description", ""),
            )
            self._rules[rule.tool] = rule

    def _load_defaults(self) -> None:
        self._default = "deny"
        self._rules = {
            "http_get": PolicyRule("http_get", allow=True, description="Read-only HTTP"),
            "read_file": PolicyRule("read_file", allow=True, description="Read local files"),
            "write_file": PolicyRule("write_file", allow=False, description="Disabled by default"),
            "shell": PolicyRule("shell", allow=False, description="Never granted"),
        }

    def authorize(self, call: ToolCall) -> None:
        """Check the call against the policy. Raises PolicyDenied if not allowed."""
        rule = self._rules.get(call.tool)

        if rule is not None:
            if rule.allow:
                return  # allowed
            raise PolicyDenied(
                f"Tool '{call.tool}' is explicitly denied by policy. "
                f"Rule: {rule.description!r}. "
                f"Requested by: {call.requested_by}"
            )

        # No rule found — apply default
        if self._default == "allow":
            return

        raise PolicyDenied(
            f"Tool '{call.tool}' has no policy rule and the default is 'deny'. "
            f"Add an explicit rule to your policy YAML to allow this tool. "
            f"Requested by: {call.requested_by}"
        )

    def is_allowed(self, tool_name: str) -> bool:
        try:
            self.authorize(ToolCall(tool=tool_name))
            return True
        except PolicyDenied:
            return False

    def summary(self) -> dict[str, str]:
        """Human-readable summary of the active policy."""
        return {
            name: ("✓ allowed" if rule.allow else "✗ denied")
            for name, rule in self._rules.items()
        }
