"""Novelty Ingestion for UNKNOWN Candidate Frontier (§38, §64).

Translates production typed refusals (REFUSED_NOVELTY, REFUSED_NO_GRANT, UNKNOWN)
into structured UnknownCandidate items for bounded Lab exploration.
Enforces that runtime novelty never executes ambiently in production;
it is refused, packaged, and routed to the Lab.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from autofde_lab.sa2a.brce.receipts import FinalReceipt, TerminalReceiptState
from autofde_lab.sa2a.unknown.allocator import UnknownCandidate


@dataclass(frozen=True, slots=True)
class NoveltyPacket:
    """Structured representation of unhandled production novelty."""

    packet_id: str
    refusal_code: str
    trigger_action_iri: str
    target_resource_iri: str
    observed_state_ttl: str
    parameters: Mapping[str, Any]
    prior_receipt_digest: str
    entropy_estimate: float = 1.0
    estimated_cost: float = 10.0


class NoveltyIngestionGateway:
    """Ingests production refusal receipts and transforms them into Lab candidates."""

    def ingest_refusal_receipt(
        self,
        receipt: FinalReceipt,
        *,
        action_iri: str = "",
        target_resource: str = "",
        observed_state_ttl: str = "",
        parameters: Mapping[str, Any] | None = None,
    ) -> UnknownCandidate:
        """Convert a refused production receipt into an UnknownCandidate for Lab exploration."""
        if receipt.state != TerminalReceiptState.REFUSED:
            raise ValueError(
                f"Only REFUSED receipts represent novelty needing Lab exploration. Got {receipt.state.value}"
            )

        refusal_code = receipt.refusal_code or "UNKNOWN_REFUSAL"
        param_dict = dict(parameters or {})
        if receipt.evidence:
            param_dict.update(receipt.evidence)

        # Compute deterministic packet ID
        payload = json.dumps(
            {
                "receipt_id": receipt.receipt_id,
                "refusal_code": refusal_code,
                "action": action_iri,
                "target": target_resource,
                "state": observed_state_ttl,
                "params": dict(sorted(param_dict.items())),
            },
            sort_keys=True,
        )
        packet_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        candidate_id = f"novelty-{packet_hash[:12]}"

        # Higher entropy estimate for unclassified/un-granted actions
        entropy = (
            1.5 if refusal_code in ("REFUSED_NO_GRANT", "REFUSED_NOVELTY") else 1.0
        )

        return UnknownCandidate(
            item_id=candidate_id,
            description=f"Novelty [{refusal_code}]: action={action_iri} target={target_resource} reason={receipt.reason}",
            option_entropy=entropy,
            estimated_cost=15.0,
            historical_yield=1.0,
            metadata={
                "receipt_id": receipt.receipt_id,
                "refusal_code": refusal_code,
                "action_iri": action_iri,
                "target_resource_iri": target_resource,
                "observed_state_ttl": observed_state_ttl,
                "parameters": param_dict,
                "prepared_receipt_digest": receipt.prepared_receipt_digest,
            },
        )
