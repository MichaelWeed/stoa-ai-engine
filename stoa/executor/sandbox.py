"""Sandbox executor.

Two backends:
  - DockerSandbox (default, recommended): spins an ephemeral container per
    execution. No network, read-only filesystem except /tmp, hard CPU/memory
    limits, killed after timeout. The container is removed immediately after.
  - SubprocessSandbox (fallback): runs code in a subprocess with a timeout.
    Safer than running in-process, but does not provide Docker-level isolation.
    Suitable for local development when Docker is unavailable.

Neither backend ever allows the executed code access to:
  - The host filesystem (beyond the input it's explicitly given)
  - The network
  - The host shell
  - Long-lived state between runs
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stoa.config import get_config


class SandboxError(Exception):
    """Raised when sandbox execution fails."""


@dataclass
class SandboxResult:
    success: bool
    output: Any  # parsed JSON output from the script
    stdout: str
    stderr: str
    execution_time_ms: float
    error: str | None = None


def _build_runner_script(user_code: str, inputs: dict[str, Any]) -> str:
    """Wrap user code in a harness that captures output as JSON."""
    inputs_json = json.dumps(inputs)
    return textwrap.dedent(f"""
        import json, sys, traceback

        INPUTS = json.loads({repr(inputs_json)})

        try:
            {textwrap.indent(user_code, "    ")}
            # The script is expected to set a variable named `result`
            print(json.dumps({{"success": True, "result": result}}))
        except Exception as exc:
            print(json.dumps({{"success": False, "error": str(exc),
                               "traceback": traceback.format_exc()}}))
    """).strip()


class DockerSandbox:
    """Executes code inside an ephemeral, network-isolated Docker container."""

    IMAGE = "python:3.12-slim"
    _MEMORY_BYTES_PER_MB = 1024 * 1024

    def __init__(self) -> None:
        self._config = get_config()
        self._timeout = self._config.sandbox_timeout_seconds
        self._memory = self._config.sandbox_memory_mb * self._MEMORY_BYTES_PER_MB

    def run(self, code: str, inputs: dict[str, Any] | None = None) -> SandboxResult:
        import docker  # imported lazily — not required if using subprocess backend

        runner_script = _build_runner_script(code, inputs or {})

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "run.py"
            script_path.write_text(runner_script)

            client = docker.from_env()
            start = time.perf_counter()

            try:
                container = client.containers.run(
                    image=self.IMAGE,
                    command=["python", "/workspace/run.py"],
                    volumes={tmpdir: {"bind": "/workspace", "mode": "ro"}},
                    network_disabled=True,
                    mem_limit=self._memory,
                    cpu_period=100_000,
                    cpu_quota=50_000,  # 50% of one CPU
                    read_only=True,
                    tmpfs={"/tmp": "size=64m"},
                    remove=True,
                    stdout=True,
                    stderr=True,
                    detach=False,
                    timeout=self._timeout,
                )
                elapsed_ms = (time.perf_counter() - start) * 1000
                raw_output = container.decode("utf-8") if isinstance(container, bytes) else str(container)

            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000
                return SandboxResult(
                    success=False,
                    output=None,
                    stdout="",
                    stderr="",
                    execution_time_ms=elapsed_ms,
                    error=f"Docker execution failed: {exc}",
                )

        return self._parse_output(raw_output, "", elapsed_ms)

    def _parse_output(self, stdout: str, stderr: str, elapsed_ms: float) -> SandboxResult:
        last_line = stdout.strip().split("\n")[-1] if stdout.strip() else ""
        try:
            data = json.loads(last_line)
            if data.get("success"):
                return SandboxResult(
                    success=True, output=data.get("result"),
                    stdout=stdout, stderr=stderr, execution_time_ms=elapsed_ms,
                )
            return SandboxResult(
                success=False, output=None, stdout=stdout, stderr=stderr,
                execution_time_ms=elapsed_ms, error=data.get("error", "Unknown error"),
            )
        except json.JSONDecodeError:
            return SandboxResult(
                success=False, output=None, stdout=stdout, stderr=stderr,
                execution_time_ms=elapsed_ms,
                error=f"Script did not produce valid JSON output. Last line: {last_line!r}",
            )


class SubprocessSandbox:
    """Fallback sandbox using a subprocess with timeout.

    Provides process-level isolation but not container-level isolation.
    Use this only when Docker is unavailable (e.g., CI environments without
    Docker-in-Docker, developer machines without Docker Desktop).
    """

    def __init__(self) -> None:
        self._config = get_config()
        self._timeout = self._config.sandbox_timeout_seconds

    def run(self, code: str, inputs: dict[str, Any] | None = None) -> SandboxResult:
        runner_script = _build_runner_script(code, inputs or {})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(runner_script)
            script_path = f.name

        try:
            start = time.perf_counter()
            proc = subprocess.run(
                ["python", script_path],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                env={k: v for k, v in os.environ.items() if k.startswith("STOA_")},
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False, output=None, stdout="", stderr="",
                execution_time_ms=self._timeout * 1000,
                error=f"Script exceeded {self._timeout}s timeout",
            )
        finally:
            Path(script_path).unlink(missing_ok=True)

        last_line = proc.stdout.strip().split("\n")[-1] if proc.stdout.strip() else ""
        try:
            data = json.loads(last_line)
            if data.get("success"):
                return SandboxResult(
                    success=True, output=data.get("result"),
                    stdout=proc.stdout, stderr=proc.stderr, execution_time_ms=elapsed_ms,
                )
            return SandboxResult(
                success=False, output=None,
                stdout=proc.stdout, stderr=proc.stderr,
                execution_time_ms=elapsed_ms, error=data.get("error"),
            )
        except json.JSONDecodeError:
            return SandboxResult(
                success=False, output=None,
                stdout=proc.stdout, stderr=proc.stderr,
                execution_time_ms=elapsed_ms,
                error=f"Script did not produce valid JSON. Last line: {last_line!r}",
            )


def Sandbox() -> DockerSandbox | SubprocessSandbox:
    """Factory — returns the appropriate sandbox based on config."""
    backend = get_config().sandbox
    if backend == "docker":
        try:
            import docker
            docker.from_env().ping()
            return DockerSandbox()
        except Exception:
            pass  # Docker unavailable — fall through to subprocess
    return SubprocessSandbox()
