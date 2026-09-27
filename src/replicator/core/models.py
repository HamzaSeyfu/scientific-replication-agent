from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    REPRODUCED = "reproduced"
    PARTIAL = "partial"
    NOT_REPRODUCED = "not_reproduced"
    NOT_EVALUABLE = "not_evaluable"


@dataclass(frozen=True)
class ClaimProtocol:
    claim_id: str
    statement: str
    metric_name: str
    dataset: str | None = None
    protocol: str | None = None
    tolerance_relative: float = 0.05


@dataclass(frozen=True)
class SealedTarget:
    claim_id: str
    digest: str
    encrypted_payload: str


@dataclass
class Intervention:
    attempt: int
    kind: str
    description: str
    rationale: str
    source: str | None = None
    before: str | None = None
    after: str | None = None


@dataclass
class ExecutionEvidence:
    attempt: int
    exit_code: int
    command: str
    commit: str | None = None
    environment_digest: str | None = None
    raw_metrics: dict[str, float] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    interventions: list[Intervention] = field(default_factory=list)


@dataclass
class EvidenceCertificate:
    claim: ClaimProtocol
    observed_value: float | None
    published_value: float | None
    verdict: Verdict
    relative_error: float | None
    executions: list[ExecutionEvidence] = field(default_factory=list)
    auditor_findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
