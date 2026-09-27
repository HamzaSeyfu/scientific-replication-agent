from __future__ import annotations

import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: str
    exit_code: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class WorkspaceTools:
    """Small tool surface for an agent operating inside one workspace.

    This is *not* the isolation boundary. The production path must run this
    inside Token Factory Sandboxes / another isolated worker. Path operations
    are constrained to ``root`` so the agent cannot use our file tools to read
    sealed targets or host files outside its assigned workspace.
    """

    def __init__(
        self,
        root: Path,
        *,
        env: Mapping[str, str] | None = None,
        max_output_chars: int = 20_000,
    ) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.env = dict(env) if env is not None else None
        self.max_output_chars = max_output_chars

    def _resolve(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"path escapes workspace: {relative_path}") from exc
        return candidate

    def list_files(self, path: str = ".") -> ToolResult:
        target = self._resolve(path)
        if not target.exists():
            return ToolResult(False, f"path does not exist: {path}")
        if target.is_file():
            return ToolResult(True, str(target.relative_to(self.root)))
        entries: list[str] = []
        for child in sorted(target.rglob("*")):
            if child.is_file():
                entries.append(str(child.relative_to(self.root)))
            if len(entries) >= 500:
                entries.append("... truncated after 500 files ...")
                break
        return ToolResult(True, "\n".join(entries))

    def read_file(self, path: str) -> ToolResult:
        target = self._resolve(path)
        if not target.is_file():
            return ToolResult(False, f"file does not exist: {path}")
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult(False, str(exc))
        return ToolResult(True, self._truncate(content))

    def write_file(self, path: str, content: str) -> ToolResult:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(False, str(exc))
        return ToolResult(True, f"wrote {len(content.encode('utf-8'))} bytes to {path}")

    def run_shell(self, command: str, timeout_seconds: int = 120) -> ToolResult:
        """Run a shell command inside the workspace.

        The command is intentionally unrestricted because scientific replication
        needs package managers, build systems and arbitrary experiment commands.
        Therefore callers MUST place the workspace inside an external isolation
        boundary before using this against untrusted repositories.
        """
        env = self.env if self.env is not None else os.environ.copy()
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self.root,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(1, timeout_seconds),
            )
        except subprocess.TimeoutExpired as exc:
            combined = (exc.stdout or "") + (exc.stderr or "")
            return ToolResult(False, self._truncate(combined or "command timed out"), None)
        except OSError as exc:
            return ToolResult(False, str(exc), None)
        combined = (proc.stdout or "") + (proc.stderr or "")
        return ToolResult(proc.returncode == 0, self._truncate(combined), proc.returncode)

    def dispatch(self, name: str, arguments: dict[str, object]) -> ToolResult:
        if name == "list_files":
            return self.list_files(str(arguments.get("path", ".")))
        if name == "read_file":
            return self.read_file(str(arguments["path"]))
        if name == "write_file":
            return self.write_file(str(arguments["path"]), str(arguments["content"]))
        if name == "run_shell":
            timeout = int(arguments.get("timeout_seconds", 120))
            return self.run_shell(str(arguments["command"]), timeout)
        return ToolResult(False, f"unknown tool: {name}")

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_output_chars:
            return text
        head = self.max_output_chars // 2
        tail = self.max_output_chars - head
        return text[:head] + "\n... [output truncated] ...\n" + text[-tail:]
