# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The chained certification ledger — `docs/jira/v26.8.12/cloud-cert-wbpr-
prd.md` FR3 and the ARD's `certification_claim` data-model addition.

Per Correction 1: `scripts/ocel_standing.py` does not exist anywhere in this
repo — this module is net-new, not an extension of a prior mechanism. It is
built on the real, already-tested `OcelLog` (`autofde_lab.ocel.log`) rather
than reimplementing OCEL append/digest logic: each ledger entry wraps one
real episode's `OcelLog`, with a `certification_claim` object added (per the
PRD's data-model addition) and a `certifies` E2O relationship pointing at
the episode's own object.

A `BLOCKED:<reason>` trial is appended with exactly the same rigor as an
`ALIVE` one — FR3's "never silently dropped" requirement — by chaining it
into the same digest sequence rather than being filtered out before
appending.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import OcelAttribute, OcelAttributeValue, OcelObject

__all__ = ["LedgerEntry", "CertificationLedger", "CERTIFICATION_CLAIM_TYPE", "CERTIFIES_QUALIFIER"]

CERTIFICATION_CLAIM_TYPE = "certification_claim"
CERTIFIES_QUALIFIER = "certifies"

_GENESIS_DIGEST = "0" * 64


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One real, chained ledger entry — a certification claim over one
    episode's real `OcelLog`, plus the hash link to the entry before it."""

    index: int
    domain: str
    tier: str
    standing: str
    """A `standing-law.md` value — `ALIVE`, `PARTIAL_ALIVE`, or
    `BLOCKED:<reason>` (never a bare boolean, never silently dropped when
    not ALIVE, per FR3)."""
    claim_id: str
    episode_object_id: str
    prev_digest: str
    log: OcelLog
    """The real episode `OcelLog`, with this entry's `certification_claim`
    object and `certifies` relationship already added."""

    @property
    def entry_digest(self) -> str:
        """Chains `prev_digest` into the content digest — changing any
        prior entry changes every digest after it, the same guarantee
        `OcelLog.digest()` already gives within one log, extended across
        the whole ledger."""
        payload = f"{self.prev_digest}:{self.log.digest()}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class CertificationLedger:
    """An append-only sequence of `LedgerEntry`. Frozen, like `OcelLog`:
    every mutator returns a new ledger."""

    entries: tuple[LedgerEntry, ...] = field(default_factory=tuple)

    @classmethod
    def empty(cls) -> "CertificationLedger":
        return cls(())

    def append(
        self,
        *,
        domain: str,
        tier: str,
        standing: str,
        episode_log: OcelLog,
        episode_object_id: str,
        claim_id: str,
        timestamp_ns: int = 0,
    ) -> "CertificationLedger":
        """Append one real trial's outcome — `ALIVE` or `BLOCKED:<reason>`,
        with identical rigor. Adds the `certification_claim` object and a
        `certify` event linking it to `episode_object_id` via the
        `certifies` qualifier, per the PRD ARD's data-model addition.
        """
        claim_object = OcelObject(
            claim_id,
            CERTIFICATION_CLAIM_TYPE,
            (
                OcelAttribute("domain", OcelAttributeValue.string(domain)),
                OcelAttribute("tier", OcelAttributeValue.string(tier)),
                OcelAttribute("standing", OcelAttributeValue.string(standing)),
            ),
        )
        log_with_claim = episode_log.with_objects(claim_object).append_event(
            f"{claim_id}:certify",
            "certify",
            [
                (episode_object_id, CERTIFIES_QUALIFIER),
                claim_id,
            ],
            timestamp_ns=timestamp_ns,
            attributes={
                "domain": OcelAttributeValue.string(domain),
                "tier": OcelAttributeValue.string(tier),
                "standing": OcelAttributeValue.string(standing),
            },
        )

        prev_digest = self.entries[-1].entry_digest if self.entries else _GENESIS_DIGEST
        entry = LedgerEntry(
            index=len(self.entries),
            domain=domain,
            tier=tier,
            standing=standing,
            claim_id=claim_id,
            episode_object_id=episode_object_id,
            prev_digest=prev_digest,
            log=log_with_claim,
        )
        return CertificationLedger(self.entries + (entry,))

    def verify_chain(self) -> tuple[bool, str]:
        """Re-derive every entry's `prev_digest` link from scratch and
        confirm it matches what's stored — real chain-integrity
        verification, not a self-report. Returns `(True, "")` on success,
        `(False, detail)` naming the exact first broken link.
        """
        expected_prev = _GENESIS_DIGEST
        for entry in self.entries:
            if entry.prev_digest != expected_prev:
                return False, (
                    f"entry {entry.index} ({entry.domain}/{entry.tier}): "
                    f"prev_digest {entry.prev_digest!r} != expected {expected_prev!r}"
                )
            expected_prev = entry.entry_digest
        return True, ""

    def entries_for_domain(self, domain: str) -> tuple[LedgerEntry, ...]:
        return tuple(e for e in self.entries if e.domain == domain)
