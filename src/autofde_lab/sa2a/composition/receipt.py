"""CompositionReceipt: standalone, independently-verifiable evidence that Episode 1,
Episode 2, AND the exact subject were genuinely bound together in ONE crown run
(v26.9.17 PRD §14 item 28 / ARD §64 item 16).

Before this module, `composition_digest` (`composition/exact_subject.py`) was real but
appeared only as one field inside the combined multi-stage crown receipt
`ReleaseRun.to_receipt()` produces -- `grep -n "receipt|Receipt"
src/autofde_lab/sa2a/composition/*.py` returned zero matches before this module existed.
A field sitting inside a larger JSON blob is not itself tamper-evident: nothing bound
`composition_digest` to the SPECIFIC Episode 1 / Episode 2 receipts it was presented
alongside, so two different crown runs' `to_receipt()` outputs could in principle be
spliced together (same `composition_digest`, someone else's episode receipts) without
detection.

`CompositionReceipt` closes that gap the same way `PreparedReceipt`/`FinalReceipt`
(`brce/receipts.py`) and `AdmissionReceipt` (`admission/pipeline.py`) already do for
their own layers: a frozen dataclass whose `digest` property is a fresh,
content-addressed SHA-256 over ALL of its identity-bearing fields combined, so the
receipt itself becomes tamper-evident evidence of the binding, not merely a container
for digests computed elsewhere.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict


def _canonical_digest(payload: Dict[str, Any]) -> str:
    """Same canonical-JSON digest discipline as `ExactSubject.composition_digest`,
    `AdmissionReceipt.receipt_hash`, and `PreparedReceipt`/`FinalReceipt.digest`:
    `sort_keys` + compact separators neutralize key-order/whitespace variation so the
    digest is a function of content alone.
    """
    dumped = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CompositionReceipt:
    """Tamper-evident evidence binding one crown run's `ExactSubject` composition
    identity to the SPECIFIC Episode 1 and Episode 2 evidence it was crowned with
    (ARD §64 item 16).

    Every field here is identity-bearing (mirrors `ExactSubject.composition_digest`'s
    own docstring reasoning): `composition_receipt_digest` is sensitive to ALL of
    them, not merely a copy of `composition_digest`. Two crown runs sharing one
    sub-digest by coincidence (e.g. the same declared composition but genuinely
    different episode outcomes, or vice versa) MUST still produce different
    `composition_receipt_digest` values -- pinned by
    `tests/sa2a/composition/test_composition_receipt_chicago.py`.
    """

    receipt_id: str
    release_id: str
    composition_digest: str
    episode1_id: str
    episode1_final_receipt_digest: str
    episode1_ocel_digest: str
    episode2_id: str
    episode2_final_receipt_digest: str
    episode2_ocel_digest: str
    issued_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    @property
    def composition_receipt_digest(self) -> str:
        """A fresh, independent content-addressed digest over every field above
        combined -- the load-bearing property that makes this receipt tamper-evident
        rather than a plain container. Deliberately excludes nothing: a receipt whose
        digest ignored, say, `episode2_final_receipt_digest` could be re-issued
        against a DIFFERENT Episode 2 outcome without changing its own digest, which
        is exactly the "presented side by side, not genuinely bound" failure this
        type exists to close.
        """
        body = {
            "receipt_id": self.receipt_id,
            "release_id": self.release_id,
            "composition_digest": self.composition_digest,
            "episode1_id": self.episode1_id,
            "episode1_final_receipt_digest": self.episode1_final_receipt_digest,
            "episode1_ocel_digest": self.episode1_ocel_digest,
            "episode2_id": self.episode2_id,
            "episode2_final_receipt_digest": self.episode2_final_receipt_digest,
            "episode2_ocel_digest": self.episode2_ocel_digest,
            "issued_at_ms": self.issued_at_ms,
        }
        return _canonical_digest({"kind": "composition_receipt", "body": body})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "composition_receipt",
            "receipt_id": self.receipt_id,
            "release_id": self.release_id,
            "composition_digest": self.composition_digest,
            "episode1_id": self.episode1_id,
            "episode1_final_receipt_digest": self.episode1_final_receipt_digest,
            "episode1_ocel_digest": self.episode1_ocel_digest,
            "episode2_id": self.episode2_id,
            "episode2_final_receipt_digest": self.episode2_final_receipt_digest,
            "episode2_ocel_digest": self.episode2_ocel_digest,
            "issued_at_ms": self.issued_at_ms,
            "composition_receipt_digest": self.composition_receipt_digest,
        }


def build_composition_receipt(
    *,
    receipt_id: str,
    release_id: str,
    composition_digest: str,
    episode1_id: str,
    episode1_final_receipt_digest: str,
    episode1_ocel_digest: str,
    episode2_id: str,
    episode2_final_receipt_digest: str,
    episode2_ocel_digest: str,
) -> CompositionReceipt:
    """Construct a `CompositionReceipt` from the crown's own already-real evidence
    (`ExactSubject.composition_digest`, `Episode.final_receipt_digest`/`ocel_digest`
    for both episodes) -- a thin, explicit constructor so `ReleaseRun` never has to
    assemble the dataclass's field list inline at the call site.
    """
    return CompositionReceipt(
        receipt_id=receipt_id,
        release_id=release_id,
        composition_digest=composition_digest,
        episode1_id=episode1_id,
        episode1_final_receipt_digest=episode1_final_receipt_digest,
        episode1_ocel_digest=episode1_ocel_digest,
        episode2_id=episode2_id,
        episode2_final_receipt_digest=episode2_final_receipt_digest,
        episode2_ocel_digest=episode2_ocel_digest,
    )
