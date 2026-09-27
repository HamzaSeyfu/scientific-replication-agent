from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class AgentRunner(Protocol):
    def run(self, *, prompt: str, cwd: Path, timeout_seconds: int) -> dict[str, Any]: ...


@dataclass
class VeritasBackendBridge:
    """Boundary for the future Veritas `create_agent_backend` adapter.

    We intentionally do not vendor Veritas internals. The next integration step
    is to implement Veritas' backend request/session contract against Nemotron,
    preserving upstream Apache-2.0 attribution and keeping our novel orchestration
    in this repository.
    """

    runner: AgentRunner

    def execute(self, *, prompt: str, working_directory: str, timeout_seconds: int = 900) -> dict[str, Any]:
        return self.runner.run(
            prompt=prompt,
            cwd=Path(working_directory),
            timeout_seconds=timeout_seconds,
        )
