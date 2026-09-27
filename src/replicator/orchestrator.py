from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .audit import AuditReport, audit_transcript
from .benchmarks.reclaim import (
    ReclaimCase,
    build_blind_task,
    load_reclaim_case,
    parse_observed_metric,
    seal_reclaim_target,
)
from .core.evidence import write_certificate
from .core.models import ExecutionEvidence, EvidenceCertificate
from .core.sealing import TargetSealer
from .core.verifier import verify_scalar_claim


class BlindExecutor(Protocol):
    def run(
        self,
        *,
        prompt: str,
        cwd: Path,
        timeout_seconds: float | None,
        transcript_path: Path | None = None,
        append_transcript: bool = False,
    ): ...


@dataclass(frozen=True)
class ReplicationRun:
    case: ReclaimCase
    certificate: EvidenceCertificate
    audit: AuditReport
    transcript_path: Path
    raw_observed_value: float | None
    normalized_observed_value: float | None


def build_executor_prompt(case: ReclaimCase) -> str:
    task = build_blind_task(case)
    prompt = f"""REPLICATION CASE: {case.paper_id}

CLAIM:
{case.central_claim}

METRIC:
{case.metric}

SCOPE:
{case.scope}

TASK:
{task}

EVIDENCE CONTRACT:
- Execute the real released evaluation rather than estimating the answer.
- Preserve raw stdout/stderr in the transcript.
- Record repository/environment provenance before changing anything.
- Do not use a remembered, searched, or inferred published numeric answer to guide decisions.
- If faithful execution is blocked, stop with evidence of the blocker rather than substituting another experiment.
"""
    from .benchmarks.reclaim import assert_target_not_in_text

    assert_target_not_in_text(prompt, case.published_value)
    return prompt


def run_reclaim_case(
    *,
    case_path: Path,
    workspace: Path,
    output_dir: Path,
    executor: BlindExecutor,
    sealer: TargetSealer,
    timeout_seconds: float | None = 1800,
    repo_commit: str | None = None,
) -> ReplicationRun:
    case = load_reclaim_case(case_path)
    sealed_target = seal_reclaim_target(case, sealer)
    prompt = build_executor_prompt(case)

    output_dir.mkdir(parents=True, exist_ok=True)
    transcript = output_dir / "blind_executor.jsonl"
    result = executor.run(
        prompt=prompt,
        cwd=workspace,
        timeout_seconds=timeout_seconds,
        transcript_path=transcript,
        append_transcript=False,
    )

    audit = audit_transcript(case, transcript)
    raw_value: float | None = None
    normalized_value: float | None = None
    findings = list(audit.findings)

    if getattr(result, "success", False) and transcript.exists():
        try:
            raw_value, normalized_value = parse_observed_metric(
                case, transcript.read_text(encoding="utf-8")
            )
        except ValueError:
            findings.append("metric_not_observed")
    else:
        findings.append("execution_failed")

    execution = ExecutionEvidence(
        attempt=1,
        exit_code=0 if getattr(result, "success", False) else 1,
        command="blind-agent replication run",
        commit=repo_commit,
        raw_metrics={} if raw_value is None else {case.metric: raw_value},
        artifacts=[str(transcript)],
    )

    certificate = verify_scalar_claim(
        claim=case.claim_protocol,
        sealed_target=sealed_target,
        observed_value=normalized_value,
        sealer=sealer,
        executions=[execution],
        auditor_findings=sorted(set(findings)),
    )
    write_certificate(output_dir / "evidence.json", certificate)
    return ReplicationRun(
        case=case,
        certificate=certificate,
        audit=audit,
        transcript_path=transcript,
        raw_observed_value=raw_value,
        normalized_observed_value=normalized_value,
    )
