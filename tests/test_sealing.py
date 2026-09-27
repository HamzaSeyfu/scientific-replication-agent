import pytest

from replicator.core.models import SealedTarget
from replicator.core.sealing import TargetSealer


def test_sealed_target_round_trip():
    sealer = TargetSealer(secret=b"x" * 32)
    sealed = sealer.seal("claim-1", 91.4)
    assert "91.4" not in sealed.encrypted_payload
    assert sealer.unseal(sealed) == 91.4


def test_tampering_is_detected():
    sealer = TargetSealer(secret=b"x" * 32)
    sealed = sealer.seal("claim-1", 91.4)
    tampered = SealedTarget(
        claim_id=sealed.claim_id,
        digest=sealed.digest,
        encrypted_payload=sealed.encrypted_payload[:-2] + "AA",
    )
    with pytest.raises(Exception):
        sealer.unseal(tampered)
