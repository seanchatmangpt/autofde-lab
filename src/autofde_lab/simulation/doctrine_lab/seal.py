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
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from autofde_lab._cache.provenance import (
    AttestationSigner,
    CacheAttestation,
    LedgerVerification,
    ProvenanceLedger,
)
from autofde_lab.simulation.fortune5_safe.model import stable_digest

from .catalog import CATALOG_SHA256, admitted_catalog
from .matrix import (
    EVIDENCE_CEILING,
    RECEIPT_SCHEMA,
    EpisodeRecord,
    ProvenanceRefused,
    receipt_body,
    run_strategy_episode,
)
from .ocel import episode_log, log_sha256
from .world import world_by_id

KEY_ENV = "AUTOFDE_DOCTRINE_LAB_KEY"
FIXTURE_KEY_ID = "doctrine-lab-fixture-v1"
FIXTURE_KEY = hashlib.sha256(
    b"autofde-lab doctrine-lab FIXTURE seal key v1 (not a secret)"
).digest()
NAMESPACE = "autofde-lab.simulation.doctrine-lab"
OBSERVED_AT = 0.0
MIN_KEY_BYTES = 32
AUTHORITY = "NONE"
CEILINGS = frozenset({"SELECT", "CONSTRUCT"})


class SealKeyRefused(ValueError):
    """``AUTOFDE_DOCTRINE_LAB_KEY`` is not hex or is shorter than 32 bytes."""


def signer_from_env(env: Mapping[str, str] | None = None) -> AttestationSigner:
    env = os.environ if env is None else env
    raw = env.get(KEY_ENV)
    if raw:
        try:
            key = bytes.fromhex(raw)
        except ValueError as exc:
            raise SealKeyRefused(f"{KEY_ENV} is not hex: {exc}") from None
        if len(key) < MIN_KEY_BYTES:
            raise SealKeyRefused(
                f"{KEY_ENV} carries {len(key)} bytes; at least {MIN_KEY_BYTES} required"
            )
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


def outcome_digest_of(episode: EpisodeRecord) -> str:
    """Recompute the receipt's ``outcome_digest`` from the episode's own rounds."""
    r = episode.receipt
    return stable_digest(
        {
            "policy": r.policy_digest,
            "world": episode.world.id,
            "seed": episode.seed,
            "rounds": tuple(rr.receipt.replay_digest for rr in episode.rounds),
            "opponent": stable_digest([rr.move for rr in episode.rounds]),
        }
    )


def admit_for_seal(episode: EpisodeRecord, ocel_sha256: str) -> None:
    """Refuse an episode whose origin, rounds or digests do not recompute.

    The catalog digest must have been admitted by ``load_catalog`` in-process AND
    be the pinned vendored ``CATALOG_SHA256`` (the catalog ``verify_run`` reloads;
    a re-pinned catalog admitted from another path cannot be sealed). The
    receipt's ordinal must resolve, in that catalog, to an operationalized
    Strategy whose signature and policy digest the receipt carries. The receipt
    must carry authority NONE with a SELECT/CONSTRUCT ceiling and the lab schema
    and evidence ceiling; its world/seed/rounds must be the episode's; every
    round's engine receipt must carry the admitted policy digest; and the episode
    is RE-EXECUTED from (admitted Strategy, world, seed, rounds) under the lab
    config: rounds, opponent moves and the whole receipt must be identical to the
    re-execution. A relabelled episode that ran a foreign composition therefore
    cannot be sealed even with every digest recomputed. Finally the supplied OCEL
    digest must equal the digest of the episode's own log.
    """
    r = episode.receipt
    catalog = admitted_catalog(r.catalog_sha256)
    if catalog is None:
        raise ProvenanceRefused(f"catalog {r.catalog_sha256!r} was never admitted")
    if r.catalog_sha256 != CATALOG_SHA256:
        raise ProvenanceRefused(
            f"catalog {r.catalog_sha256!r} is not the pinned catalog {CATALOG_SHA256}"
        )
    if r.authority != AUTHORITY or r.authority_ceiling not in CEILINGS:
        raise ProvenanceRefused(
            f"receipt authority {r.authority}/{r.authority_ceiling}"
        )
    if r.schema != RECEIPT_SCHEMA or r.evidence_ceiling != EVIDENCE_CEILING:
        raise ProvenanceRefused(
            f"receipt schema/ceiling {r.schema}/{r.evidence_ceiling} not the lab's"
        )
    try:
        admitted = catalog.get(r.strategy_ordinal)
    except KeyError:
        raise ProvenanceRefused(
            f"ordinal {r.strategy_ordinal} is not in admitted catalog"
        ) from None
    if admitted.status != "operationalized":
        raise ProvenanceRefused(f"ordinal {r.strategy_ordinal} is a stub")
    if r.strategy_signature != admitted.signature:
        raise ProvenanceRefused(
            f"episode {episode.id} signature {r.strategy_signature!r} is not the "
            f"admitted catalog's {admitted.signature!r} for ordinal {admitted.ordinal}"
        )
    if episode.strategy != admitted or r.policy_digest != admitted.policy.digest:
        raise ProvenanceRefused(
            f"episode {episode.id} strategy/policy is not the admitted catalog's"
        )
    if (r.world_id, r.seed, r.rounds) != (
        episode.world.id,
        episode.seed,
        len(episode.rounds),
    ):
        raise ProvenanceRefused(f"episode {episode.id} world/seed/rounds mismatch")
    foreign = [
        rr.round
        for rr in episode.rounds
        if rr.receipt.policy_digest != admitted.policy.digest
    ]
    if foreign:
        raise ProvenanceRefused(
            f"episode {episode.id} rounds {foreign} ran a policy that is not the "
            f"admitted catalog's for ordinal {admitted.ordinal}"
        )
    if outcome_digest_of(episode) != r.outcome_digest:
        raise ProvenanceRefused(f"episode {episode.id} outcome does not recompute")
    expected = stable_digest(
        receipt_body(
            r.catalog_sha256, r.strategy_ordinal, r.strategy_signature, r.outcome_digest
        )
    )
    if expected != r.episode_digest:
        raise ProvenanceRefused(f"episode {episode.id} digest does not recompute")
    try:
        world = world_by_id(r.world_id)
        rerun = run_strategy_episode(
            r.seed, admitted, world, catalog_sha256=r.catalog_sha256, rounds=r.rounds
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise ProvenanceRefused(
            f"episode {episode.id} cannot be re-executed: {exc}"
        ) from None
    if episode.world != world or episode.rounds != rerun.rounds:
        raise ProvenanceRefused(
            f"episode {episode.id} rounds differ from re-execution of the admitted "
            f"strategy {admitted.id}"
        )
    if r != rerun.receipt:
        raise ProvenanceRefused(
            f"episode {episode.id} receipt differs from re-execution"
        )
    if ocel_sha256 != log_sha256(episode_log(episode)):
        raise ProvenanceRefused(f"episode {episode.id} OCEL digest does not recompute")


def _sealed_subjects(ledger_path: Path) -> set[str]:
    if not ledger_path.exists():
        return set()
    subjects: set[str] = set()
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            subjects.add(str(row["signed_attestation"]["attestation"]["subject_id"]))
    return subjects


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
    seen = _sealed_subjects(Path(ledger_path))
    for episode, ocel_sha in admitted:
        admit_for_seal(episode, ocel_sha)
        subject = f"doctrine-lab:{episode.id}"
        if subject in seen:
            raise ProvenanceRefused(f"duplicate delivery of {subject}")
        seen.add(subject)
    for episode, ocel_sha in admitted:
        ledger.append(attestation_for(episode, ocel_sha))
    return ledger.verify()


def verify_ledger(
    ledger_path: Path | str, *, signer: AttestationSigner | None = None
) -> LedgerVerification:
    return ProvenanceLedger(
        ledger_path, signer=signer or signer_from_env(), fsync=False
    ).verify()


@dataclass(frozen=True)
class ReportSeal:
    """Keyed binding of report body digest to the ledger anchor.

    ``report_digest`` alone is an unkeyed sha256 that anyone who edits the
    report can recompute; the seal is an HMAC under the ledger key over
    (report_digest, records, tail_digest). Under the FIXTURE key it proves
    consistency only (``attests_writer`` False); under an env key it binds the
    writer.
    """

    report_digest: str
    records: int
    tail_digest: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": NAMESPACE + ".report",
            "report_digest": self.report_digest,
            "records": self.records,
            "tail_digest": self.tail_digest,
        }


def report_signature(
    signer: AttestationSigner,
    report_digest: str,
    records: int,
    tail_digest: str | None,
) -> str:
    return signer.sign(ReportSeal(report_digest, records, tail_digest)).signature
