import json
from pathlib import Path

import pytest

from replicator.benchmarks.reclaim import (
    assert_target_not_in_text,
    build_blind_task,
    load_reclaim_case,
    seal_reclaim_target,
)
from replicator.core.sealing import TargetSealer


CASE = Path("benchmarks/reclaim/dev/2505.18513.json")


def test_airrep_case_builds_blind_payload_without_target():
    case = load_reclaim_case(CASE)
    payload = build_blind_task(case)
    assert "21.11" not in payload
    assert "AirRep-Flan-Small" in payload
    assert "LDS Spearman" in payload


def test_airrep_reference_is_sealed_outside_executor_payload():
    case = load_reclaim_case(CASE)
    sealer = TargetSealer(secret=b"r" * 32)
    sealed = seal_reclaim_target(case, sealer)
    assert "21.11" not in sealed.encrypted_payload
    assert sealer.unseal(sealed) == 21.11


def test_leakage_gate_rejects_reclaim_style_target_hint():
    with pytest.raises(ValueError, match="target leaked"):
        assert_target_not_in_text("Verify the LDS score is approximately 21.11.", 21.11)


def test_manifest_reference_and_blind_payload_are_distinct():
    raw = json.loads(CASE.read_text())
    assert raw["reference"]["value"] == 21.11
    assert "value" not in raw["blind_executor"]
