from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..agent.nemotron import NemotronWorkspaceAgent
from ..llm.nebius import NemotronClient


class AgentRunner(Protocol):
    def run(self, *, prompt: str, cwd: Path, timeout_seconds: int) -> dict[str, Any]: ...


@dataclass
class VeritasBackendBridge:
    """Small stable boundary used by unit tests and non-Veritas callers."""

    runner: AgentRunner

    def execute(self, *, prompt: str, working_directory: str, timeout_seconds: int = 900) -> dict[str, Any]:
        return self.runner.run(
            prompt=prompt,
            cwd=Path(working_directory),
            timeout_seconds=timeout_seconds,
        )


class VeritasNemotronBackend:
    """Implements Veritas' AgentBackend contract with Nebius/Nemotron.

    Imports Veritas lazily so the core project can be installed and tested
    without pulling the upstream application. Session resume is deliberately
    not advertised yet; Veritas will therefore avoid its heartbeat/resume path.
    """

    def __init__(self, client: NemotronClient | None = None) -> None:
        self._agent = NemotronWorkspaceAgent(client or NemotronClient.from_env())

    @property
    def capabilities(self):
        from veritas.llm.runtime import AgentCapabilities

        return AgentCapabilities(supports_resume=False)

    def invoke(self, request):
        from veritas.llm.runtime import AgentResult

        cwd = Path(request.working_dir or Path.cwd())
        result = self._agent.run(
            prompt=request.prompt,
            cwd=cwd,
            timeout_seconds=request.timeout,
            env=request.env,
            transcript_path=request.transcript_path,
            append_transcript=request.append,
        )
        return AgentResult(
            success=result.success,
            timed_out=result.timed_out,
            exit_code=0 if result.success else 1,
            error=result.error,
        )


def patch_veritas_provider() -> None:
    """Register a runtime-only ``nebius`` provider in an installed Veritas.

    We patch the three references Veritas binds at import time instead of
    maintaining a fork. This keeps upstream replaceable while we validate the
    architecture. If the integration proves stable, we can upstream a provider
    hook or carry a tiny explicit patch later.
    """
    import veritas.llm as llm
    import veritas.llm.factory as factory
    import veritas.core.config as config
    import veritas.core.runner as runner

    original_factory = factory.create_agent_backend

    def create_agent_backend(provider: str):
        if provider.lower() == "nebius":
            return VeritasNemotronBackend()
        return original_factory(provider)

    factory.create_agent_backend = create_agent_backend
    llm.create_agent_backend = create_agent_backend
    runner.create_agent_backend = create_agent_backend

    if "nebius" not in config.VALID_PROVIDERS:
        config.VALID_PROVIDERS.append("nebius")
