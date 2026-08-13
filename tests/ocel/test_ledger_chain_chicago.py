# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for `autofde_lab.ocel.ledger` —
`docs/jira/v26.8.12/cloud-cert-wbpr-prd.md` FR3.

Real `OcelLog`/`OcelObject` throughout (the same real classes production
code uses, per Correction 1's finding that this module has no prior
implementation to reuse) — no mocks. Every assertion is on real, computed
state: real SHA-256 digests, a real chain-integrity re-derivation, real
`BLOCKED:<reason>` entries appended alongside `ALIVE` ones.
"""

from __future__ import annotations

from autofde_lab.ocel.ledger import CERTIFICATION_CLAIM_TYPE, CertificationLedger
from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import OcelObject


def _episode_log(episode_id: str) -> OcelLog:
    """A small, real, synthetic episode log — matches the real
    materialize/act/verify shape closely enough to exercise the ledger
    without needing a live trial to have run (per this pass's scope: FR3
    unit-tested against synthetic fixtures)."""
    return OcelLog.new(objects=[OcelObject(episode_id, "episode")]).append_event(
        f"{episode_id}:verify", "verify", [episode_id], timestamp_ns=1
    )


def test_first_append_chains_from_genesis() -> None:
    ledger = CertificationLedger.empty()

    ledger = ledger.append(
        domain="azuregoat_privesc",
        tier="associate",
        standing="ALIVE",
        episode_log=_episode_log("ep-1"),
        episode_object_id="ep-1",
        claim_id="claim-1",
    )

    assert len(ledger.entries) == 1
    entry = ledger.entries[0]
    assert entry.prev_digest == "0" * 64
    assert entry.standing == "ALIVE"
    # The certification_claim object is real, present in the entry's own log.
    claim_objects = [o for o in entry.log.objects if o.object_type == CERTIFICATION_CLAIM_TYPE]
    assert len(claim_objects) == 1
    assert claim_objects[0].id == "claim-1"


def test_second_entry_chains_to_first_entrys_real_digest() -> None:
    ledger = CertificationLedger.empty().append(
        domain="azuregoat_privesc",
        tier="associate",
        standing="ALIVE",
        episode_log=_episode_log("ep-1"),
        episode_object_id="ep-1",
        claim_id="claim-1",
    )
    first_digest = ledger.entries[0].entry_digest

    ledger = ledger.append(
        domain="terragoat",
        tier="associate",
        standing="ALIVE",
        episode_log=_episode_log("ep-2"),
        episode_object_id="ep-2",
        claim_id="claim-2",
    )

    assert ledger.entries[1].prev_digest == first_digest


def test_blocked_trial_is_appended_with_the_same_rigor_as_alive() -> None:
    """FR3: 'a failed or blocked trial is logged with the same rigor as a
    pass... never silently dropped.'"""
    ledger = CertificationLedger.empty().append(
        domain="cloudgoat_iam_privesc",
        tier="associate",
        standing="BLOCKED:NO_ACTUATION_BRIDGE",
        episode_log=_episode_log("ep-3"),
        episode_object_id="ep-3",
        claim_id="claim-3",
    )

    assert len(ledger.entries) == 1
    assert ledger.entries[0].standing == "BLOCKED:NO_ACTUATION_BRIDGE"
    passing, detail = ledger.verify_chain()
    assert passing is True, detail


def test_verify_chain_detects_a_tampered_prev_digest() -> None:
    ledger = CertificationLedger.empty().append(
        domain="d1",
        tier="associate",
        standing="ALIVE",
        episode_log=_episode_log("ep-1"),
        episode_object_id="ep-1",
        claim_id="claim-1",
    ).append(
        domain="d2",
        tier="associate",
        standing="ALIVE",
        episode_log=_episode_log("ep-2"),
        episode_object_id="ep-2",
        claim_id="claim-2",
    )

    # Tamper: rebuild the second entry with a fabricated prev_digest,
    # simulating a chain edited out-of-band.
    from dataclasses import replace

    tampered_second = replace(ledger.entries[1], prev_digest="f" * 64)
    tampered_ledger = CertificationLedger((ledger.entries[0], tampered_second))

    passing, detail = tampered_ledger.verify_chain()

    assert passing is False
    assert "entry 1" in detail


def test_entries_for_domain_filters_real_entries() -> None:
    ledger = (
        CertificationLedger.empty()
        .append(
            domain="azuregoat_privesc",
            tier="associate",
            standing="ALIVE",
            episode_log=_episode_log("ep-1"),
            episode_object_id="ep-1",
            claim_id="claim-1",
        )
        .append(
            domain="terragoat",
            tier="associate",
            standing="ALIVE",
            episode_log=_episode_log("ep-2"),
            episode_object_id="ep-2",
            claim_id="claim-2",
        )
    )

    azuregoat_entries = ledger.entries_for_domain("azuregoat_privesc")

    assert len(azuregoat_entries) == 1
    assert azuregoat_entries[0].claim_id == "claim-1"
