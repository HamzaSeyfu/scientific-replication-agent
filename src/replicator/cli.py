from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core.evidence import write_certificate
from .core.models import ClaimProtocol, ExecutionEvidence
from .core.sealing import TargetSealer
from .core.verifier import verify_scalar_claim


def demo(output: Path) -> None:
    """Offline smoke test of the trust boundary, not a fake replication."""
    claim = ClaimProtocol(
        claim_id="demo-claim",
        statement="Demo metric should match its sealed published value.",
        metric_name="accuracy",
        dataset="demo",
        protocol="offline smoke test only",
        tolerance_relative=0.05,
    )
    sealer = TargetSealer(secret=b"local-development-secret-32bytes!!")
    sealed = sealer.seal(claim.claim_id, 0.847)

    execution = ExecutionEvidence(
        attempt=1,
        exit_code=0,
        command="offline-demo",
        raw_metrics={"accuracy": 0.844},
        artifacts=[],
    )
    cert = verify_scalar_claim(
        claim=claim,
        sealed_target=sealed,
        observed_value=0.844,
        sealer=sealer,
        executions=[execution],
    )
    write_certificate(output, cert)
    print(json.dumps(cert.to_dict(), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evidence-first replication prototype")
    parser.add_argument("--demo", action="store_true", help="run an offline trust-boundary smoke test")
    parser.add_argument("--output", type=Path, default=Path("evidence.json"))
    args = parser.parse_args()
    if args.demo:
        demo(args.output)
        return
    parser.error("first live-paper command is not wired yet; use --demo")


if __name__ == "__main__":
    main()
