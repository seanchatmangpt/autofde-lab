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

from autofde_lab.simulation.fortune5_safe.model import stable_digest

from .catalog import is_admitted
from .matrix import EVIDENCE_CEILING, EpisodeRecord, ProvenanceRefused, receipt_body
from .ocel import episode_log, log_sha256

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


def key_provenance(signer: AttestationSigner) -> dict[str, object]:
    """Which key sealed a ledger, and whether that key can attest the writer.

    A FIXTURE key is published in source: its ledger proves chain integrity and
    replay only. An env key is operator-held: its ledger also binds the writer.
    """
    fixture = signer.key_id == FIXTURE_KEY_ID
    return {
        "key_id": signer.key_id,
        "key_kind": "fixture" if fixture else "env",
        "attests_writer": not fixture,
    }


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


def admit_for_seal(episode: EpisodeRecord, ocel_sha256: str) -> None:
    """Refuse an episode whose origin or digests do not recompute.

    The catalog digest must have been admitted by ``load_catalog`` in-process,
    the receipt's ``episode_digest`` must recompute from its own fields, the
    receipt must carry authority NONE, and the supplied OCEL digest must equal
    the digest of the episode's own deterministic log.
    """
    r = episode.receipt
    if not is_admitted(r.catalog_sha256):
        raise ProvenanceRefused(f"catalog {r.catalog_sha256!r} was never admitted")
    if r.authority != "NONE" or r.authority_ceiling not in ("SELECT", "CONSTRUCT"):
        raise ProvenanceRefused(
            f"receipt authority {r.authority}/{r.authority_ceiling}"
        )
    expected = stable_digest(
        receipt_body(
            r.catalog_sha256, r.strategy_ordinal, r.strategy_signature, r.outcome_digest
        )
    )
    if expected != r.episode_digest:
        raise ProvenanceRefused(f"episode {episode.id} digest does not recompute")
    if ocel_sha256 != log_sha256(episode_log(episode)):
        raise ProvenanceRefused(f"episode {episode.id} OCEL digest does not recompute")


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
    admitted = list(episodes)
    for episode, ocel_sha in admitted:
        admit_for_seal(episode, ocel_sha)
    for episode, ocel_sha in admitted:
        ledger.append(attestation_for(episode, ocel_sha))
    return ledger.verify()


def verify_ledger(
    ledger_path: Path | str, *, signer: AttestationSigner | None = None
) -> LedgerVerification:
    return ProvenanceLedger(
        ledger_path, signer=signer or signer_from_env(), fsync=False
    ).verify()
