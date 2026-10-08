# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ALOOP sealed-recorder profile (court r9).

Why this exists -- the non-convergence theorem (RFC-ALOOP section "Sealed
recorder"): an unsealed OCEL log is authored, byte for byte, by the party the
court judges. Every shape rule has a complement the author can write next, and
the *absence* of a human cause is not a shape at all: a log that omits a human
act is indistinguishable, from its own bytes, from one where none happened.
Completeness is therefore not observable from the log. ALOOP-001 over an
unsealed log can at most say ``CONSISTENT_UNDER_ASSUMED_COMPLETENESS``.

A sealed log moves authorship of the evidence stream out of the judged party:

* every OCEL event is carried by exactly one record of an append-only
  :class:`~autofde_lab._cache.provenance.ProvenanceLedger` (sequence,
  ``previous_digest`` hash chain, record digest, HMAC signature by a recorder
  key that is **not** in the log), in log order, and a final ``close`` record
  binds the digest of the whole canonical document (objects, attribute
  changes, O2O included);
* completeness is witnessed from *outside* the log: (a) every commit of each
  named repository's ``git rev-list`` range maps to exactly one sealed
  ``actuate``/``commit``/``merge`` event whose output ``Subject`` carries that
  SHA (and every such sealed event claiming a named repository is in the
  range, and no sealed commit claim names an unwitnessed repository); (b)
  EVERY entry of a supplied human-message ledger maps to exactly one sealed
  ``human.intervene`` event with that ``messageId``, at exactly the witnessed
  time, on the same side of ``episode.start`` in log order as its witnessed
  time is of ``t0``; an event carries at most one ``messageId``;
* the log clock is anchored outside the author's bytes (court r9 repair,
  attack C2 "clock shift"): each sealed commit event's time must equal, to
  the second, the git committer time of its SHA, and ``t0`` (the declared
  ``episode.start``) must lie in ``[base committer time, first witnessed
  commit event]``. Without that anchor a witnessed human message cannot be
  placed relative to ``t0`` at all -- the author could shift every event
  time and push a mid-loop message before a declared epoch -- so a non-empty
  human ledger over an unanchored clock yields ``complete = None`` (never
  QUALIFIED), and a mismatch is refused ``SEAL_CLOCK_MISMATCH``.

The chain and signature code is the ledger's own
(:func:`~autofde_lab._cache.provenance.verify_ledger_records`), generalized
over the record type rather than duplicated.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from autofde_lab._cache.provenance import (
    AttestationKeyring,
    AttestationSigner,
    ProvenanceLedger,
    verify_ledger_records,
)
from autofde_lab.ocel.model import parse_ns

__all__ = [
    "COMMIT_ACTIVITIES",
    "AloopSealRecord",
    "CommitClock",
    "SealInputs",
    "git_rev_list",
    "git_witness",
    "seal_document",
    "verify_seal",
]

#: activities whose output ``Subject`` is a repository commit.
COMMIT_ACTIVITIES = frozenset({"actuate", "commit", "merge"})
_HUMAN = "human.intervene"
_SECOND = 1_000_000_000


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class AloopSealRecord:
    """One sealed-recorder ledger record: an OCEL event, or the closing digest."""

    kind: str  # "event" | "close"
    event_id: str | None
    digest: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CommitClock:
    """The git clock of one witnessed range, read from git, not from the log.

    ``times``: commit SHA -> committer time (epoch seconds). ``floor``: the
    latest committer time of the range's excluded boundary (the base), or
    ``None`` when the range has no lower boundary.
    """

    times: Mapping[str, int]
    floor: int | None = None


@dataclass(frozen=True)
class SealInputs:
    """What a verifier supplies that the judged author does not control.

    ``keyring``: recorder verification key(s). ``commits``: repository object id
    -> ordered commit SHAs from ``git rev-list`` (``None`` = not witnessed).
    ``human_messages``: the out-of-band human-message ledger, entries
    ``{"id": ..., "time": <OCEL time>}`` (``None`` = not witnessed).
    ``commit_clock``: repository object id -> :class:`CommitClock` (``None``
    = clock not witnessed; a non-empty human ledger then cannot be complete).
    """

    ledger: Path
    keyring: AttestationKeyring
    commits: Mapping[str, Sequence[str]] | None = None
    human_messages: Sequence[Mapping[str, str]] | None = None
    key_material: Sequence[bytes] = field(default_factory=tuple)
    commit_clock: Mapping[str, CommitClock] | None = None


def git_rev_list(repo: Path | str, rev_range: str) -> list[str]:
    """Commits of ``rev_range`` in ``repo``, oldest first (real ``git``)."""
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--reverse", rev_range],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in out.stdout.split() if line]


def _git_out(repo: Path | str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


def git_witness(repo: Path | str, rev_range: str) -> tuple[list[str], CommitClock]:
    """Commits of ``rev_range`` (oldest first) and their git clock (real ``git``).

    The floor is the newest committer time among the range's excluded
    revisions (``git rev-parse`` lines starting with ``^``).
    """
    shas = git_rev_list(repo, rev_range)
    times: dict[str, int] = {}
    if shas:
        for line in _git_out(
            repo, "log", "--no-walk=unsorted", "--format=%H %ct", *shas
        ).splitlines():
            sha, _, ct = line.partition(" ")
            times[sha] = int(ct)
    excluded = [
        line[1:]
        for line in _git_out(repo, "rev-parse", rev_range).split()
        if line.startswith("^")
    ]
    floor = None
    if excluded:
        floor = max(
            int(x)
            for x in _git_out(
                repo, "log", "--no-walk=unsorted", "--format=%ct", *excluded
            ).split()
        )
    return shas, CommitClock(times=times, floor=floor)


def seal_document(
    document: Mapping[str, Any], ledger: Path | str, signer: AttestationSigner
) -> Path:
    """Recorder side: append one record per OCEL event, then a close record."""
    path = Path(ledger)
    book = ProvenanceLedger(
        path, signer=signer, fsync=False, attestation_type=AloopSealRecord
    )
    for event in document.get("events", ()):
        book.append(AloopSealRecord("event", str(event["id"]), _digest(event)))
    book.append(AloopSealRecord("close", None, _digest(document)))
    return path


def _refusal(code: str, term: str, detail: str) -> dict[str, str]:
    return {
        "code": code,
        "broken_term": term,
        "failure_class": "EVIDENCE_FAILURE",
        "detail": detail,
    }


def verify_seal(document: Any, inputs: SealInputs, log_bytes: bytes) -> dict[str, Any]:
    """Verify chain, signature, OCEL<->ledger bijection and completeness.

    Returns a report with ``sealed`` (chain+signature+bijection hold),
    ``complete`` (``True``/``False``, or ``None`` when a witness is absent) and
    typed ``refusals``. Any refusal makes the court REFUSE the log.
    """
    raw = Path(inputs.ledger).read_bytes()
    report: dict[str, Any] = {
        "profile": "aloop-sealed-recorder/v1",
        "ledger_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "key_ids": list(inputs.keyring.key_ids),
        "sealed": False,
        "complete": None,
        "records": 0,
        "tail_digest": None,
        "witnesses": {"commits": None, "human_messages": None},
        "refusals": [],
    }
    refusals: list[dict[str, str]] = report["refusals"]
    for key in inputs.key_material:
        for form in (key, key.hex().encode()):
            if form and (form in log_bytes or form in raw):
                refusals.append(
                    _refusal(
                        "SEAL_KEY_DISCLOSED",
                        "R_missing_authority",
                        "recorder key material appears in the sealed bytes",
                    )
                )
                return report
    check, records = verify_ledger_records(
        raw.decode("utf-8", errors="replace").splitlines(),
        keyring=inputs.keyring,
        attestation_type=AloopSealRecord,
    )
    report["records"], report["tail_digest"] = check.records, check.tail_digest
    if not check.valid:
        refusals.append(
            _refusal("SEAL_CHAIN_INVALID", "R_missing_identity", str(check.error))
        )
        return report
    if not isinstance(document, Mapping) or not isinstance(
        document.get("events"), list
    ):
        refusals.append(
            _refusal("SEAL_BIJECTION", "R_missing_identity", "log has no event list")
        )
        return report
    atts = [r["signed_attestation"]["attestation"] for r in records]
    events = document["events"]
    if not atts or atts[-1]["kind"] != "close":
        refusals.append(
            _refusal("SEAL_BIJECTION", "R_missing_identity", "no close record")
        )
        return report
    if atts[-1]["digest"] != _digest(document):
        refusals.append(
            _refusal(
                "SEAL_BIJECTION",
                "R_missing_identity",
                "close digest does not match the canonical log document",
            )
        )
        return report
    body = atts[:-1]
    if any(a["kind"] != "event" for a in body) or len(body) != len(events):
        refusals.append(
            _refusal(
                "SEAL_BIJECTION",
                "R_missing_identity",
                f"{len(body)} event records for {len(events)} OCEL events",
            )
        )
        return report
    seen: set[str] = set()
    for a, e in zip(body, events):
        eid = str(e.get("id"))
        if a["event_id"] != eid or eid in seen or a["digest"] != _digest(e):
            refusals.append(
                _refusal(
                    "SEAL_BIJECTION",
                    "R_missing_identity",
                    f"record for {a['event_id']!r} does not bind OCEL event {eid!r}",
                )
            )
            return report
        seen.add(eid)
    report["sealed"] = True

    objects = {
        str(o.get("id")): o
        for o in document.get("objects", ())
        if isinstance(o, Mapping)
    }

    def attr(o: Mapping[str, Any], name: str) -> Any:
        vals = [
            a.get("value") for a in o.get("attributes", ()) if a.get("name") == name
        ]
        return vals[-1] if vals else None

    starts = [parse_ns(e["time"]) for e in events if e.get("type") == "episode.start"]
    t0 = min(starts) if starts else None

    by_id = {str(e.get("id")): e for e in events}
    anchored = False
    complete = True
    if inputs.commits is None:
        complete = None
    else:
        claims: dict[tuple[str, str], list[str]] = {}
        for e in events:
            if e.get("type") not in COMMIT_ACTIVITIES:
                continue
            for rel in e.get("relationships", ()):
                o = objects.get(str(rel.get("objectId")))
                if rel.get("qualifier") != "output" or o is None:
                    continue
                if o.get("type") != "Subject":
                    continue
                key = (str(attr(o, "repository")), str(attr(o, "sha")))
                claims.setdefault(key, []).append(str(e["id"]))
        witnessed = {repo: list(shas) for repo, shas in inputs.commits.items()}
        # Every sealed commit claim must be mapped by the witness: a claim naming
        # a repository outside the witnessed set would otherwise escape the
        # rev-list bijection (court r9 repair, A4_unnamed_repo).
        for (r, sha), hits in sorted(claims.items()):
            if r not in witnessed:
                refusals.append(
                    _refusal(
                        "SEAL_UNWITNESSED_COMMIT",
                        "R_missing_identity",
                        f"{hits[:3]} claim {r}@{sha}: repository not in the "
                        f"witnessed set {sorted(witnessed)}",
                    )
                )
                complete = False
        report["witnesses"]["commits"] = {
            repo: len(shas) for repo, shas in sorted(witnessed.items())
        }
        for repo, shas in sorted(witnessed.items()):
            for sha in shas:
                hits = claims.get((repo, sha), [])
                if len(hits) != 1:
                    refusals.append(
                        _refusal(
                            "SEAL_INCOMPLETE_COMMIT",
                            "R_missing_consequence",
                            f"{repo}@{sha}: {len(hits)} sealed commit events "
                            f"{hits[:3]} (exactly 1 required)",
                        )
                    )
                    complete = False
            inrange = set(shas)
            for (r, sha), hits in sorted(claims.items()):
                if r == repo and sha not in inrange:
                    refusals.append(
                        _refusal(
                            "SEAL_UNWITNESSED_COMMIT",
                            "R_missing_identity",
                            f"{hits[:3]} claim {repo}@{sha} outside the witnessed range",
                        )
                    )
                    complete = False
        # Clock anchor (court r9 repair, attack C2): the author signs whatever
        # times it writes, so the epoch must be tied to a clock it does not
        # write. Each sealed commit event is dated by git's committer time of
        # its SHA, and t0 is bounded by the base and the first commit.
        clock = inputs.commit_clock
        if clock is not None and all(r in clock for r in witnessed):
            anchor_ns: list[int] = []
            clock_ok = True
            for repo, shas in sorted(witnessed.items()):
                for sha in shas:
                    hits = claims.get((repo, sha), [])
                    if len(hits) != 1:
                        continue
                    ev = by_id[hits[0]]
                    e_ns = parse_ns(str(ev["time"]))
                    ct = clock[repo].times.get(sha)
                    if ct is None or e_ns // _SECOND != ct:
                        refusals.append(
                            _refusal(
                                "SEAL_CLOCK_MISMATCH",
                                "R_missing_identity",
                                f"{hits[0]!r} claims {repo}@{sha} at {ev.get('time')} "
                                f"but git committer time is {ct} (epoch s)",
                            )
                        )
                        clock_ok = False
                        continue
                    anchor_ns.append(e_ns)
            floors = [c.floor for r, c in clock.items() if r in witnessed]
            floor_s = max((f for f in floors if f is not None), default=None)
            if t0 is not None and floor_s is not None and t0 < floor_s * _SECOND:
                refusals.append(
                    _refusal(
                        "SEAL_CLOCK_MISMATCH",
                        "R_missing_identity",
                        f"episode.start at {t0} ns precedes the witnessed base "
                        f"commit time {floor_s} s",
                    )
                )
                clock_ok = False
            if t0 is not None and anchor_ns and t0 > min(anchor_ns):
                refusals.append(
                    _refusal(
                        "SEAL_CLOCK_MISMATCH",
                        "R_missing_identity",
                        f"episode.start at {t0} ns follows the first witnessed "
                        f"commit event at {min(anchor_ns)} ns",
                    )
                )
                clock_ok = False
            if not clock_ok:
                complete = False
            anchored = clock_ok and bool(anchor_ns) and t0 is not None
    report["clock_anchored"] = anchored
    if inputs.human_messages is None:
        complete = None if complete is not False else False
    else:
        # A human message is witnessed out of band with its own time. Its sealed
        # human.intervene must carry exactly that messageId, at exactly that
        # time, and (after t0) sit after episode.start in log order: otherwise
        # a mid-loop human act can be relabelled as pre-epoch goal supply
        # (court r9 repair, attacks A1b/A3/A4).
        start_pos = min(
            (i for i, e in enumerate(events) if e.get("type") == "episode.start"),
            default=None,
        )
        by_msg: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        for i, e in enumerate(events):
            if e.get("type") != _HUMAN:
                continue
            mids = [
                str(a.get("value"))
                for a in e.get("attributes", ())
                if a.get("name") == "messageId"
            ]
            if len(mids) > 1:
                refusals.append(
                    _refusal(
                        "SEAL_INCOMPLETE_HUMAN",
                        "mu_on_O",
                        f"human.intervene {e.get('id')!r} carries {len(mids)} "
                        "messageIds (at most 1 per event)",
                    )
                )
                complete = False
            for mid in mids:
                by_msg.setdefault(mid, []).append((i, e))
        # Every witnessed message, pre-epoch ones included: a pre-t0 filter
        # read t0 from the author's bytes, so a shifted clock dropped genuine
        # mid-loop messages from the witness set (court r9 repair, C2).
        messages = list(inputs.human_messages)
        report["witnesses"]["human_messages"] = len(messages)
        for m in messages:
            hits = by_msg.get(str(m["id"]), [])
            if len(hits) != 1:
                refusals.append(
                    _refusal(
                        "SEAL_INCOMPLETE_HUMAN",
                        "mu_on_O",
                        f"human message {m['id']!r} at {m['time']}: {len(hits)} "
                        "sealed human.intervene events (exactly 1 required)",
                    )
                )
                complete = False
                continue
            pos, ev = hits[0]
            m_ns = parse_ns(str(m["time"]))
            e_ns = parse_ns(str(ev["time"]))
            wrong_side = False
            if start_pos is not None and t0 is not None:
                wrong_side = (pos <= start_pos) if m_ns >= t0 else (pos > start_pos)
            if e_ns != m_ns or wrong_side:
                refusals.append(
                    _refusal(
                        "SEAL_INCOMPLETE_HUMAN",
                        "mu_on_O",
                        f"human message {m['id']!r} witnessed at {m['time']} but "
                        f"sealed as {ev.get('id')!r} at {ev.get('time')} (log "
                        f"position {pos}, episode.start at {start_pos}): time must "
                        "match and log order must agree with t0",
                    )
                )
                complete = False
        if messages and not anchored and complete is True:
            # the messages cannot be placed relative to an author-chosen t0
            complete = None
    report["complete"] = complete
    return report


def keyring_from_file(
    path: Path | str, key_id: str
) -> tuple[AttestationKeyring, bytes]:
    """Load a recorder verification key (raw bytes, or hex text) from a file."""
    data = Path(path).read_bytes().strip()
    try:
        key = bytes.fromhex(data.decode("ascii"))
    except (UnicodeDecodeError, ValueError):
        key = data
    return AttestationKeyring((AttestationSigner(key, key_id=key_id),)), key


def load_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text())
