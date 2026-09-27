from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .benchmarks.reclaim import ReclaimCase, known_value_strings


@dataclass(frozen=True)
class AuditReport:
    completed: bool
    protocol_compliant: bool
    findings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def audit_transcript(case: ReclaimCase, transcript_path: Path) -> AuditReport:
    """Run deterministic pre-unseal checks over an agent transcript.

    Tool *results* are not blindly target-scanned because the real experiment may
    legitimately compute a number identical to the paper. We scan model-authored
    content and tool arguments, where a published target should never appear.
    A future network evidence broker will separately audit retrieved documents.
    """
    findings: list[str] = []
    notes: list[str] = []
    if not transcript_path.exists():
        return AuditReport(True, False, ["missing_transcript"], ["agent transcript not found"])

    target_tokens = {x.lower() for x in known_value_strings(case.published_value)}
    events = []
    for line_no, line in enumerate(transcript_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            findings.append("malformed_transcript")
            notes.append(f"invalid JSONL at line {line_no}")
            continue
        events.append(event)

        authored_parts: list[str] = []
        if event.get("event") == "assistant":
            authored_parts.append(str(event.get("content", "")))
            for call in event.get("tool_calls", []) or []:
                authored_parts.append(json.dumps(call.get("function", {}).get("arguments", "")))
        elif event.get("event") == "tool":
            # Arguments are agent-authored; result output is environment-authored.
            authored_parts.append(json.dumps(event.get("arguments", {}), sort_keys=True))

        authored = " ".join(authored_parts).lower()
        if authored and any(token in authored for token in target_tokens):
            findings.append("target_leakage")
            notes.append(f"published target appeared in agent-authored transcript at line {line_no}")

    if not events:
        findings.append("empty_transcript")

    findings = sorted(set(findings))
    hard = {"target_leakage", "malformed_transcript", "missing_transcript", "empty_transcript"}
    return AuditReport(
        completed=True,
        protocol_compliant=not any(x in hard for x in findings),
        findings=findings,
        notes=notes,
    )
