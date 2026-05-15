"""Learnings ledger — persistent memory of how past failures were fixed.

When the Reflexion engine repairs a broken step, it writes a concise
entry to learnings.md. On every subsequent run, Stoa reads this file
and gives the AI the recorded fixes at planning time.

Result: each deployment gets smarter over time without fine-tuning or
manual prompt engineering. A fix discovered at 2am on a Tuesday is
automatically applied to every run from Wednesday onward.
"""

from __future__ import annotations

import datetime
from pathlib import Path


class LearningsLedger:
    def __init__(self, path: Path = Path("learnings.md")) -> None:
        self._path = path
        if not self._path.exists():
            self._path.write_text(
                "# Stoa Learnings Ledger\n\n"
                "Automatically updated. Do not delete — this is how Stoa improves.\n\n"
            )

    def record(self, workflow: str, step_id: str, failure: str, fix: str) -> None:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        entry = (
            f"## [{timestamp}] {workflow} / {step_id}\n"
            f"**Failure:** {failure}\n"
            f"**Fix applied:** {fix}\n\n"
        )
        with self._path.open("a") as f:
            f.write(entry)

    def read(self) -> str:
        return self._path.read_text() if self._path.exists() else ""

    def entries(self) -> list[dict[str, str]]:
        """Parse ledger into structured entries for the dashboard."""
        text = self.read()
        entries = []
        current: dict[str, str] = {}
        for line in text.splitlines():
            if line.startswith("## ["):
                if current:
                    entries.append(current)
                current = {"header": line.lstrip("# ").strip()}
            elif line.startswith("**Failure:**"):
                current["failure"] = line.replace("**Failure:**", "").strip()
            elif line.startswith("**Fix applied:**"):
                current["fix"] = line.replace("**Fix applied:**", "").strip()
        if current:
            entries.append(current)
        return entries
