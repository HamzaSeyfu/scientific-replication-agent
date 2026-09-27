from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from .models import EvidenceCertificate, ExecutionEvidence


def environment_digest(lock_material: str) -> str:
    return hashlib.sha256(lock_material.encode()).hexdigest()


def write_execution(path: Path, evidence: ExecutionEvidence) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(evidence), indent=2, sort_keys=True), encoding="utf-8")
    return path


def write_certificate(path: Path, certificate: EvidenceCertificate) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(certificate.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return path
