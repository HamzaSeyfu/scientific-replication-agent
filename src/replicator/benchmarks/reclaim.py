from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from ..core.models import ClaimProtocol, SealedTarget
from ..core.sealing import TargetSealer


@dataclass(frozen=True)
class ReclaimCase:
    paper_id: str
    tier: str
    central_claim: str
    metric: str
    scope: str
    match_bar_kind: str
    published_value: float
    tolerance_relative: float
    blind_task: str
    repo_url: str
    model_id: str | None = None
    dataset_id: str | None = None
    benchmark: str | None = None
    source_url: str | None = None
    result_regex: str | None = None
    observed_scale: float = 1.0

    @property
    def claim_protocol(self) -> ClaimProtocol:
        return ClaimProtocol(
            claim_id=f"reclaim-{self.paper_id}",
            statement=self.central_claim,
            metric_name=self.metric,
            dataset=self.dataset_id,
            protocol=self.blind_task,
            tolerance_relative=self.tolerance_relative,
        )


def load_reclaim_case(path: str | Path) -> ReclaimCase:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ref = data["reference"]
    executor = data["blind_executor"]
    case = ReclaimCase(
        paper_id=str(data["paper_id"]),
        tier=str(data["tier"]),
        central_claim=str(data["central_claim"]),
        metric=str(ref["metric"]),
        scope=str(ref["scope"]),
        match_bar_kind=str(ref["match_bar_kind"]),
        published_value=float(ref["value"]),
        tolerance_relative=float(ref.get("tolerance_relative", 0.05)),
        blind_task=str(executor["task"]),
        repo_url=str(executor["repo_url"]),
        model_id=executor.get("model_id"),
        dataset_id=executor.get("dataset_id"),
        benchmark=executor.get("benchmark"),
        source_url=data.get("source_url"),
        result_regex=(data.get("result_parser") or {}).get("regex"),
        observed_scale=float((data.get("result_parser") or {}).get("scale", 1.0)),
    )
    assert_target_not_in_text(case.blind_task, case.published_value)
    return case


def seal_reclaim_target(case: ReclaimCase, sealer: TargetSealer) -> SealedTarget:
    return sealer.seal(case.claim_protocol.claim_id, case.published_value)


def build_blind_task(case: ReclaimCase) -> str:
    """Return executor instructions with no published answer in the payload."""
    task = case.blind_task.strip()
    assert_target_not_in_text(task, case.published_value)
    return task


def known_value_strings(value: float) -> set[str]:
    """Conservative textual variants used by the pre-flight leakage gate.

    This is a guardrail, not the full security boundary. The production executor
    must also run in an isolated workspace with target-bearing sources withheld
    or accessed only through a redacting broker.
    """
    candidates = {
        str(value),
        f"{value:g}",
        f"{value:.1f}",
        f"{value:.2f}",
        f"{value:.3f}",
        f"{value:.4f}",
    }
    if math.isfinite(value):
        candidates |= {f"{v}%" for v in list(candidates)}
    return {x for x in candidates if x and x not in {"0", "0.0", "1", "1.0"}}


def assert_target_not_in_text(text: str, value: float) -> None:
    normalized = re.sub(r"\s+", " ", text).lower()
    leaks = sorted(token for token in known_value_strings(value) if token.lower() in normalized)
    if leaks:
        raise ValueError(f"published target leaked into blind executor payload: {leaks}")


def parse_observed_metric(case: ReclaimCase, text: str) -> tuple[float, float]:
    """Extract a raw metric from execution output and normalize its published unit.

    Returns ``(raw_value, normalized_value)``. The scale is verifier-side
    metadata and is never needed by the blind worker.
    """
    if not case.result_regex:
        raise ValueError(f"no result parser configured for {case.paper_id}")
    match = re.search(case.result_regex, text, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"metric not found in execution output for {case.paper_id}")
    raw = float(match.group(1))
    return raw, raw * case.observed_scale
