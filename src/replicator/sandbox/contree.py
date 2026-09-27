from __future__ import annotations

import base64
import posixpath
import shlex
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from ..agent.workspace import ToolResult


class ContreeRuntime:
    """Own a sync ConTree client and persistent sandbox session.

    Imports are lazy so the normal unit-test install does not require ConTree.
    Credentials come from ConTree's normal saved-profile mechanism rather than
    being passed through prompts or committed configuration.
    """

    def __init__(self, *, profile: str | None = None, image: str = "docker://docker.io/python:3.11") -> None:
        self.profile = profile
        self.image_tag = image
        self._client_cm: Any = None
        self._client: Any = None
        self.session: Any = None

    def __enter__(self) -> "ContreeRuntime":
        from contree_client.httpx import ContreeClient
        from contree_sdk import ContreeSync

        self._client_cm = ContreeClient.from_profile(profile=self.profile)
        self._client = self._client_cm.__enter__()
        contree = ContreeSync(self._client)
        if self.image_tag.startswith(("docker://", "oci://")):
            image = contree.images.oci(self.image_tag)
        else:
            image = contree.images.use(self.image_tag)
        self.session = image.session()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._client_cm is not None:
            self._client_cm.__exit__(exc_type, exc, tb)


class ContreeWorkspaceTools:
    """Workspace tool surface backed by a persistent ConTree VM session."""

    def __init__(
        self,
        session: Any,
        *,
        root: str = "/workspace",
        max_output_chars: int = 20_000,
        network_enabled: bool = False,
    ):
        self.session = session
        self.root = posixpath.normpath(root)
        self.max_output_chars = max_output_chars
        self.network_enabled = network_enabled
        self._run_raw(f"mkdir -p {shlex.quote(self.root)}", timeout_seconds=60)

    def _relative(self, path: str) -> str:
        p = PurePosixPath(path)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"path escapes workspace: {path}")
        return str(p)

    def _absolute(self, path: str) -> str:
        rel = self._relative(path)
        return posixpath.join(self.root, rel)

    def _run_raw(self, command: str, *, timeout_seconds: int) -> ToolResult:
        try:
            proc = self.session.popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = proc.communicate(timeout=max(1, timeout_seconds))
            code = proc.wait()
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            return ToolResult(False, "command timed out", None)
        except Exception as exc:
            return ToolResult(False, str(exc), None)
        output = (stdout or "") + (stderr or "")
        return ToolResult(code == 0, self._truncate(output), code)

    def assert_network_isolation(self) -> None:
        if self.network_enabled:
            raise RuntimeError("network isolation check requested on network-enabled tools")
        result = self._run_raw("unshare --net -- true", timeout_seconds=30)
        if not result.ok:
            raise RuntimeError(
                "ConTree image cannot create a private network namespace; refusing blind run"
            )

    def run_shell(self, command: str, timeout_seconds: int = 120) -> ToolResult:
        inner = f"cd {shlex.quote(self.root)} && ({command})"
        if self.network_enabled:
            wrapped = inner
        else:
            offline_inner = (
                "export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1; "
                + inner
            )
            wrapped = f"unshare --net -- sh -lc {shlex.quote(offline_inner)}"
        return self._run_raw(wrapped, timeout_seconds=timeout_seconds)

    def list_files(self, path: str = ".") -> ToolResult:
        target = self._absolute(path)
        cmd = f"find {shlex.quote(target)} -type f -print | head -500"
        result = self._run_raw(cmd, timeout_seconds=30)
        if result.ok:
            prefix = self.root.rstrip("/") + "/"
            result = ToolResult(True, result.output.replace(prefix, ""), result.exit_code)
        return result

    def read_file(self, path: str) -> ToolResult:
        target = self._absolute(path)
        return self._run_raw(f"cat -- {shlex.quote(target)}", timeout_seconds=30)

    def write_file(self, path: str, content: str) -> ToolResult:
        target = self._absolute(path)
        payload = base64.b64encode(content.encode()).decode()
        parent = posixpath.dirname(target)
        script = (
            f"mkdir -p {shlex.quote(parent)} && "
            f"printf %s {shlex.quote(payload)} | base64 -d > {shlex.quote(target)}"
        )
        result = self._run_raw(script, timeout_seconds=30)
        if result.ok:
            return ToolResult(True, f"wrote {len(content.encode())} bytes to {path}", result.exit_code)
        return result

    def dispatch(self, name: str, arguments: dict[str, object]) -> ToolResult:
        if name == "list_files":
            return self.list_files(str(arguments.get("path", ".")))
        if name == "read_file":
            return self.read_file(str(arguments["path"]))
        if name == "write_file":
            return self.write_file(str(arguments["path"]), str(arguments["content"]))
        if name == "run_shell":
            return self.run_shell(
                str(arguments["command"]), int(arguments.get("timeout_seconds", 120))
            )
        return ToolResult(False, f"unknown tool: {name}")

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_output_chars:
            return text
        half = self.max_output_chars // 2
        return text[:half] + "\n... [output truncated] ...\n" + text[-half:]


class ContreeBlindExecutor:
    """Adapt NemotronWorkspaceAgent to an already-prepared ConTree workspace."""

    def __init__(self, client, tools: ContreeWorkspaceTools, *, max_steps: int = 40) -> None:
        from ..agent.nemotron import NemotronWorkspaceAgent

        if tools.network_enabled:
            raise ValueError("blind executor requires network-disabled ConTree tools")
        self.agent = NemotronWorkspaceAgent(client, max_steps=max_steps)
        self.tools = tools

    def run(
        self,
        *,
        prompt: str,
        cwd,
        timeout_seconds: float | None,
        transcript_path=None,
        append_transcript: bool = False,
    ):
        self.tools.assert_network_isolation()
        return self.agent.run(
            prompt=prompt,
            cwd=Path("/workspace"),
            timeout_seconds=timeout_seconds,
            transcript_path=transcript_path,
            append_transcript=append_transcript,
            tool_backend=self.tools,
        )
