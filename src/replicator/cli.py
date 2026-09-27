from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .benchmarks.reclaim import load_reclaim_case
from .core.evidence import write_certificate
from .core.models import ClaimProtocol, ExecutionEvidence
from .core.sealing import TargetSealer
from .core.verifier import verify_scalar_claim
from .llm.nebius import NemotronClient
from .orchestrator import run_reclaim_case
from .sandbox.contree import ContreeBlindExecutor, ContreeRuntime, ContreeWorkspaceTools
from .setup import prepare_reclaim_workspace


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


def run_live_case(
    *,
    case_path: Path,
    output_dir: Path,
    profile: str | None,
    image: str,
    timeout_seconds: float,
) -> None:
    case = load_reclaim_case(case_path)
    client = NemotronClient.from_env()
    output_dir.mkdir(parents=True, exist_ok=True)

    with ContreeRuntime(profile=profile, image=image) as runtime:
        setup_tools = ContreeWorkspaceTools(runtime.session, network_enabled=True)
        setup = prepare_reclaim_workspace(
            case,
            setup_tools,
            evidence_path=output_dir / "setup.json",
        )
        blind_tools = ContreeWorkspaceTools(runtime.session, network_enabled=False)
        executor = ContreeBlindExecutor(client, blind_tools)
        run = run_reclaim_case(
            case_path=case_path,
            workspace=Path("/workspace"),
            output_dir=output_dir,
            executor=executor,
            sealer=TargetSealer(),
            timeout_seconds=timeout_seconds,
            repo_commit=setup.commit,
        )

    print(
        json.dumps(
            {
                "paper_id": run.case.paper_id,
                "repo_commit": setup.commit,
                "raw_observed_value": run.raw_observed_value,
                "normalized_observed_value": run.normalized_observed_value,
                "verdict": run.certificate.verdict.value,
                "findings": run.certificate.auditor_findings,
                "evidence": str(output_dir / "evidence.json"),
                "transcript": str(run.transcript_path),
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evidence-first replication prototype")
    parser.add_argument("--demo", action="store_true", help="run an offline trust-boundary smoke test")
    parser.add_argument("--output", type=Path, default=Path("evidence.json"))
    parser.add_argument("--case", type=Path, help="run one benchmark case manifest in ConTree")
    parser.add_argument("--output-dir", type=Path, default=Path("runs/live"))
    parser.add_argument("--contree-profile", default=os.environ.get("CONTREE_PROFILE"))
    parser.add_argument(
        "--contree-image",
        default=os.environ.get("CONTREE_IMAGE", "docker://docker.io/python:3.11"),
    )
    parser.add_argument("--timeout", type=float, default=3600.0)
    args = parser.parse_args()

    if args.demo:
        demo(args.output)
        return
    if args.case:
        run_live_case(
            case_path=args.case,
            output_dir=args.output_dir,
            profile=args.contree_profile,
            image=args.contree_image,
            timeout_seconds=args.timeout,
        )
        return
    parser.error("choose --demo or --case <manifest>")


if __name__ == "__main__":
    main()
