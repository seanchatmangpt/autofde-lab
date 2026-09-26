"""Seal doctrine-lab episodes into the append-only ProvenanceLedger.

Chain per episode: fortune5_safe SimulationReceipt(s) -> DoctrineReceipt ->
CacheAttestation -> ProvenanceLedger.append (HMAC-SHA256, hash chain). The key
comes from ``AUTOFDE_DOCTRINE_LAB_KEY`` (hex, >= 32 bytes) or, absent that, a
deterministic FIXTURE key that is explicitly not a secret: a fixture-keyed ledger
proves chain integrity and replay, not who wrote it. ``observed_at`` is pinned to
0.0 so ledger bytes are a pure function of the episodes.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable, Mapping

from autofde_lab._cache.provenance import (
    AttestationSigner,
    CacheAttestation,
    LedgerVerification,
    ProvenanceLedger,
)

from .matrix import EVIDENCE_CEILING, EpisodeRecord

KEY_ENV = "AUTOFDE_DOCTRINE_LAB_KEY"
FIXTURE_KEY_ID = "doctrine-lab-fixture-v1"
FIXTURE_KEY = hashlib.sha256(
    b"autofde-lab doctrine-lab FIXTURE seal key v1 (not a secret)"
).digest()
NAMESPACE = "autofde-lab.simulation.doctrine-lab"
OBSERVED_AT = 0.0


def signer_from_env(env: Mapping[str, str] | None = None) -> AttestationSigner:
    env = os.environ if env is None else env
    raw = env.get(KEY_ENV)
    if raw:
        key = bytes.fromhex(raw)
        key_id = "doctrine-lab-env-" + hashlib.sha256(key).hexdigest()[:12]
        return AttestationSigner(key, key_id=key_id)
    return AttestationSigner(FIXTURE_KEY, key_id=FIXTURE_KEY_ID)


def attestation_for(episode: EpisodeRecord, ocel_sha256: str) -> CacheAttestation:
    r = episode.receipt
    return CacheAttestation(
        subject_id=f"doctrine-lab:{episode.id}",
        namespace=NAMESPACE,
        method="fortune5_safe.engine.run_episode x rounds",
        key_digest=r.outcome_digest,
        value_digest=r.episode_digest,
        disposition=r.standing,
        policy_digest=r.policy_digest,
        release_id=f"catalog:{r.catalog_sha256}",
        model_fingerprint=episode.rounds[0].receipt.topology_digest,
        data_fingerprint=f"ocel:{ocel_sha256}",
        rollout_reason=EVIDENCE_CEILING,
        rollout_cohort=None,
        observed_at=OBSERVED_AT,
        owner=f"authority={r.authority};ceiling={r.authority_ceiling}",
    )


def seal_episodes(
    episodes: Iterable[tuple[EpisodeRecord, str]],
    ledger_path: Path | str,
    *,
    signer: AttestationSigner | None = None,
) -> LedgerVerification:
    """Append one attestation per (episode, ocel_sha256); return the verification."""
    ledger = ProvenanceLedger(
        ledger_path, signer=signer or signer_from_env(), fsync=False
    )
    for episode, ocel_sha in episodes:
        ledger.append(attestation_for(episode, ocel_sha))
    return ledger.verify()


def verify_ledger(
    ledger_path: Path | str, *, signer: AttestationSigner | None = None
) -> LedgerVerification:
    return ProvenanceLedger(
        ledger_path, signer=signer or signer_from_env(), fsync=False
    ).verify()
