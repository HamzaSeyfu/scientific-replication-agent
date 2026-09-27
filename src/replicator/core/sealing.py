from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os

from .models import SealedTarget


class TargetSealer:
    """Keeps the published result out of the blind executor's context.

    This is intentionally simple for the first vertical slice: authenticated
    encoding using an HMAC-derived stream. The security boundary is architectural,
    not cryptographic secrecy from a hostile local process. A production version
    should move unsealing into a separate service / trust boundary.
    """

    def __init__(self, secret: bytes | None = None) -> None:
        self._secret = secret or os.urandom(32)

    def seal(self, claim_id: str, published_value: float) -> SealedTarget:
        payload = json.dumps(
            {"claim_id": claim_id, "published_value": published_value},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        keystream = hashlib.sha256(self._secret + claim_id.encode()).digest()
        cipher = bytes(b ^ keystream[i % len(keystream)] for i, b in enumerate(payload))
        tag = hmac.new(self._secret, cipher, hashlib.sha256).hexdigest()
        packed = base64.urlsafe_b64encode(cipher).decode()
        digest = hashlib.sha256(payload).hexdigest()
        return SealedTarget(claim_id=claim_id, digest=f"{digest}:{tag}", encrypted_payload=packed)

    def unseal(self, sealed: SealedTarget) -> float:
        cipher = base64.urlsafe_b64decode(sealed.encrypted_payload.encode())
        digest, expected_tag = sealed.digest.split(":", 1)
        actual_tag = hmac.new(self._secret, cipher, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_tag, actual_tag):
            raise ValueError("sealed target integrity check failed")
        keystream = hashlib.sha256(self._secret + sealed.claim_id.encode()).digest()
        payload = bytes(b ^ keystream[i % len(keystream)] for i, b in enumerate(cipher))
        if hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError("sealed target digest mismatch")
        data = json.loads(payload)
        if data["claim_id"] != sealed.claim_id:
            raise ValueError("sealed target claim mismatch")
        return float(data["published_value"])
