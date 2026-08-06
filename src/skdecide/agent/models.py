# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Envelope types for the persistent agent runtime.

``AgentOutcome`` is a **new** envelope. It deliberately does not widen
:class:`skdecide.fabric.models.DecisionResult`, which is structurally committed
to a total order (``steps`` indexed by ``int``) and is consumed by
``service.py``/``cli.py``/``mcp.py``/``a2a.py``/``cache.py``. A ``DecisionResult``
appears here only as *per-epoch evidence*, contained, never extended.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from skdecide.fabric.canonical import sha256
from skdecide.fabric.models import DecisionResult
from skdecide.powl.identity import OccurrenceKey

__all__ = ["EpochStanding", "EpochReceipt", "AgentOutcome"]

EPOCH_RECEIPT_SCHEMA = "skdecide.agent.epoch_receipt/1"
AGENT_OUTCOME_SCHEMA = "skdecide.agent.outcome/1"


class EpochStanding(StrEnum):
    """Standing of one decision epoch, in the repo's standing vocabulary."""

    ALIVE = "ALIVE"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class EpochReceipt:
    """Evidence for a single epoch. Descriptive only; carries no authority."""

    schema: str
    session_id: str
    epoch_id: str
    model_sha256: str
    bound_sha256: str
    standing: EpochStanding
    blocked_reason: str | None
    steps: int
    trace: tuple[str, ...]
    occurrences: tuple[OccurrenceKey, ...]
    marking_sha256: str
    supersedes: tuple[str, ...]
    preserves: tuple[str, ...]
    evidence: DecisionResult | None
    claim_ceiling: str
    receipt_sha256: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["standing"] = self.standing.value
        payload["evidence"] = (
            self.evidence.as_dict() if self.evidence is not None else None
        )
        return payload


@dataclass(frozen=True, slots=True)
class AgentOutcome:
    """The whole-session envelope: an append-only stack of epoch receipts."""

    schema: str
    session_id: str
    epochs: tuple[EpochReceipt, ...]
    standing: EpochStanding
    blocked_reason: str | None
    claim_ceiling: str
    input_sha256: str
    lineage_sha256: str
    receipt_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "session_id": self.session_id,
            "epochs": [e.as_dict() for e in self.epochs],
            "standing": self.standing.value,
            "blocked_reason": self.blocked_reason,
            "claim_ceiling": self.claim_ceiling,
            "input_sha256": self.input_sha256,
            "lineage_sha256": self.lineage_sha256,
            "receipt_sha256": self.receipt_sha256,
        }

    def digest(self) -> str:
        """Content hash over the full envelope."""
        return sha256(self.as_dict())
