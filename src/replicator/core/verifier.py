from __future__ import annotations

from .models import EvidenceCertificate, ExecutionEvidence, ClaimProtocol, Verdict
from .sealing import TargetSealer


def verify_scalar_claim(
    *,
    claim: ClaimProtocol,
    sealed_target,
    observed_value: float | None,
    sealer: TargetSealer,
    executions: list[ExecutionEvidence],
    auditor_findings: list[str] | None = None,
) -> EvidenceCertificate:
    findings = list(auditor_findings or [])
    published = sealer.unseal(sealed_target)

    if observed_value is None:
        return EvidenceCertificate(
            claim=claim,
            observed_value=None,
            published_value=published,
            verdict=Verdict.NOT_EVALUABLE,
            relative_error=None,
            executions=executions,
            auditor_findings=findings,
        )

    denominator = max(abs(published), 1e-12)
    rel_error = abs(observed_value - published) / denominator

    hard_flags = {
        "target_leakage",
        "wrong_dataset",
        "wrong_metric",
        "wrong_checkpoint",
        "protocol_deviation",
        "cherry_picking",
    }
    if any(flag in hard_flags for flag in findings):
        verdict = Verdict.NOT_REPRODUCED
    elif rel_error <= claim.tolerance_relative:
        verdict = Verdict.REPRODUCED
    elif rel_error <= max(0.30, claim.tolerance_relative):
        verdict = Verdict.PARTIAL
    else:
        verdict = Verdict.NOT_REPRODUCED

    return EvidenceCertificate(
        claim=claim,
        observed_value=observed_value,
        published_value=published,
        verdict=verdict,
        relative_error=rel_error,
        executions=executions,
        auditor_findings=findings,
    )
