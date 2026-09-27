from replicator.core.models import ClaimProtocol, ExecutionEvidence, Verdict
from replicator.core.sealing import TargetSealer
from replicator.core.verifier import verify_scalar_claim


def _claim():
    return ClaimProtocol(
        claim_id="c1",
        statement="accuracy",
        metric_name="accuracy",
        tolerance_relative=0.05,
    )


def test_reproduced_when_within_tolerance():
    sealer = TargetSealer(secret=b"z" * 32)
    sealed = sealer.seal("c1", 0.90)
    cert = verify_scalar_claim(
        claim=_claim(),
        sealed_target=sealed,
        observed_value=0.88,
        sealer=sealer,
        executions=[ExecutionEvidence(attempt=1, exit_code=0, command="run")],
    )
    assert cert.verdict == Verdict.REPRODUCED


def test_adversarial_hard_flag_fails_closed():
    sealer = TargetSealer(secret=b"z" * 32)
    sealed = sealer.seal("c1", 0.90)
    cert = verify_scalar_claim(
        claim=_claim(),
        sealed_target=sealed,
        observed_value=0.899,
        sealer=sealer,
        executions=[ExecutionEvidence(attempt=1, exit_code=0, command="run")],
        auditor_findings=["wrong_dataset"],
    )
    assert cert.verdict == Verdict.NOT_REPRODUCED
