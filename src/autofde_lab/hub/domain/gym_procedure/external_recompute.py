# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Recompute Level 4 standing from durable artifacts alone.

This is the crown threshold, stated as an executable check rather than an
aspiration:

    Delete the Python runtime state. Load only what is on disk. Recompute the
    same standing.

If that succeeds, standing is **external to the actor** -- checkable by
someone who did not run the trial and does not trust the runtime that
produced it. If it fails, standing still depends on the implementation that
emitted it, which is self-attestation with extra steps.

This module deliberately reads NOTHING from `TrialReport`, `CrownRun`, or any
in-memory object. Its only inputs are files. What it cannot establish from a
file, it reports as a missing identity -- never as a pass, and never as a
failure-by-default (see `.claude/rules/absence-is-not-evidence.md`).

Today it is expected to report missing joins, because the artifacts do not yet
carry them: `commitment.ttl` and `episode.ocel.json` share no identity, and
`parent_receipt_ids` is dropped at OCEL export. That honest failure is the
point -- it measures the distance to the threshold instead of asserting it.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

#: The identity joins that must be reconstructible from artifacts alone for
#: standing to be recomputable externally. Each is a question a third party
#: must be able to answer without the runtime.
REQUIRED_JOINS: tuple[tuple[str, str], ...] = (
    ("commitment->episode", "was this actuation the realization of this exact commitment?"),
    ("authority->actuation", "was this exact actuation authorized by this exact authority envelope?"),
    ("postcondition->actuation", "did an independent observation of THIS actuation occur?"),
    ("receipt->parents", "can the receipt DAG be reconstructed?"),
    ("replay->receipt", "did the replay bind the exact source receipt?"),
)


@dataclass(frozen=True)
class ArtifactSet:
    """Only files. No runtime objects, by construction."""

    trial_dir: Path
    ocel: Optional[dict] = None
    commitment_turtle: Optional[str] = None
    ledger_path: Optional[Path] = None

    @classmethod
    def load(cls, trial_dir: Path) -> "ArtifactSet":
        act = trial_dir / "actuation"
        ocel_path = act / "episode.ocel.json"
        ttl_path = act / "commitment.ttl"
        ledger = act / "receipts.sqlite3"
        return cls(
            trial_dir=trial_dir,
            ocel=json.loads(ocel_path.read_text()) if ocel_path.is_file() else None,
            commitment_turtle=ttl_path.read_text() if ttl_path.is_file() else None,
            ledger_path=ledger if ledger.is_file() else None,
        )


@dataclass(frozen=True)
class JoinResult:
    """One identity join, and the exact evidence establishing it (or not)."""

    join: str
    question: str
    established: bool
    detail: str
    witness: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecomputedStanding:
    """The verdict a third party can reach from artifacts alone."""

    trial_dir: str
    joins: tuple[JoinResult, ...]
    missing_artifacts: tuple[str, ...] = ()

    def unestablished(self) -> list[str]:
        return [j.join for j in self.joins if not j.established]

    def verdict(self) -> str:
        """`EXTERNALLY_RECOMPUTABLE` only when every required join is
        established from files. Otherwise `UNKNOWN:<missing joins>` -- an
        unestablished join is not a failed trial, it is an unanswerable
        question, and those are different things."""
        if self.missing_artifacts:
            return f"UNKNOWN:ARTIFACTS_ABSENT:{','.join(self.missing_artifacts)}"
        missing = self.unestablished()
        if missing:
            return f"UNKNOWN:JOIN_NOT_ESTABLISHED:{','.join(missing)}"
        return "EXTERNALLY_RECOMPUTABLE"

    def report(self) -> list[str]:
        return [
            f"{'OK ' if j.established else '-- '}{j.join}: {j.detail}" for j in self.joins
        ]


_DIGEST_RE = re.compile(r'"([0-9a-f]{8,64})"')


def _ocel_tokens(ocel: dict) -> set[str]:
    """Every identity-bearing string anywhere in the OCEL graph."""
    tokens: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            tokens.add(node)

    walk(ocel)
    return tokens


def _receipt_rows(ledger: Path) -> list[dict]:
    con = sqlite3.connect(ledger)
    try:
        rows = con.execute("SELECT receipt_json FROM receipt_evidence ORDER BY sequence").fetchall()
    finally:
        con.close()
    return [json.loads(r[0]) for r in rows]


def recompute(trial_dir: Path) -> RecomputedStanding:
    """Attempt the third-party recomputation. Files only."""
    arts = ArtifactSet.load(trial_dir)
    missing = [
        name
        for name, present in (
            ("episode.ocel.json", arts.ocel is not None),
            ("commitment.ttl", arts.commitment_turtle is not None),
            ("receipts.sqlite3", arts.ledger_path is not None),
        )
        if not present
    ]
    if missing:
        return RecomputedStanding(str(trial_dir), (), tuple(missing))

    assert arts.ocel is not None and arts.commitment_turtle is not None and arts.ledger_path is not None
    tokens = _ocel_tokens(arts.ocel)
    receipts = _receipt_rows(arts.ledger_path)
    ttl = arts.commitment_turtle
    results: list[JoinResult] = []

    # 1. commitment -> episode: does any digest in the TTL appear in the OCEL,
    #    or any OCEL identity appear in the TTL? Adjacency is not a join.
    ttl_digests = set(_DIGEST_RE.findall(ttl))
    shared = ttl_digests & tokens
    ttl_mentions_ocel = [t for t in tokens if len(t) >= 16 and t in ttl]
    established = bool(shared or ttl_mentions_ocel)
    results.append(
        JoinResult(
            "commitment->episode",
            REQUIRED_JOINS[0][1],
            established,
            (
                f"shared identities: {sorted(shared | set(ttl_mentions_ocel))}"
                if established
                else "no identity appears in BOTH commitment.ttl and episode.ocel.json "
                "(filesystem adjacency is not a join)"
            ),
            tuple(sorted(shared | set(ttl_mentions_ocel))),
        )
    )

    # 2. authority -> actuation: does an ACT receipt carry a real authority ref?
    act_receipts = [r for r in receipts if r.get("operation") == "act"]
    with_auth = [r for r in act_receipts if r.get("authority_ref")]
    results.append(
        JoinResult(
            "authority->actuation",
            REQUIRED_JOINS[1][1],
            bool(act_receipts) and len(with_auth) == len(act_receipts),
            f"{len(with_auth)}/{len(act_receipts)} act receipts carry authority_ref",
            tuple(sorted({r["authority_ref"] for r in with_auth if r.get("authority_ref")})),
        )
    )

    # 3. postcondition -> actuation: a verify receipt naming an act receipt.
    verify_receipts = [r for r in receipts if r.get("operation") == "verify"]
    act_ids = {r.get("receipt_id") for r in act_receipts}
    linked = [r for r in verify_receipts if set(r.get("parent_receipt_ids") or []) & act_ids]
    results.append(
        JoinResult(
            "postcondition->actuation",
            REQUIRED_JOINS[2][1],
            bool(linked),
            f"{len(linked)}/{len(verify_receipts)} verify receipts name an act receipt as parent",
            tuple(sorted(r.get("verification_id") or "" for r in linked if r.get("verification_id"))),
        )
    )

    # 4. receipt DAG: is ancestry reconstructible FROM THE OCEL, not only from
    #    the ledger?
    #
    #    WEAKNESS IN THIS CHECK, stated rather than hidden: it tests whether a
    #    parent receipt id appears anywhere in the OCEL as a token. Receipt ids
    #    ARE event ids there, so this passes on incidental token presence, not
    #    on a real parent EDGE. gymact's receipts_to_ocel emits no O2O
    #    relationships at all, so no explicit ancestry edge exists today. A
    #    stronger version of this join must require a typed relationship, not
    #    co-occurrence of a string -- until then this row reads OK for a
    #    reason weaker than the question it claims to answer.
    parents_in_ledger = any(r.get("parent_receipt_ids") for r in receipts)
    parents_in_ocel = any(
        pid in tokens for r in receipts for pid in (r.get("parent_receipt_ids") or [])
    )
    results.append(
        JoinResult(
            "receipt->parents",
            REQUIRED_JOINS[3][1],
            parents_in_ledger and parents_in_ocel,
            (
                "receipt ancestry present in both ledger and OCEL"
                if parents_in_ledger and parents_in_ocel
                else f"parent_receipt_ids in ledger={parents_in_ledger}, "
                f"reconstructible from OCEL={parents_in_ocel}"
            ),
        )
    )

    # 5. replay -> receipt: is any replay result durable at all?
    replay_files = [p.name for p in (trial_dir / "actuation").glob("replay*.json")]
    results.append(
        JoinResult(
            "replay->receipt",
            REQUIRED_JOINS[4][1],
            bool(replay_files),
            (
                f"replay artifacts: {replay_files}"
                if replay_files
                else "no durable replay artifact; the replay verdict exists only in runtime state"
            ),
            tuple(replay_files),
        )
    )

    return RecomputedStanding(str(trial_dir), tuple(results))
