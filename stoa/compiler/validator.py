"""AST-based validator for AI-generated code.

Before any AI-generated Python is executed, it passes through this validator.
The validator parses the code into an Abstract Syntax Tree (AST) and walks
every node looking for dangerous constructs.

If it finds anything on the blocklist, it raises ValidationError and the
code is never executed. This check happens in the host process before the
sandbox even starts — defense in depth.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


class ValidationError(Exception):
    """Raised when AI-generated code fails the safety check."""


# Functions and attributes that must never appear in AI-generated code.
_BLOCKED_CALLS = frozenset({
    "eval", "exec", "compile", "open", "__import__",
    "breakpoint", "input",
})

_BLOCKED_ATTRS = frozenset({
    "system", "popen", "spawn", "call", "run",  # os / subprocess
    "__class__", "__bases__", "__subclasses__",   # class introspection
    "__globals__", "__locals__", "__builtins__",  # scope escape
})

_BLOCKED_IMPORTS = frozenset({
    "subprocess", "os", "sys", "socket", "ctypes",
    "importlib", "pickle", "marshal", "shelve",
    "ftplib", "telnetlib", "smtplib",
})


@dataclass
class ValidationResult:
    passed: bool
    violations: list[str] = field(default_factory=list)


class _SafetyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in _BLOCKED_CALLS:
            self.violations.append(f"Blocked call: {node.func.id}() at line {node.lineno}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in _BLOCKED_ATTRS:
            self.violations.append(f"Blocked attribute: .{node.attr} at line {node.lineno}")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root in _BLOCKED_IMPORTS:
                self.violations.append(f"Blocked import: {alias.name} at line {node.lineno}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            root = node.module.split(".")[0]
            if root in _BLOCKED_IMPORTS:
                self.violations.append(
                    f"Blocked import: from {node.module} at line {node.lineno}"
                )
        self.generic_visit(node)


class ASTValidator:
    """Validates AI-generated Python code before execution."""

    def validate(self, code: str) -> ValidationResult:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return ValidationResult(passed=False, violations=[f"Syntax error: {exc}"])

        visitor = _SafetyVisitor()
        visitor.visit(tree)

        return ValidationResult(
            passed=len(visitor.violations) == 0,
            violations=visitor.violations,
        )

    def validate_or_raise(self, code: str) -> None:
        result = self.validate(code)
        if not result.passed:
            raise ValidationError(
                "AI-generated code failed safety validation:\n"
                + "\n".join(f"  - {v}" for v in result.violations)
            )
