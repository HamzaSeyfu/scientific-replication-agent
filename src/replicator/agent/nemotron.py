from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..llm.nebius import NemotronClient
from .workspace import WorkspaceTools


BLIND_EXECUTOR_SYSTEM_PROMPT = """You are the blind execution agent in an adversarial scientific-replication system.

Your job is to execute the supplied replication task inside the assigned workspace and leave real artifacts on disk. Work from the paper protocol, repository, logs, and tool outputs. You may diagnose failures and repair execution problems when that preserves the intended methodology.

Hard rules:
- Never search for, infer, request, or optimize toward the paper's published target value.
- Never choose a seed, checkpoint, metric, dataset, split, or branch because its result is closer to an expected number.
- Preserve scientific provenance. Any meaningful intervention must be explainable from repository evidence, official documentation, or execution failures.
- Do not claim success unless the requested experiment actually ran and produced evidence.
- If the task cannot be completed faithfully, leave the evidence needed to explain why and say so.
- The filesystem tools are scoped to the assigned workspace. Treat everything outside it as unavailable.
"""


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files recursively inside the assigned workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file inside the workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write a UTF-8 text file inside the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command in the workspace and return stdout/stderr and the exit code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 3600},
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
]


@dataclass(frozen=True)
class AgentRunResult:
    success: bool
    timed_out: bool
    final_text: str
    steps: int
    error: str | None = None


class NemotronWorkspaceAgent:
    """Tool-using Nemotron loop for a replication workspace."""

    def __init__(self, client: NemotronClient, *, max_steps: int = 40) -> None:
        self.client = client
        self.max_steps = max_steps

    def run(
        self,
        *,
        prompt: str,
        cwd: Path,
        timeout_seconds: float | None,
        env: Mapping[str, str] | None = None,
        transcript_path: Path | None = None,
        append_transcript: bool = False,
    ) -> AgentRunResult:
        start = time.monotonic()
        tools = WorkspaceTools(cwd, env=env)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": BLIND_EXECUTOR_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        transcript: list[dict[str, Any]] = []

        for step in range(1, self.max_steps + 1):
            remaining = self._remaining(start, timeout_seconds)
            if remaining is not None and remaining <= 0:
                self._write_transcript(transcript_path, transcript, append_transcript)
                return AgentRunResult(False, True, "", step - 1, "agent timeout")

            try:
                response = self.client.chat(messages=messages, tools=TOOL_SCHEMAS)
            except Exception as exc:
                transcript.append({"event": "model_error", "error": str(exc)})
                self._write_transcript(transcript_path, transcript, append_transcript)
                return AgentRunResult(False, False, "", step - 1, str(exc))

            message = response.choices[0].message
            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": message.content or "",
            }
            tool_calls = list(message.tool_calls or [])
            if tool_calls:
                assistant_message["tool_calls"] = [self._tool_call_to_dict(call) for call in tool_calls]
            messages.append(assistant_message)
            transcript.append({"event": "assistant", "step": step, **assistant_message})

            if not tool_calls:
                self._write_transcript(transcript_path, transcript, append_transcript)
                return AgentRunResult(True, False, message.content or "", step)

            for call in tool_calls:
                name = call.function.name
                arguments: dict[str, object] = {}
                try:
                    parsed_arguments = json.loads(call.function.arguments or "{}")
                    if not isinstance(parsed_arguments, dict):
                        raise ValueError("tool arguments must be an object")
                    arguments = parsed_arguments
                    result = tools.dispatch(name, arguments)
                except Exception as exc:
                    result_payload = {"ok": False, "output": str(exc), "exit_code": None}
                else:
                    result_payload = result.to_dict()

                tool_content = json.dumps(result_payload, sort_keys=True)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": tool_content,
                    }
                )
                transcript.append(
                    {
                        "event": "tool",
                        "step": step,
                        "tool_call_id": call.id,
                        "name": name,
                        "arguments": arguments,
                        "result": result_payload,
                    }
                )

        self._write_transcript(transcript_path, transcript, append_transcript)
        return AgentRunResult(False, False, "", self.max_steps, "max agent steps exceeded")

    @staticmethod
    def _remaining(start: float, timeout_seconds: float | None) -> float | None:
        if timeout_seconds is None or timeout_seconds <= 0:
            return None
        return timeout_seconds - (time.monotonic() - start)

    @staticmethod
    def _tool_call_to_dict(call: Any) -> dict[str, Any]:
        return {
            "id": call.id,
            "type": "function",
            "function": {
                "name": call.function.name,
                "arguments": call.function.arguments,
            },
        }

    @staticmethod
    def _write_transcript(path: Path | None, events: list[dict[str, Any]], append: bool) -> None:
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with path.open(mode, encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
