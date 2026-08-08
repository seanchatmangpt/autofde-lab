# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Branchless, typed-evidence Level 4 crown standing.

`crown_factor.py` scored the acceptance equation as a conjunction of seven
independently-constructed booleans-with-provenance. That representation is
kept, unchanged, as a read-only compatibility shim over legacy scoreboard
rows (see `conjunction_from_row`) -- but it is no longer the live
construction path. The live path stops constructing seven separate factors
whose caller was trusted to assemble consistently, and instead runs ONE
real evidence chain (`standing_from_episode`) that can only ever terminate
in one of five typed outcomes:

* :class:`AliveEvidence` -- every real check in the chain (schema, replay
  conformance, replay validity, receipted postcondition) produced positive
  evidence.
* :class:`UnknownEvidence` -- the chain stopped at a named point because a
  check failed or its precondition (a postcondition reference, a non-empty
  receipt list) was absent.
* :class:`RefusedEvidence` / :class:`BlockedEvidence` / :class:`UnsupportedEvidence`
  -- typed non-outcomes for call sites that need to report a refusal,
  external blocker, or missing capability without going through the episode
  chain at all (mirrors `CrownFactor.refused/.blocked/.unsupported`).

None of the five variants defines ``__bool__``: there is no boolean
shortcut standing in for "is this ALIVE?" -- callers must ``match`` on the
type, exactly as `CrownFactor.holds` denies `if factor:` a plausible verdict.

See `.claude/rules/absence-is-not-evidence.md` and `crown_factor.py`'s own
module docstring for the governing law this file inherits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

import jsonschema

from gymact.ocel import digest_ocel_log, validate_ocel_log
from gymact.process import ConformanceChecker, ConformanceResult
from gymact.replay import ReplayReport


@dataclass(frozen=True)
class AliveEvidence:
    """Every real check in the chain produced positive evidence.

    Every field is a real artifact reference or a real collaborator's own
    return value -- never a fabricated default. `standing_from_episode` is
    the only place permitted to construct this type.
    """

    episode_digest: str
    conformance: ConformanceResult
    replay: ReplayReport
    receipt_id: str
    postcondition_ref: str


@dataclass(frozen=True)
class UnknownEvidence:
    """The chain stopped at a named point. Never evidence of failure, and
    never evidence of success -- exactly `FactorState.UNKNOWN`'s meaning."""

    missing: str
    episode_digest: str | None = None


@dataclass(frozen=True)
class RefusedEvidence:
    """A typed refusal is a real answer, not an absence."""

    reason: str
    subject: str


@dataclass(frozen=True)
class BlockedEvidence:
    """A named external prerequisite prevented observation."""

    reason: str


@dataclass(frozen=True)
class UnsupportedEvidence:
    """A capability/dependency genuinely absent."""

    reason: str


Standing = Union[
    AliveEvidence, UnknownEvidence, RefusedEvidence, BlockedEvidence, UnsupportedEvidence
]


def standing_to_dict(standing: Standing) -> dict:
    """Lossless dict representation, discriminated by `variant`, so
    `crown_run.json` can serialize any of the five cases without guessing
    which fields are present."""
    if isinstance(standing, AliveEvidence):
        return {
            "variant": "AliveEvidence",
            "episode_digest": standing.episode_digest,
            "conformance": {
                "conformant": standing.conformance.conformant,
                "deviations": [d.model_dump() for d in standing.conformance.deviations],
            },
            "replay": {
                "mode": standing.replay.mode.value
                if hasattr(standing.replay.mode, "value")
                else str(standing.replay.mode),
                "valid": standing.replay.valid,
                "record_count": standing.replay.record_count,
                "head_digest": standing.replay.head_digest,
                "mismatches": list(standing.replay.mismatches),
            },
            "receipt_id": standing.receipt_id,
            "postcondition_ref": standing.postcondition_ref,
        }
    if isinstance(standing, UnknownEvidence):
        return {
            "variant": "UnknownEvidence",
            "missing": standing.missing,
            "episode_digest": standing.episode_digest,
        }
    if isinstance(standing, RefusedEvidence):
        return {"variant": "RefusedEvidence", "reason": standing.reason, "subject": standing.subject}
    if isinstance(standing, BlockedEvidence):
        return {"variant": "BlockedEvidence", "reason": standing.reason}
    if isinstance(standing, UnsupportedEvidence):
        return {"variant": "UnsupportedEvidence", "reason": standing.reason}
    raise TypeError(f"UNKNOWN_STANDING_VARIANT:{type(standing).__name__}")


def standing_from_dict(payload: dict) -> Standing:
    """Reconstruct a `Standing` from its `standing_to_dict` serialization,
    using real gymact model reconstruction (`model_validate`) for the
    `AliveEvidence` case's nested `ConformanceResult`/`ReplayReport` --
    never a re-derived or approximated stand-in for either."""
    from gymact.process import ConformanceResult
    from gymact.replay import ReplayMode, ReplayReport

    variant = payload["variant"]
    if variant == "AliveEvidence":
        replay_payload = dict(payload["replay"])
        replay_payload["mode"] = ReplayMode(replay_payload["mode"])
        return AliveEvidence(
            episode_digest=payload["episode_digest"],
            conformance=ConformanceResult.model_validate(payload["conformance"]),
            replay=ReplayReport.model_validate(replay_payload),
            receipt_id=payload["receipt_id"],
            postcondition_ref=payload["postcondition_ref"],
        )
    if variant == "UnknownEvidence":
        return UnknownEvidence(missing=payload["missing"], episode_digest=payload["episode_digest"])
    if variant == "RefusedEvidence":
        return RefusedEvidence(reason=payload["reason"], subject=payload["subject"])
    if variant == "BlockedEvidence":
        return BlockedEvidence(reason=payload["reason"])
    if variant == "UnsupportedEvidence":
        return UnsupportedEvidence(reason=payload["reason"])
    raise ValueError(f"UNKNOWN_STANDING_VARIANT_IN_PAYLOAD:{variant}")


def standing_from_episode(
    log: dict,
    operations: list,
    receipts: list,
    *,
    replay: ReplayReport,
    receipt_id: str | None = None,
    postcondition_ref: str | None,
) -> Standing:
    """The ONLY constructor of a live `Standing`. Runs the real chain:

    1. real OCEL 2.0 schema validation of ``log``
       (`gymact.ocel.validate_ocel_log`);
    2. real conformance replay of ``operations``
       (`gymact.process.ConformanceChecker().check(...)`);
    3. the passed-in, already-produced `replay` (`gymact.replay.ReplayReport`)
       for this episode, checked for `.valid`;
    4. requiring ``postcondition_ref`` is not None and ``receipts`` is
       non-empty.

    Only when every one of those steps produces real positive evidence does
    this return `AliveEvidence`, built entirely from the real objects the
    caller passed in -- never a fabricated digest, receipt id, or
    postcondition ref. This function takes no boolean `success` parameter
    and derives its answer from nothing but the real collaborators given to
    it.

    Deviation from the literal signature named in the task spec: `replay`
    is threaded in as an explicit keyword argument rather than derived
    inside this function, because producing a `ReplayReport` requires a
    live `LedgerLike` (`gymact.replay.replay_ledger(ledger, ...)`), and this
    function is deliberately kept free of any ledger/subprocess/IO
    dependency so it can be unit-tested with plain real objects. The task
    text itself says "then the passed-in replay report", which only parses
    if `replay` is a parameter; the four-argument signature literally
    written in the task omits it, which would make step 3 an unaddressable
    instruction. `receipt_id` is likewise threaded in explicitly (taken
    from the first real receipt when the caller does not supply one) so
    `AliveEvidence.receipt_id` names a real receipt rather than a
    fabricated placeholder.
    """
    try:
        validate_ocel_log(log)
    except jsonschema.ValidationError as exc:
        return UnknownEvidence(missing=f"OCEL_SCHEMA_INVALID:{exc.message}", episode_digest=None)

    episode_digest = digest_ocel_log(log)

    conformance = ConformanceChecker().check(operations)
    if not conformance.conformant:
        reasons = "; ".join(d.reason for d in conformance.deviations)
        return UnknownEvidence(
            missing=f"CONFORMANCE_DEVIATIONS:{reasons}", episode_digest=episode_digest
        )

    if not replay.valid:
        mismatches = "; ".join(replay.mismatches) or "REPLAY_REPORTED_INVALID_NO_MISMATCH_DETAIL"
        return UnknownEvidence(missing=f"REPLAY_INVALID:{mismatches}", episode_digest=episode_digest)

    if postcondition_ref is None:
        return UnknownEvidence(missing="POSTCONDITION_REF_ABSENT", episode_digest=episode_digest)

    if not receipts:
        return UnknownEvidence(missing="RECEIPTS_EMPTY", episode_digest=episode_digest)

    resolved_receipt_id = receipt_id if receipt_id is not None else str(receipts[0].receipt_id)

    return AliveEvidence(
        episode_digest=episode_digest,
        conformance=conformance,
        replay=replay,
        receipt_id=resolved_receipt_id,
        postcondition_ref=postcondition_ref,
    )
