# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ALOOP-001 -- basic closed-loop court over an OCEL 2.0 flight recorder.

Spec: ``docs/rfcs/RFC-ALOOP-v26.9.25.md``. Profile:
``schemas/aloop/ocel2-aloop-profile.json`` (constrains the official OCEL 2.0
JSON schema vendored beside it).

Admission, in order (any failure -> ``REFUSED``, exit 2):

1. the document validates against the official OCEL 2.0 JSON schema;
2. it parses into :class:`autofde_lab.ocel.OcelLog` and passes
   ``validate(strict_qualifiers=True)`` (OCPQ Definition 2 laws, reused);
3. it satisfies the ALOOP profile (types, qualifiers, qualifier target
   types, per-event required qualifier cardinalities, required attributes);
4. it is not internally forged: one ``episode.start`` per episode, no
   non-consequence object minted twice, no cause produced after its
   consumer, every ``workorder.issue`` origin authority granted at the
   episode epoch.

Causal graph: event ``p -> e`` iff ``e`` consumes (qualifier ``input`` or
``cause``) an object that ``p`` produced (qualifier ``output``; or
``consequence`` on an actuation). Nothing else creates an edge -- in
particular timestamps and log order never do. O2O links are read for human
provenance: a consumed object with an O2O path (any profile qualifier) to a
``Human`` -- or to an object whose ``origin`` is ``human`` -- is a human cause,
unless the path passes through the lawful pre-epoch channel (``Objective``,
``Authority``).

Closing rule (repair round 1): a ``receipt.persist`` closes iteration ``w`` only
if it binds at least one ``consequence`` produced by an actuation that is
causally downstream of ``w`` and inside the receipt's own iteration segment.
A loop that never actuates, or that re-receipts an earlier consequence, cannot
close; ALOOP-001 additionally requires ``actuations > 0`` (``UAR`` is never
defaulted from 0/0).

Repair round 2: every object a ``human.intervene`` links under any qualifier
is human-touched (consuming it is a human causal edge); every actuation must
have a ``workorder.issue`` of its episode upstream (``UNAUTHORIZED_ACTUATION``);
``episode.start``/``receipt.persist`` must bind a ``Subject``, not a Repository.

Repair round 3: whether a human touch is a human cause is judged relative to
the consuming event's episode epoch (never the human event's own episode); a
causal E2O flow across episodes is refused (``CROSS_EPISODE_CAUSALITY``); and
human taint propagates transitively through pre-epoch machine events, so a
pre-epoch hop cannot launder a human-authored next action.

Repair round 4: a transition ``receipt[n] -> reobserve[n+1] -> workorder[n+1]``
counts only if the reobserve is fresh -- strictly after ``receipt[n]``, consuming
its output, with no later receipt persisted before ``workorder[n+1]``, no older
observation in ``workorder[n+1]``'s segment, and no superseded Subject read in
that segment; a stale transition is dropped from ALD and reported as
``STALE_REOBSERVE`` (B4). A post-epoch human act that outputs, modifies or links
(E2O, or O2O through what it links) an ``Authority``/``Objective`` object makes
every later event citing that object (``originAuthority``/``input``/``cause``)
human-caused; an ``Authority`` a machine event outputs after ``t0`` without
consuming the pre-declared envelope (an ``Authority`` granted at
``episode.start``) is the same human next-action channel (C9).

Repair round 5: freshness is judged over the whole causal cone of
``workorder[n+1]`` back to ``receipt[n]`` -- including the reobserve's own
inputs and every machine hop between them. Every object consumed in that cone
must be ``receipt[n]``'s own output, produced strictly after ``receipt[n]``, or
a lawful ``Objective``/``Authority``; any other older state, of any activity
and any type, makes the transition ``STALE_REOBSERVE`` (B4'). The C9 channel
follows O2O links with no hop bound: a post-epoch human act opens the channel
of every ``Objective``/``Authority`` in the O2O component of anything it links.

Repair round 6: the B4' cone exempts an ``Objective``/``Authority`` by
provenance, never by type. Only the pre-declared envelope -- the
``Objective``/``Authority`` objects the episode's ``episode.start`` consumes
(``input``/``cause``/``originAuthority``) -- is lawful older state. Any other
object of those types (a pre-epoch per-iteration script, a post-epoch machine
output, a pre-epoch human script that ``episode.start`` never bound) is judged
by its producer's position like any other state: produced before ``receipt[n]``
it is stale (B4'', ``R_not_fed_back``).

Repair round 7: the envelope exemption is not a laundering slot. Binding a
per-iteration next-action script into ``episode.start`` made every scripted
step "pre-declared" and brought the r6 kill-target mutants back to
``AUTONOMOUS`` (finish adversarial r2 H1/H2/H3). Two laws close it (B4'''):
(a) the cone is rooted -- every event in the cone of ``workorder[n+1]`` after
``receipt[n]`` must itself be causally downstream of ``receipt[n]``, so a
decision taken from envelope state alone (a gap.detect whose only cause is a
bound script step, the fresh observation attached decoratively later) is
stale; the only unrooted hop allowed is an envelope derivation (every causal
input envelope state, every output an ``Objective``/``Authority``);
(b) the envelope is invariant -- an envelope object cited (``input``/``cause``/
``originAuthority``) in the cone of some candidate transition of the episode
but not in every one is per-iteration decision state, not a goal or a policy,
and loses the exemption;
(c) the envelope is bounded -- an invariant envelope with at least as many
objects consumed in every cone as there are candidate transitions has the
capacity of a one-step-per-iteration script (every work order citing the whole
bound script), so none of it is exempt. (Law (c) is replaced in round 8.)

Repair round 8 stops closing channels one at a time. The finish adversarial
court r3 refused r7 with J1 (a producer-less post-epoch Objective, O2O-bound
to the Human, causing every reobserve: QUALIFIED). A fail-closed provenance
law replaces the channel-by-channel exemptions (RFC "Fail-closed provenance
law"; gated by ``_LAWS`` so the ablation witness can drop exactly one):
P1 closed world -- every object a post-epoch machine event links, under any
qualifier but its own output, is output by an earlier (strictly, in time)
post-epoch machine event of the episode, or is frozen envelope state
(declared by episode.start, created at or before it, never modified after
t0); anything else is ``UNATTRIBUTED_EXOGENOUS_CAUSE`` and the episode FAILS.
P2 human taint is qualifier-agnostic -- a Human reached over any E2O
qualifier, any O2O relation (either direction, any depth, any type), or an
attribute change co-timed with a human act after t0 makes the episode
ASSISTED. P3 rooted, functional, unindexed cone -- hops before reobserve[n+1]
descend from receipt[n], every other hop from reobserve[n+1]; strict time
order (G7); invariant envelope; one reobserve roots one work order (a forked
next action, the J3 candidate inflation that defeated law (c), is not a
transition); an envelope family of same-typed objects or an envelope object
with a multi-valued attribute is indexed per iteration and not exempt. A
script in one scalar attribute value remains beyond an OCEL court (UNKNOWN).

Repair round 9 closes P1-P3 over the whole episode, not over the work-order
cone (finish adversarial r0 attacks-r8 K1/K4b/K8/K9, each QUALIFIED on r8):
the indexed and invariance clauses of P3 were applied only inside the cone of
``workorder.issue`` and only to Objective/Authority envelope members, and
P1's frozen exemption did not consult them, so a human-authored step-n cited by
``actuate[n]`` (K1) or by ``workorder.issue[n]`` under ``evidence`` (K4b) rode
through as "frozen envelope state". P1 now exempts only the frozen AND
unindexed AND invariant part of the envelope, where -- over every object
episode.start declares, of any type, under any qualifier -- indexed means a
same-typed family, a multi-valued attribute, or an attribute key outside the
profile's closed ``envelopeAttributes`` vocabulary (a key-indexed script), and
invariant means every post-epoch machine event of one activity that cites
envelope objects (any qualifier) cites the same set. OCEL ``ObjectChange``
values have no producing event: P1 attributes a value on a non-envelope object
only when it is timed exactly at the object's post-epoch machine producer, so
an attribute changed after creation (K9) is unattributed; P2 treats such an
unattributed change at or after any post-epoch human act as human contact
(K8), not only one co-timed to the nanosecond.

Round 9 also admits what generate-and-kill cannot converge on (RFC section
"Non-convergence and the sealed recorder"): the log's author controls every
byte, so no shape rule certifies the *absence* of a human cause, and
completeness is not observable from the log. The verdict lattice is therefore:
``QUALIFIED`` (exit 0, episode ``AUTONOMOUS``) only for a log sealed by the
recorder profile (``autofde_lab.aloop.seal``) AND complete against external
witnesses (git rev-list, human-message ledger) AND passing every rule; an
unsealed (or sealed but unwitnessed) log that passes every rule is
``CONSISTENT_UNDER_ASSUMED_COMPLETENESS`` relative to the content hash of its
frozen envelope, standing ceiling PARTIAL_ALIVE, exit 3; a sealed log whose
chain, signature, bijection or completeness fails is REFUSED (exit 2).
``NOT_QUALIFIED``/``REFUSED`` from the rules are unchanged.

The verdict is a pure function of (log bytes, profile bytes, court source,
seal ledger bytes and witnesses): the receipt carries no wall-clock value, so a
cold replay is byte-identical.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from autofde_lab.ocel import OcelError, OcelLog

__all__ = [
    "COURT_ID",
    "COURT_VERSION",
    "EXIT_QUALIFIED",
    "EXIT_NOT_QUALIFIED",
    "EXIT_REFUSED",
    "EXIT_CONSISTENT_UNDER_ASSUMED_COMPLETENESS",
    "CONSISTENT",
    "AloopRefusal",
    "load_profile",
    "evaluate_document",
    "evaluate_path",
    "canonical",
]

COURT_ID = "ALOOP-001"
COURT_VERSION = "aloop-001/v26.9.25-r9"
RECEIPT_SCHEMA = "autofde-lab/aloop-court-receipt/v1"

EXIT_QUALIFIED = 0
EXIT_REFUSED = 2
EXIT_NOT_QUALIFIED = 3
#: r9 verdict lattice: rules pass but the log is not sealed+complete. Never 0.
EXIT_CONSISTENT_UNDER_ASSUMED_COMPLETENESS = 3
CONSISTENT = "CONSISTENT_UNDER_ASSUMED_COMPLETENESS"

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROFILE = REPO_ROOT / "schemas" / "aloop" / "ocel2-aloop-profile.json"

_HUMAN = "human.intervene"
_WORKORDER = "workorder.issue"
_RECEIPT = "receipt.persist"
_REOBSERVE = "reobserve"
_START = "episode.start"

#: Repair round 8: the fail-closed provenance law is three clauses (RFC
#: section "Fail-closed provenance law"). Each is gated here so the ablation
#: witness can disable exactly one and show a mutant survives without it.
_LAWS = frozenset({"P1", "P2", "P3"})


def canonical(value: Any) -> str:
    """Compact, key-sorted JSON -- the byte form every digest is taken over."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ratio(num: int, den: int) -> float | None:
    return None if den == 0 else round(num / den, 6)


@dataclass(frozen=True)
class AloopRefusal(Exception):
    """A typed refusal: the log is not admissible evidence for this court."""

    code: str
    broken_term: str
    failure_class: str
    detail: str

    def as_json(self) -> dict[str, str]:
        return {
            "code": self.code,
            "broken_term": self.broken_term,
            "failure_class": self.failure_class,
            "detail": self.detail,
        }


def _reason(code: str, term: str, klass: str, detail: str) -> dict[str, str]:
    return {"code": code, "broken_term": term, "failure_class": klass, "detail": detail}


# ── profile ─────────────────────────────────────────────────────────────────


def load_profile(path: Path | None = None) -> dict[str, Any]:
    """Load the ALOOP profile and the official schema it pins, checking the pin."""
    profile_path = Path(path) if path is not None else DEFAULT_PROFILE
    profile_bytes = profile_path.read_bytes()
    profile = json.loads(profile_bytes)
    base = profile["base_schema"]
    schema_path = REPO_ROOT / base["path"]
    schema_bytes = schema_path.read_bytes()
    actual = _sha256(schema_bytes)
    if actual != base["sha256"]:
        raise AloopRefusal(
            "BASE_SCHEMA_PIN_MISMATCH",
            "R_missing_identity",
            "VERIFICATION_FAILURE",
            f"{base['path']} sha256 {actual} != pinned {base['sha256']}",
        )
    profile["_profile_sha256"] = _sha256(profile_bytes)
    profile["_base_schema"] = json.loads(schema_bytes)
    return profile


def _court_source_sha256(profile: Mapping[str, Any]) -> str:
    digest = hashlib.sha256()
    digest.update(Path(__file__).read_bytes())
    # r9: the sealed-recorder verifier is part of the verdict function
    digest.update((Path(__file__).parent / "seal.py").read_bytes())
    digest.update(profile["_profile_sha256"].encode())
    digest.update(profile["base_schema"]["sha256"].encode())
    return digest.hexdigest()


# ── admission ───────────────────────────────────────────────────────────────


def _refuse(
    code: str, detail: str, term: str = "mu_on_O", klass: str = "EVIDENCE_FAILURE"
):
    raise AloopRefusal(code, term, klass, detail)


def _admit(document: Any, profile: Mapping[str, Any]) -> OcelLog:
    try:
        import jsonschema
    except ModuleNotFoundError as exc:  # pragma: no cover - environment defect
        raise AloopRefusal(
            "VALIDATOR_UNAVAILABLE",
            "R_missing_replay",
            "TRANSPORT_FAILURE",
            f"jsonschema not importable: {exc}",
        ) from exc
    validator = jsonschema.Draft7Validator(profile["_base_schema"])
    errors = sorted(
        validator.iter_errors(document), key=lambda e: list(e.absolute_path)
    )
    if errors:
        first = errors[0]
        where = "/".join(str(p) for p in first.absolute_path)
        _refuse("OCEL2_SCHEMA_VIOLATION", f"{where}: {first.message}")
    try:
        log = OcelLog.from_ocel2_json(document).validate(strict_qualifiers=True)
    except OcelError as exc:
        _refuse(f"OCEL_ADMISSION:{exc.refusal.value}", exc.detail)
    except (KeyError, ValueError, TypeError) as exc:
        _refuse("OCEL_PARSE_FAILURE", f"{type(exc).__name__}: {exc}")

    object_types = set(profile["objectTypes"])
    event_types = set(profile["eventTypes"])
    for section, allowed in (
        ("objectTypes", object_types),
        ("eventTypes", event_types),
    ):
        for entry in document.get(section) or ():
            if entry["name"] not in allowed:
                _refuse("PROFILE_UNKNOWN_TYPE", f"{section} declares {entry['name']!r}")
    otype = {o.id: o.object_type for o in log.objects}
    attrs = {
        o.id: {a.key: a.value.to_json() for a in o.attributes} for o in log.objects
    }
    for oid, t in otype.items():
        if t not in object_types:
            _refuse("PROFILE_UNKNOWN_OBJECT_TYPE", f"object {oid} has type {t!r}")
        for name in profile["requiredObjectAttributes"].get(t, ()):
            if attrs[oid].get(name) in (None, ""):
                _refuse("PROFILE_MISSING_OBJECT_ATTRIBUTE", f"{t} {oid} lacks {name!r}")
        if t == "Authority" and attrs[oid]["kind"] not in profile["authorityKinds"]:
            _refuse(
                "PROFILE_AUTHORITY_KIND",
                f"Authority {oid} kind {attrs[oid]['kind']!r}",
                "R_missing_authority",
                "AUTHORITY_FAILURE",
            )
    qualifiers: Mapping[str, Any] = profile["e2oQualifiers"]
    links: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for link in log.event_object_links:
        q = link.qualifier or ""
        if q not in qualifiers:
            _refuse(
                "PROFILE_UNKNOWN_QUALIFIER", f"event {link.event_id} qualifier {q!r}"
            )
        allowed = qualifiers[q]
        if allowed != "*" and otype[link.object_id] not in allowed:
            _refuse(
                "PROFILE_QUALIFIER_TARGET_TYPE",
                f"event {link.event_id} {q} -> {otype[link.object_id]} {link.object_id}",
            )
        links[link.event_id].append((q, link.object_id))
    activity = {e.id: e.activity for e in log.events}
    narrowing: Mapping[str, Any] = profile["e2oQualifierTargetsByEvent"]
    for link in log.event_object_links:
        allowed_here = narrowing.get(activity.get(link.event_id, ""), {}).get(
            link.qualifier or ""
        )
        if allowed_here is not None and otype[link.object_id] not in allowed_here:
            _refuse(
                "PROFILE_QUALIFIER_TARGET_TYPE",
                f"event {link.event_id} ({activity[link.event_id]}) "
                f"{link.qualifier} -> {otype[link.object_id]} {link.object_id}; "
                f"needs {allowed_here}",
                "R_missing_identity",
                "SUBJECT_FAILURE",
            )
    for link in log.object_object_links:
        if (link.qualifier or "") not in profile["o2oQualifiers"]:
            _refuse(
                "PROFILE_UNKNOWN_QUALIFIER",
                f"o2o {link.source_id}->{link.target_id} qualifier {link.qualifier!r}",
            )
    required = profile["required"]
    for event in log.events:
        if event.activity not in event_types:
            _refuse(
                "PROFILE_UNKNOWN_EVENT_TYPE",
                f"event {event.id} type {event.activity!r}",
            )
        counts: dict[str, int] = defaultdict(int)
        for q, _ in links[event.id]:
            counts[q] += 1
        for spec in (required["*"], required.get(event.activity, {})):
            for q, (lo, hi) in spec.items():
                n = counts[q]
                if n < lo or (hi is not None and n > hi):
                    term, klass = (
                        ("R_missing_authority", "AUTHORITY_FAILURE")
                        if q == "originAuthority"
                        else ("mu_on_O", "EVIDENCE_FAILURE")
                    )
                    _refuse(
                        "PROFILE_QUALIFIER_CARDINALITY",
                        f"event {event.id} ({event.activity}) has {n} {q!r}, needs [{lo},{hi}]",
                        term,
                        klass,
                    )
        for name, allowed_values in (
            profile["requiredEventAttributes"].get(event.activity, {}).items()
        ):
            values = {a.key: a.value.to_json() for a in event.attributes}
            if values.get(name) not in allowed_values:
                _refuse(
                    "PROFILE_EVENT_ATTRIBUTE",
                    f"event {event.id} {name}={values.get(name)!r} not in {allowed_values}",
                )
    return log


# ── analysis ────────────────────────────────────────────────────────────────


class _Graph:
    """The causal graph derived from qualified E2O links, plus lookup tables."""

    def __init__(self, log: OcelLog, profile: Mapping[str, Any]) -> None:
        indexed = list(enumerate(log.events))
        indexed.sort(key=lambda pair: (pair[1].timestamp_ns, pair[0]))
        self.events = [e for _, e in indexed]
        self.pos = {e.id: i for i, e in enumerate(self.events)}
        self.act = {e.id: e.activity for e in self.events}
        self.ts = {e.id: e.timestamp_ns for e in self.events}
        self.eattr = {
            e.id: {a.key: a.value.to_json() for a in e.attributes} for e in self.events
        }
        self.otype = {o.id: o.object_type for o in log.objects}
        self.oattr = {
            o.id: {a.key: a.value.to_json() for a in o.attributes} for o in log.objects
        }
        # Repair round 8: time-stamped attribute values (OCEL ``ObjectChange``)
        # -- a value history, read by P1 (modified after t0), P2 (co-timed with
        # a human act) and P3 (an ordered value sequence is an indexed script).
        self.values: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for o in log.objects:
            for a in o.attributes:
                self.values[o.id][a.key] += 1
        self.changes: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for ch in log.object_changes:
            self.values[ch.object_id][ch.attribute] += 1
            self.changes[ch.object_id].append((ch.attribute, ch.timestamp_ns or 0))
        self.links: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for link in log.event_object_links:
            self.links[link.event_id].append((link.qualifier or "", link.object_id))
        actuations = set(profile["actuations"])
        self.actuations = actuations
        causal = set(profile["causalQualifiers"])
        producing = set(profile["producingQualifiers"])

        self.episode: dict[str, str] = {}
        for e in self.events:
            (eid,) = [o for q, o in self.links[e.id] if q == "episode"]
            self.episode[e.id] = eid
        starts: dict[str, list[str]] = defaultdict(list)
        for e in self.events:
            if e.activity == _START:
                starts[self.episode[e.id]].append(e.id)
        for ep in sorted(set(self.episode.values())):
            if len(starts[ep]) != 1:
                _refuse(
                    "EPISODE_START_CARDINALITY",
                    f"episode {ep} has {len(starts[ep])} {_START}",
                )
        self.start = {ep: ids[0] for ep, ids in starts.items()}
        # Repair round 6 (B4''): the pre-declared envelope of each episode --
        # the Objective/Authority objects its episode.start consumes. This is
        # the only older state the B4' freshness cone exempts.
        allowed_pre_types = set(profile["humanPreEpochAllowedOutputTypes"])
        declared_state: dict[str, set[str]] = {
            ep: {
                o
                for q, o in self.links[s]
                if q in ("input", "cause", "originAuthority")
                and self.otype.get(o) in allowed_pre_types
            }
            for ep, s in self.start.items()
        }

        self.producers: dict[str, list[str]] = defaultdict(list)
        for e in self.events:
            for q, o in self.links[e.id]:
                if q in producing or (q == "consequence" and e.activity in actuations):
                    if e.id not in self.producers[o]:
                        self.producers[o].append(e.id)
        for o, ps in sorted(self.producers.items()):
            if len(ps) > 1 and self.otype[o] != "Consequence":
                _refuse("MULTIPLE_PRODUCERS", f"object {o} produced by {ps}")

        # Repair round 8 (P1 closed world): the envelope an episode.start
        # declares, under ANY qualifier, and the part of it that is frozen --
        # created at or before episode.start, never modified after t0 (no
        # post-epoch attribute value, no post-epoch output, no post-epoch
        # human link). ``touch_any[o]``: every human.intervene linking ``o``
        # under any qualifier but ``episode`` (P2 is qualifier-agnostic).
        self.touch_any: dict[str, list[str]] = defaultdict(list)
        for e in self.events:
            if e.activity == _HUMAN:
                for q, o in self.links[e.id]:
                    if q != "episode" and e.id not in self.touch_any[o]:
                        self.touch_any[o].append(e.id)
        self.human_ts = {e.timestamp_ns for e in self.events if e.activity == _HUMAN}
        # Repair round 9 (P2, K8): per episode, the earliest human act after
        # its epoch or of another episode.
        self.first_post_human: dict[str, int] = {}
        for ep, s in self.start.items():
            ts = [
                self.ts[e.id]
                for e in self.events
                if e.activity == _HUMAN
                and (self.episode[e.id] != ep or self.pos[e.id] > self.pos[s])
            ]
            if ts:
                self.first_post_human[ep] = min(ts)
        self.declared: dict[str, frozenset[str]] = {
            ep: frozenset(o for _, o in self.links[s]) for ep, s in self.start.items()
        }
        self.frozen: dict[str, frozenset[str]] = {}
        for ep, s in self.start.items():
            t0, p0 = self.ts[s], self.pos[s]
            self.frozen[ep] = frozenset(
                o
                for o in self.declared[ep]
                if all(self.pos[p] <= p0 for p in self.producers.get(o, ()))
                and all(t <= t0 for _, t in self.changes.get(o, ()))
                and not any(
                    self.pos[h] > p0 or self.episode[h] != ep
                    for h in self.touch_any.get(o, ())
                )
            )
        # Repair round 8 (P3 not indexed): an envelope that is a family of
        # same-typed objects (same type and Authority kind), or an envelope
        # object whose attribute holds an ordered sequence of values, can be
        # indexed per iteration -- a script, not a goal or a policy.
        # Repair round 9: judged over EVERY object episode.start declares (any
        # type, any qualifier), not only its Objective/Authority members; an
        # attribute key outside the profile's closed envelope vocabulary for
        # the object's type is a key-indexed script (K6), fail closed.
        env_keys: Mapping[str, Any] = profile["failClosedProvenance"][
            "envelopeAttributes"
        ]
        self.indexed: dict[str, frozenset[str]] = {}
        for ep, members in self.declared.items():
            family: dict[tuple[str, Any], list[str]] = defaultdict(list)
            for o in members:
                family[(self.otype[o], self.oattr[o].get("kind"))].append(o)
            self.indexed[ep] = frozenset(
                o
                for o in members
                if len(family[(self.otype[o], self.oattr[o].get("kind"))]) > 1
                or any(n > 1 for n in self.values.get(o, {}).values())
                or set(self.values.get(o, {})) - set(env_keys.get(self.otype[o], ()))
            )
        # Repair round 9 (P3 invariant, whole episode): every post-epoch machine
        # event of one activity that cites envelope objects, under any
        # qualifier but ``episode``, must cite the same set. An envelope object
        # cited by some occurrences of an activity and not by others is
        # iteration-indexed decision state (K1: step-n into actuate[n]; K4b:
        # step-n under ``evidence`` on workorder.issue[n]).
        cites: dict[tuple[str, str], list[frozenset[str]]] = defaultdict(list)
        for e in self.events:
            ep = self.episode[e.id]
            if e.activity == _HUMAN or self.pos[e.id] <= self.pos[self.start[ep]]:
                continue
            cited = frozenset(
                o
                for q, o in self.links[e.id]
                if q != "episode" and o in self.declared[ep]
            )
            if cited:
                cites[(ep, e.activity)].append(cited)
        self.varying: dict[str, frozenset[str]] = {ep: frozenset() for ep in self.start}
        for (ep, _a), sets in cites.items():
            self.varying[ep] = self.varying[ep] | (
                frozenset().union(*sets) - frozenset.intersection(*sets)
            )
        # What P1 exempts as envelope state: frozen, and (P3) unindexed and
        # invariant.
        self.p1_exempt: dict[str, frozenset[str]] = {
            ep: frozenset(
                o
                for o in self.frozen[ep]
                if "P3" not in _LAWS
                or (o not in self.indexed[ep] and o not in self.varying[ep])
            )
            for ep in self.start
        }
        self.envelope_state: dict[str, frozenset[str]] = {
            ep: frozenset(
                o
                for o in members
                if ("P1" not in _LAWS or o in self.frozen[ep])
                and (
                    "P3" not in _LAWS
                    or (o not in self.indexed[ep] and o not in self.varying[ep])
                )
            )
            for ep, members in declared_state.items()
        }

        self.preds: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self.children: dict[str, list[str]] = defaultdict(list)
        self.exogenous: dict[str, list[str]] = defaultdict(list)
        for e in self.events:
            for q, o in self.links[e.id]:
                if q not in causal:
                    continue
                ps = self.producers.get(o)
                if not ps:
                    self.exogenous[e.id].append(o)
                    continue
                p = ps[0]
                if self.pos[p] >= self.pos[e.id]:
                    _refuse(
                        "CAUSALITY_VIOLATION",
                        f"event {e.id} consumes {o} produced by later/same event {p}",
                    )
                if self.episode[p] != self.episode[e.id]:
                    # Repair round 3 (C2): each episode has its own epoch t0, so a
                    # causal flow across episodes has no single epoch to judge a
                    # human cause against. Refuse rather than guess.
                    _refuse(
                        "CROSS_EPISODE_CAUSALITY",
                        f"event {e.id} (episode {self.episode[e.id]}) consumes {o} "
                        f"produced by {p} (episode {self.episode[p]})",
                        "R_missing_authority",
                        "AUTHORITY_FAILURE",
                    )
                self.preds[e.id].append((p, o))
                if e.id not in self.children[p]:
                    self.children[p].append(e.id)

        allowed_pre = set(profile["humanPreEpochAllowedOutputTypes"])
        self.allowed_pre = allowed_pre
        self.o2o: dict[str, list[tuple[str, str]]] = defaultdict(list)
        taint = set(profile["o2oHumanTaint"]["qualifiers"])
        for link in log.object_object_links:
            if (link.qualifier or "") in taint:
                self.o2o[link.source_id].append((link.qualifier or "", link.target_id))
        self._o2o_human_cache: dict[tuple[str, str], str | None] = {}
        # Repair round 8 (P2): O2O components, both directions, every profile
        # qualifier, no hop bound and no type exemption.
        parent: dict[str, str] = {o: o for o in self.otype}

        def root(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for link in log.object_object_links:
            a, b = root(link.source_id), root(link.target_id)
            if a != b:
                parent[max(a, b)] = min(a, b)
        self.component: dict[str, list[str]] = defaultdict(list)
        for o in sorted(self.otype):
            self.component[root(o)].append(o)
        self.comp_of = {o: root(o) for o in self.otype}
        self.human_edges: list[tuple[str, str, str]] = []
        # ``human[e]``: e is a post-epoch human act, or has a *direct* human
        # causal in-edge. Deliberately not transitive *after* the epoch: one
        # human act does not poison every later iteration; each iteration's own
        # segment is judged. Before the epoch taint is transitive (``laundered``).
        self.human: dict[str, bool] = {}
        self.post: dict[str, bool] = {}
        for e in self.events:
            self.post[e.id] = self.pos[e.id] > self.pos[self.start[self.episode[e.id]]]
        # Repair round 2 (B1): a human act touches every object it links, under
        # any qualifier -- not only what it ``output``s. ``touches[o]`` lists all
        # such human events in log order. Whether a touch is a human *cause* is
        # decided relative to the CONSUMER (repair round 3, C2), never relative
        # to the human event's own episode: see :meth:`unlawful_touch`.
        exempt = set(profile["humanTouch"]["exemptQualifiers"])
        self.touches: dict[str, list[str]] = defaultdict(list)
        for e in self.events:
            if e.activity != _HUMAN:
                continue
            for q, o in self.links[e.id]:
                if q not in exempt and e.id not in self.touches[o]:
                    self.touches[o].append(e.id)
        # Repair round 4 (C9): the lawful pre-epoch channel (Objective,
        # Authority) is lawful only while no post-epoch hand reaches it. A
        # human act that outputs, modifies or links such an object -- directly
        # under any qualifier but ``episode``, or over one O2O hop from any
        # object it links (repair round 5: any number of O2O hops in either
        # direction, i.e. the whole O2O component) -- opens a human next-action
        # channel through it from
        # that act on (judged against each consumer's epoch in
        # :meth:`authority_channel`). A machine event that outputs an
        # ``Authority`` after its epoch is the same channel unless it consumes
        # the pre-declared envelope (an Authority granted at its episode's
        # ``episode.start``); if it does, it inherits the envelope's channel.
        # ``channel[o]`` lists the opening events in log order.
        o2o_any: dict[str, set[str]] = defaultdict(set)
        for link in log.object_object_links:
            o2o_any[link.source_id].add(link.target_id)
            o2o_any[link.target_id].add(link.source_id)
        self.channel: dict[str, list[str]] = defaultdict(list)
        envelope = {
            ep: {
                o
                for q, o in self.links[s]
                if q in ("input", "originAuthority")
                and self.otype.get(o) == "Authority"
            }
            for ep, s in self.start.items()
        }
        for e in self.events:
            eid = e.id
            opened: set[str] = set()
            if e.activity == _HUMAN:
                for q, o in self.links[eid]:
                    if q == "episode":
                        continue
                    seen_o2o = {o}
                    frontier = deque([o])
                    while frontier:
                        x = frontier.popleft()
                        if self.otype.get(x) in allowed_pre:
                            opened.add(x)
                        for y in sorted(o2o_any.get(x, ())):
                            if y not in seen_o2o:
                                seen_o2o.add(y)
                                frontier.append(y)
                for x in sorted(opened):
                    if eid not in self.channel[x]:
                        self.channel[x].append(eid)
                continue
            if not self.post[eid]:
                continue
            granted_out = [
                o
                for q, o in self.links[eid]
                if q in producing and self.otype[o] == "Authority"
            ]
            if not granted_out:
                continue
            via = [
                o
                for q, o in self.links[eid]
                if q in causal and o in envelope[self.episode[eid]]
            ]
            origins = (
                [h for o in via for h in self.channel.get(o, ()) if h != eid]
                if via
                else [eid]
            )
            for x in granted_out:
                for h in origins:
                    if h not in self.channel[x]:
                        self.channel[x].append(h)
        # Repair round 3 (C1): human-touch taint propagates transitively through
        # machine events that run before their episode's epoch. A pre-epoch
        # machine hop that consumes a human-authored object outside the lawful
        # Objective/Authority channel (or a foreign/post-epoch human's object)
        # yields outputs that carry that human origin, so one hop cannot launder
        # a human script for every iteration into an "autonomous" loop.
        # ``laundered[o]`` = the human events o transitively derives from.
        self.laundered: dict[str, list[str]] = defaultdict(list)
        for e in self.events:
            eid = e.id
            if self.post[eid] or e.activity == _HUMAN:
                continue
            origins: list[str] = []
            for q, o in self.links[eid]:
                if q not in causal:
                    continue
                h = self.unlawful_touch(o, eid)
                if h is not None and h not in origins:
                    origins.append(h)
                for h2 in self.laundered.get(o, ()):
                    if h2 not in origins:
                        origins.append(h2)
            if not origins:
                continue
            for q, x in self.links[eid]:
                if q in producing:
                    for h in origins:
                        if h not in self.laundered[x]:
                            self.laundered[x].append(h)
        for e in self.events:
            eid = e.id
            if not self.post[eid]:
                self.human[eid] = False
                continue
            hit = e.activity == _HUMAN
            direct = {p for p, _ in self.preds[eid] if self.act[p] == _HUMAN}
            for q, o in self.links[eid]:
                if q not in causal:
                    continue
                h = self.unlawful_touch(o, eid)
                if h is not None and h not in direct:
                    self.human_edges.append((f"<touch:{h}>", eid, o))
                    hit = True
                for h2 in self.laundered.get(o, ()):
                    if self.pos[h2] < self.pos[eid]:
                        self.human_edges.append((f"<laundered:{h2}>", eid, o))
                        hit = True
                        break
            for p, o in self.preds[eid]:
                if self.act[p] == _HUMAN:
                    outputs_ok = all(
                        self.otype[x] in allowed_pre
                        for q, x in self.links[p]
                        if q == "output"
                    )
                    if self.post_for(p, eid) or not outputs_ok:
                        self.human_edges.append((p, eid, o))
                        hit = True
            for o in self.exogenous[eid]:
                if self.otype[o] == "Human" or self.oattr[o].get("origin") == "human":
                    self.human_edges.append(("<exogenous>", eid, o))
                    hit = True
            for q, o in self.links[eid]:
                if q not in causal:
                    continue
                via = self.o2o_human(o, eid)
                if via is not None:
                    self.human_edges.append((f"<o2o:{via}>", eid, o))
                    hit = True
            if e.activity != _HUMAN:
                for q, o in self.links[eid]:
                    if q == "originAuthority" and self.otype[o] == "Human":
                        self.human_edges.append(("<originAuthority>", eid, o))
                        hit = True
                # Repair round 4 (C9): citing an Authority/Objective whose
                # channel a post-epoch hand opened is a human cause.
                for q, o in self.links[eid]:
                    if q not in ("originAuthority", "input", "cause"):
                        continue
                    h = self.authority_channel(o, eid)
                    if h is not None:
                        self.human_edges.append((f"<authority:{h}>", eid, o))
                        hit = True
            if not hit and "P2" in _LAWS:
                taint = self.p2_taint(eid)
                if taint is not None:
                    self.human_edges.append((f"<p2:{taint[0]}>", eid, taint[1]))
                    hit = True
            self.human[eid] = hit

        for e in self.events:
            if e.activity != _WORKORDER:
                continue
            start = self.start[self.episode[e.id]]
            granted = {
                o
                for q, o in self.links[start]
                if q in ("input", "originAuthority") and self.otype[o] == "Authority"
            }
            for q, o in self.links[e.id]:
                if (
                    q == "originAuthority"
                    and self.otype[o] == "Authority"
                    and o not in granted
                ):
                    _refuse(
                        "FORGED_ORIGIN_AUTHORITY",
                        f"{e.id} originAuthority {o} not granted at {start}",
                        "R_missing_authority",
                        "AUTHORITY_FAILURE",
                    )

    def p1_unattributed(self, eid: str) -> list[tuple[str, str, str]]:
        """P1 closed world: every object a post-epoch machine event links.

        Under any qualifier except its own ``output`` (or an actuation's
        ``consequence``), the object must be (i) output by a machine event of
        the same episode after t0 and strictly earlier in time, or (ii) frozen
        envelope state. Human objects, and objects a human act outputs after
        t0 or in another episode, are P2's jurisdiction; a pre-epoch human
        output that episode.start does not declare is unattributed here.
        """
        ep = self.episode[eid]
        start = self.start[ep]
        if self.act[eid] == _HUMAN or self.pos[eid] <= self.pos[start]:
            return []
        bad: list[tuple[str, str, str]] = []
        for q, o in self.links[eid]:
            if q == "output" or (
                q == "consequence" and self.act[eid] in self.actuations
            ):
                continue
            if self.otype[o] == "Human":
                continue
            ps = self.producers.get(o)
            if (
                ps
                and self.act[ps[0]] == _HUMAN
                and (self.pos[ps[0]] > self.pos[start] or self.episode[ps[0]] != ep)
            ):
                continue
            if o in self.p1_exempt[ep]:
                continue
            if o in self.frozen[ep]:
                why = (
                    "envelope object indexed per iteration (same-typed family, "
                    "multi-valued or out-of-vocabulary attribute)"
                    if o in self.indexed[ep]
                    else "envelope object cited by some occurrences of "
                    f"{self.act[eid]} but not all (iteration-indexed)"
                )
            elif not ps:
                why = "no producer and not frozen envelope state"
            else:
                p = ps[0]
                if self.episode[p] != ep:
                    why = f"produced by {p} of episode {self.episode[p]}"
                elif self.pos[p] <= self.pos[start]:
                    why = f"produced before t0 by {p} but not frozen envelope state"
                elif self.ts[p] >= self.ts[eid]:
                    why = f"producer {p} is not strictly earlier in time"
                elif (ch := self.unattributed_change(o)) is not None:
                    why = (
                        f"attribute {ch[0]!r} value timed {ch[1]} has no producing "
                        f"event ({p} created {o} at {self.ts[p]})"
                    )
                else:
                    continue
            bad.append((q, o, why))
        return bad

    def unattributed_change(self, o: str) -> tuple[str, int] | None:
        """Repair round 9: the first OCEL ``ObjectChange`` on a non-envelope
        object that no event attributes -- i.e. not timed exactly at the
        object's post-epoch machine producer (which set it on creation)."""
        for attr, t in self.changes.get(o, ()):
            if not self.change_attributed(o, t):
                return attr, t
        return None

    def change_attributed(self, o: str, t: int) -> bool:
        """A value timed ``t`` on ``o`` is set by its post-epoch machine producer."""
        ps = self.producers.get(o)
        return bool(
            ps
            and self.act[ps[0]] != _HUMAN
            and self.post[ps[0]]
            and t == self.ts[ps[0]]
        )

    def p2_taint(self, eid: str) -> tuple[str, str] | None:
        """P2: the first Human contact of post-epoch event ``eid``, qualifier-agnostic.

        Any object ``eid`` links (any qualifier but ``episode``) that is a Human,
        is linked by a human act after its epoch (or of another episode) no
        later than ``eid``, carries an attribute value timed with a human act
        after t0, or shares an O2O component (either direction, any depth, any
        type) with any of those.
        """
        ep = self.episode[eid]
        start = self.start[ep]
        if self.pos[eid] <= self.pos[start]:
            return None
        t0, te = self.ts[start], self.ts[eid]
        first_human = self.first_post_human.get(ep)

        def human_contact(m: str) -> str | None:
            if self.otype[m] == "Human" or self.oattr[m].get("origin") == "human":
                return f"human-object:{m}"
            for h in self.touch_any.get(m, ()):
                if (
                    h != eid
                    and self.ts[h] <= te
                    and (self.episode[h] != ep or self.pos[h] > self.pos[start])
                ):
                    return f"touch:{h}"
            for attr, t in self.changes.get(m, ()):
                if t0 < t <= te and t in self.human_ts:
                    return f"cotimed-attribute:{m}.{attr}"
            # Repair round 9 (K8): an attribute value no event attributes,
            # timed at or after a post-epoch (or foreign) human act, is a human
            # hand on the object, whatever the nanosecond offset.
            if m not in self.frozen[ep] and first_human is not None:
                for attr, t in self.changes.get(m, ()):
                    if (
                        first_human <= t <= te
                        and t > t0
                        and not self.change_attributed(m, t)
                    ):
                        return f"attribute-after-human:{m}.{attr}"
            return None

        for q, o in self.links[eid]:
            if q == "episode":
                continue
            for m in [o, *(x for x in self.component[self.comp_of[o]] if x != o)]:
                why = human_contact(m)
                if why is not None:
                    return why, o
        return None

    def post_for(self, h: str, consumer: str) -> bool:
        """Is event ``h`` after the epoch of ``consumer``'s episode (repair round 3, C2)?"""
        return self.pos[h] > self.pos[self.start[self.episode[consumer]]]

    def unlawful_touch(self, o: str, consumer: str) -> str | None:
        """The earliest human event whose touch on ``o`` is a human cause for ``consumer``.

        A touch is lawful only when the human act is in the consumer's own
        episode, strictly before that episode's epoch, and ``o`` is on the lawful
        pre-epoch channel (``Objective``, ``Authority``). A human act of another
        episode, or after the consumer's epoch, is never lawful.
        """
        for h in self.touches.get(o, ()):
            if h == consumer or self.pos[h] >= self.pos[consumer]:
                continue
            lawful = (
                self.episode[h] == self.episode[consumer]
                and not self.post_for(h, consumer)
                and self.otype[o] in self.allowed_pre
            )
            if not lawful:
                return h
        return None

    def authority_channel(self, o: str, consumer: str) -> str | None:
        """The earliest event that opened a post-epoch channel through ``o`` for ``consumer``.

        Repair round 4 (C9): a human act counts when it is after ``consumer``'s
        epoch or in another episode; a machine grant (an ``Authority`` output
        after ``t0`` without the pre-declared envelope) counts when it is after
        ``consumer``'s epoch. Only acts strictly before ``consumer`` count.
        """
        for h in self.channel.get(o, ()):
            if h == consumer or self.pos[h] >= self.pos[consumer]:
                continue
            if self.act[h] == _HUMAN and self.episode[h] != self.episode[consumer]:
                return h
            if self.post_for(h, consumer):
                return h
        return None

    def is_human_object(self, o: str, consumer: str) -> bool:
        return (
            self.otype[o] == "Human"
            or self.oattr[o].get("origin") == "human"
            or self.unlawful_touch(o, consumer) is not None
            or self.authority_channel(o, consumer) is not None
            or any(self.pos[h] < self.pos[consumer] for h in self.laundered.get(o, ()))
        )

    def o2o_human(self, obj: str, consumer: str) -> str | None:
        """The Human-side object ``obj`` reaches over O2O links, or ``None``.

        Traversal does not enter the lawful pre-epoch channel (``Objective``,
        ``Authority``): those are human-originated by design and admitted at t0
        -- unless the channel object was itself touched unlawfully relative to
        ``consumer`` (repair round 3), in which case it is the human side.
        A consumed object that *is* of such a type is likewise not tainted.
        """
        key = (obj, consumer)
        if key in self._o2o_human_cache:
            return self._o2o_human_cache[key]
        found: str | None = None
        if self.otype[obj] not in self.allowed_pre:
            seen = {obj}
            queue = deque(t for _, t in self.o2o[obj])
            while queue and found is None:
                n = queue.popleft()
                if n in seen or n not in self.otype:
                    continue
                seen.add(n)
                if self.is_human_object(n, consumer):
                    found = n
                elif self.otype[n] not in self.allowed_pre:
                    queue.extend(t for _, t in self.o2o[n])
        self._o2o_human_cache[key] = found
        return found

    def objects(self, eid: str, qualifier: str) -> list[str]:
        return [o for q, o in self.links[eid] if q == qualifier]

    def descend(
        self, eid: str, stop: str | None = None, *, machine_only: bool = False
    ) -> list[str]:
        """Events reachable from ``eid``; nodes of activity ``stop`` are reached, not expanded.

        ``machine_only`` refuses to traverse any event that is a human act or has
        a direct human causal in-edge, so a path through a human is not a path.
        """
        seen: set[str] = set()
        order: list[str] = []
        queue = deque(self.children[eid])
        while queue:
            n = queue.popleft()
            if n in seen:
                continue
            seen.add(n)
            if machine_only and self.human[n]:
                continue
            order.append(n)
            if stop is not None and self.act[n] == stop:
                continue
            queue.extend(self.children[n])
        return order

    def ascend(self, eid: str, stop: Iterable[str] = ()) -> list[str]:
        """Causal ancestors of ``eid``; nodes whose activity is in ``stop`` are reached, not expanded."""
        stops = {stop} if isinstance(stop, str) else set(stop)
        seen: set[str] = set()
        order: list[str] = []
        queue = deque(p for p, _ in self.preds[eid])
        while queue:
            n = queue.popleft()
            if n in seen:
                continue
            seen.add(n)
            order.append(n)
            if self.act[n] in stops:
                continue
            queue.extend(p for p, _ in self.preds[n])
        return order


def _episode_report(g: _Graph, ep: str, profile: Mapping[str, Any]) -> dict[str, Any]:
    events = [e.id for e in g.events if g.episode[e.id] == ep]
    in_ep = set(events)
    post = [e for e in events if g.post[e]]
    start = g.start[ep]

    workorders = [e for e in post if g.act[e] == _WORKORDER]
    segment_stops = (_REOBSERVE, "observe", _START, _WORKORDER)

    def iteration_human(w: str) -> bool:
        return g.human[w] or any(g.human[a] for a in g.ascend(w, stop=segment_stops))

    def iteration_exogenous(w: str) -> list[str]:
        # observe/reobserve legitimately read the world; any other post-epoch
        # input with no producer in the log is an unattributed cause of w.
        # Inputs already attributed to a Human are counted as human edges instead.
        return sorted(
            {
                o
                for a in [w, *g.ascend(w, stop=segment_stops)]
                if g.post[a] and g.act[a] not in ("observe", _REOBSERVE)
                for o in g.exogenous[a]
                if not g.is_human_object(o, a) and g.o2o_human(o, a) is None
            }
        )

    # Repair round 8 (P1 closed world): every post-epoch machine event of the
    # episode whose links are not attributed (produced by an earlier machine
    # event of this episode after t0, or frozen envelope state).
    p1_events = (
        {e: bad for e in post if (bad := g.p1_unattributed(e))} if "P1" in _LAWS else {}
    )

    def p1_cone(w: str) -> list[str]:
        return sorted(
            {o for a in [w, *g.ascend(w)] if a in p1_events for _, o, _ in p1_events[a]}
        )

    unattributed = {
        w: sorted(set(iteration_exogenous(w)) | set(p1_cone(w))) for w in workorders
    }
    self_generated = [
        w for w in workorders if not iteration_human(w) and not unattributed[w]
    ]
    sg = set(self_generated)

    def fresh_consequences(r: str, downstream: set[str]) -> list[str]:
        segment = set(g.ascend(r, stop=segment_stops))
        return [
            c
            for c in g.objects(r, "consequence")
            if (ps := g.producers.get(c))
            and g.act[ps[0]] in g.actuations
            and ps[0] in downstream
            and ps[0] in segment
        ]

    # Repair round 4 (B4): the Subject that is current at each log position
    # (the episode.start subject, then each commit/merge output Subject).
    subject_timeline: list[tuple[int, str]] = [
        (g.pos[start], o)
        for o in g.objects(start, "subject")
        if g.otype[o] == "Subject"
    ]
    for e in events:
        if g.act[e] in ("commit", "merge"):
            subject_timeline.extend(
                (g.pos[e], o) for o in g.objects(e, "output") if g.otype[o] == "Subject"
            )

    def current_subject(at: int) -> str | None:
        cur = None
        for p, o in subject_timeline:
            if p < at:
                cur = o
        return cur

    episode_receipts = [e for e in events if g.act[e] == _RECEIPT]

    def stale_reobserve(r: str, o: str, w2: str) -> str | None:
        """Why ``receipt r -> reobserve o -> workorder w2`` is not a fresh transition, or None."""
        if g.pos[o] <= g.pos[r] or not any(p == r for p, _ in g.preds[o]):
            return f"{o} does not consume {r}'s output strictly after it"
        if "P3" in _LAWS and g.ts[o] <= g.ts[r]:
            return f"{o} is not strictly later in time than {r} (timestamp-only order)"
        later = [x for x in episode_receipts if g.pos[r] < g.pos[x] < g.pos[w2]]
        if later:
            return f"{later[0]} persisted before {w2} but {o} observes only {r}"
        segment = g.ascend(w2, stop=segment_stops)
        older = [
            a
            for a in segment
            if g.act[a] in ("observe", _REOBSERVE) and g.pos[a] < g.pos[r]
        ]
        if older:
            return f"{w2} reuses observation {older[0]} older than {r}"
        # Repair round 5 (B4'): the segment ascent stops AT the reobserve, so
        # its own inputs, and any non-observe producer of older state, were
        # never inspected. Walk the full causal cone of w2 back to r: every
        # consumed object must be r's output, produced strictly after r, or
        # part of the pre-declared envelope (whose post-epoch misuse C9
        # judges). Repair round 6 (B4''): the exemption is by provenance --
        # episode.start must consume the object -- never by type, so an
        # Objective/Authority minted as per-iteration state is judged by its
        # producer's position like any other state.
        envelope_state = g.envelope_state[ep]
        rooted = rooted_at(r)
        # Repair round 8 (P3): the cone has two roots. Hops between receipt[n]
        # and reobserve[n+1] descend from receipt[n]; every other hop of the
        # cone of workorder[n+1] descends from reobserve[n+1] itself.
        before_o = set(g.ascend(o))
        after_o = rooted_at(o) | {o}
        used = envelope_used.setdefault((r, w2), set())
        unrooted: str | None = None
        seen_cone: set[str] = set()
        cone = deque([w2])
        while cone:
            a = cone.popleft()
            if a in seen_cone:
                continue
            seen_cone.add(a)
            # Repair round 7 (B4''' a): a rooted cone -- every hop after r must
            # itself descend from r, or it decided from state r never touched.
            # The one exception is an envelope derivation: a machine event whose
            # every causal input is envelope state and whose every output is an
            # Objective/Authority (a lease derived from the granted policy).
            if (
                "P3" in _LAWS
                and unrooted is None
                and a not in (rooted if a in before_o else after_o)
                and not (
                    g.preds[a]
                    and all(x in envelope_state for _, x in g.preds[a])
                    and all(
                        g.otype.get(x) in g.allowed_pre for x in g.objects(a, "output")
                    )
                )
            ):
                unrooted = a
            # B4''' b: what the cone cites of the envelope, including the
            # non-causal originAuthority grant, is compared across transitions.
            used.update(
                x
                for q, x in g.links[a]
                if q in ("input", "cause", "originAuthority") and x in envelope_state
            )
            for p, x in g.preds[a]:
                if "P3" in _LAWS and g.ts[p] >= g.ts[a]:
                    return (
                        f"{a} consumes {x} from {p} at an equal or later timestamp: "
                        "no strict causal order"
                    )
                if p == r:
                    continue
                if g.pos[p] > g.pos[r]:
                    cone.append(p)
                elif x not in envelope_state:
                    return (
                        f"{a} consumes {x} produced by {p}, older than {r}; "
                        f"{w2} does not act on the state {r} left"
                    )
        if unrooted is not None:
            return (
                f"{unrooted} in the cone of {w2} is not causally downstream of {r} "
                f"through {o}; {w2} does not act on the state {r} left"
            )
        for a in [w2, *segment]:
            if g.pos[a] <= g.pos[r]:
                continue
            cur = current_subject(g.pos[a])
            for q, x in g.links[a]:
                if (
                    q in ("input", "cause", "subject")
                    and g.otype[x] == "Subject"
                    and x != cur
                ):
                    return f"{a} reads Subject {x} superseded by {cur}"
        return None

    rooted_cache: dict[str, set[str]] = {}

    def rooted_at(r: str) -> set[str]:
        if r not in rooted_cache:
            rooted_cache[r] = set(g.descend(r))
        return rooted_cache[r]

    envelope_used: dict[tuple[str, str], set[str]] = {}
    stale_transitions: list[tuple[str, str, str, str, str]] = []
    candidates: list[tuple[str, str, str, str]] = []
    nxt: dict[str, set[str]] = defaultdict(set)
    closing_receipts: set[str] = set()
    unclosed_receipts: set[str] = set()
    for w in self_generated:
        downstream = g.descend(w, stop=_WORKORDER, machine_only=True)
        down = set(downstream)
        for r in downstream:
            if g.act[r] != _RECEIPT:
                continue
            if not fresh_consequences(r, down):
                unclosed_receipts.add(r)
                continue
            for o in g.children[r]:
                if g.act[o] != _REOBSERVE or g.human[o]:
                    continue
                reached = [o] + g.descend(o, stop=_WORKORDER, machine_only=True)
                for w2 in reached:
                    if g.act[w2] == _WORKORDER and w2 in sg and w2 != w and w2 in in_ep:
                        why = stale_reobserve(r, o, w2)
                        if why is not None:
                            stale_transitions.append((w, r, o, w2, why))
                            continue
                        candidates.append((w, r, o, w2))
    # Repair round 7 (B4''' b, kept as P3): the envelope is invariant across
    # the episode's transitions. An envelope object consumed in the cone of
    # some candidate transition but not of every one is per-iteration decision
    # state bound into episode.start to borrow the exemption: that transition
    # is stale. Repair round 8 replaces the r7 count bound (c) -- gamed by
    # inflating the candidate count (J3) -- with P3's structural clauses: the
    # envelope is not indexed (``_Graph.indexed``) and the transition relation
    # is a function (one reobserve[n+1] roots one workorder[n+1]).
    invariant: set[str] | None = None
    for _w, r, _o, w2 in candidates:
        used = envelope_used.get((r, w2), set())
        invariant = set(used) if invariant is None else invariant & used
    successors: dict[tuple[str, str], set[str]] = defaultdict(set)
    for _w, r, o, w2 in candidates:
        successors[(r, o)].add(w2)
    for w, r, o, w2 in candidates:
        varying = sorted(envelope_used.get((r, w2), set()) - (invariant or set()))
        if "P3" in _LAWS and len(successors[(r, o)]) > 1:
            stale_transitions.append(
                (
                    w,
                    r,
                    o,
                    w2,
                    f"{o} roots {len(successors[(r, o)])} work orders "
                    f"{sorted(successors[(r, o)])[:3]}: a forked next action is "
                    "not one transition",
                )
            )
            continue
        if "P3" in _LAWS and varying:
            stale_transitions.append(
                (
                    w,
                    r,
                    o,
                    w2,
                    f"{w2} decides from envelope object(s) {varying[:3]} that not "
                    f"every transition consumes: per-iteration state bound into "
                    f"{start}, not a goal or a policy",
                )
            )
            continue
        nxt[w].add(w2)
        closing_receipts.add(r)
    depth = {w: 0 for w in self_generated}
    back: dict[str, str | None] = {w: None for w in self_generated}
    for w in sorted(self_generated, key=g.pos.__getitem__):
        for w2 in nxt[w]:
            if depth[w] + 1 > depth[w2]:
                depth[w2] = depth[w] + 1
                back[w2] = w
    ald = max(depth.values(), default=0)
    chain: list[str] = []
    if self_generated and ald > 0:
        tip = min((w for w in self_generated if depth[w] == ald), key=g.pos.__getitem__)
        cur: str | None = tip
        while cur is not None:
            chain.append(cur)
            cur = back[cur]
        chain.reverse()
    gaps = [g.ts[b] - g.ts[a] for a, b in zip(chain, chain[1:])]
    gaps_sorted = sorted(gaps)
    closed_cycles = sum(len(v) for v in nxt.values())

    receipts = [e for e in post if g.act[e] == _RECEIPT]
    actuations = [e for e in events if g.act[e] in g.actuations]
    unreceipted = []
    for a in actuations:
        for c in g.objects(a, "consequence"):
            bound = any(
                g.act[r] == _RECEIPT
                and g.pos[r] > g.pos[a]
                and c in g.objects(r, "consequence")
                for r in events
            )
            if not bound:
                unreceipted.append(a)
                break
    orphans = []
    for r in [e for e in events if g.act[e] == _RECEIPT]:
        for c in g.objects(r, "consequence"):
            ps = g.producers.get(c) or []
            if not ps or g.act[ps[0]] not in g.actuations or g.pos[ps[0]] > g.pos[r]:
                orphans.append(r)
                break
    receipted_by: dict[str, list[str]] = defaultdict(list)
    out_of_segment: list[str] = []
    for r in [e for e in events if g.act[e] == _RECEIPT]:
        segment = set(g.ascend(r, stop=segment_stops))
        for c in g.objects(r, "consequence"):
            receipted_by[c].append(r)
            ps = g.producers.get(c) or []
            if ps and g.act[ps[0]] in g.actuations and ps[0] not in segment:
                if r not in out_of_segment:
                    out_of_segment.append(r)
    rereceipted = sorted(c for c, rs in receipted_by.items() if len(rs) > 1)
    by_key: dict[str, set[str]] = defaultdict(set)
    for a in actuations:
        for c in g.objects(a, "consequence"):
            by_key[str(g.oattr[c]["key"])].add(a)
    duplicates = sorted(k for k, acts in by_key.items() if len(acts) > 1)

    current = next(
        iter(o for o in g.objects(start, "subject") if g.otype[o] == "Subject"), None
    )
    initial_subject = g.oattr[current]["sha"] if current else None
    stale = []
    for e in events:
        if g.act[e] in ("commit", "merge"):
            for o in g.objects(e, "output"):
                if g.otype[o] == "Subject":
                    current = o
        if g.act[e] == _RECEIPT:
            for s in g.objects(e, "subject"):
                if g.otype[s] == "Subject" and s != current:
                    stale.append(e)

    unavailable = [e for e in post if g.act[e] == "provider.unavailable"]
    substituted = [
        u
        for u in unavailable
        if any(g.act[d] == "provider.replace" and not g.human[d] for d in g.descend(u))
    ]
    failures = [
        e for e in post if g.act[e] in ("execution.crash", "provider.unavailable")
    ]
    recovery = set(profile["recoveryActivities"])
    recovered = [
        f
        for f in failures
        if any(g.act[d] in recovery and not g.human[d] for d in g.descend(f))
    ]
    leakage = [
        w
        for w in workorders
        if not any(g.act[a] == "candidate.admit" for a in g.ascend(w, stop=_WORKORDER))
    ]
    uncaused = [a for a in actuations if not g.preds[a] and not g.exogenous[a]]
    # Repair round 2 (B3b): every DO needs a WorkOrder of its own episode
    # upstream (whose originAuthority admission already checked). An actuation
    # with none -- uncaused, or caused only by exogenous/unrelated objects --
    # is an unleased DO; ``uncaused`` is a subset and no longer a dead metric.
    unauthorized = [
        a
        for a in actuations
        if not any(
            g.act[x] == _WORKORDER and x in in_ep for x in g.ascend(a, stop=_WORKORDER)
        )
    ]
    exogenous_post = sorted(
        {
            o
            for e in post
            for o in g.exogenous[e]
            if g.otype[o] != "Human" and g.oattr[o].get("origin") != "human"
        }
    )
    human_edges = [h for h in g.human_edges if h[1] in in_ep]
    human_targets = {h[1] for h in human_edges}
    caused_post = [e for e in post if g.preds[e] or g.exogenous[e]]
    human_events = [e for e in events if g.act[e] == _HUMAN]

    metrics = {
        "HIR": _ratio(len(human_targets), len(caused_post)),
        "ALD": ald,
        "LCR": _ratio(len(closing_receipts), len(receipts)),
        "RR": _ratio(len(recovered), len(failures)),
        "UAR": _ratio(len(unreceipted), len(actuations)),
        "PSR": _ratio(len(substituted), len(unavailable)),
        "consecutive_self_generated_transitions": ald,
        "closed_loop_cycles": closed_cycles,
        "stale_reobserve_transitions": len(stale_transitions),
        "human_causal_edges_after_epoch": len(human_edges),
        "unreceipted_actuations": len(unreceipted),
        "actuations": len(actuations),
        "uncaused_actuations": len(uncaused),
        "unauthorized_actuations": len(unauthorized),
        "duplicate_consequences": len(duplicates),
        "orphan_receipts": len(orphans),
        "receipts_without_fresh_consequence": len(unclosed_receipts),
        "receipts_out_of_segment": len(out_of_segment),
        "consequences_receipted_more_than_once": len(rereceipted),
        "unattributed_cause_workorders": sum(1 for w in workorders if unattributed[w]),
        "unattributed_post_epoch_events": len(p1_events),
        "stale_subject_receipts": len(stale),
        "unknown_frontier_leakage": len(leakage),
        "workorders": len(workorders),
        "self_generated_workorders": len(self_generated),
        "receipts": len(receipts),
        "failures": len(failures),
        "provider_unavailable": len(unavailable),
        "exogenous_post_epoch_inputs": exogenous_post,
        "inter_iteration_ns": (
            {
                "min": gaps_sorted[0],
                "median": gaps_sorted[len(gaps_sorted) // 2],
                "max": gaps_sorted[-1],
            }
            if gaps_sorted
            else None
        ),
    }

    reasons: list[dict[str, str]] = []
    integrity: list[dict[str, str]] = []
    if unreceipted:
        integrity.append(
            _reason(
                "UNRECEIPTED_ACTUATION",
                "R_missing_consequence",
                "EVIDENCE_FAILURE",
                f"{len(unreceipted)}/{len(actuations)} actuations lack a receipt.persist "
                f"bound to their consequence: {sorted(unreceipted)[:8]}",
            )
        )
    if unauthorized:
        integrity.append(
            _reason(
                "UNAUTHORIZED_ACTUATION",
                "R_missing_authority",
                "AUTHORITY_FAILURE",
                f"{len(unauthorized)}/{len(actuations)} actuations have no "
                f"{_WORKORDER} upstream ({len(uncaused)} with no cause at all): "
                f"{sorted(unauthorized, key=g.pos.__getitem__)[:8]}",
            )
        )
    if orphans:
        integrity.append(
            _reason(
                "ORPHAN_RECEIPT",
                "R_missing_identity",
                "EVIDENCE_FAILURE",
                f"{sorted(orphans)[:8]}",
            )
        )
    if out_of_segment:
        integrity.append(
            _reason(
                "RECEIPT_CONSEQUENCE_OUT_OF_SEGMENT",
                "R_missing_consequence",
                "EVIDENCE_FAILURE",
                "receipts bind a consequence produced outside their own iteration "
                f"segment: {sorted(out_of_segment)[:8]}",
            )
        )
    if rereceipted:
        integrity.append(
            _reason(
                "CONSEQUENCE_RECEIPTED_TWICE",
                "R_missing_consequence",
                "EVIDENCE_FAILURE",
                f"one DO receipted by several receipts: {rereceipted[:8]}",
            )
        )
    if duplicates:
        integrity.append(
            _reason(
                "DUPLICATE_CONSEQUENCE",
                "mu_unlawful",
                "VERIFICATION_FAILURE",
                f"keys={duplicates[:8]}",
            )
        )
    if stale:
        integrity.append(
            _reason(
                "STALE_SUBJECT",
                "R_missing_identity",
                "SUBJECT_FAILURE",
                f"receipts bound to a superseded Subject: {sorted(stale)[:8]}",
            )
        )
    if unavailable and len(substituted) < len(unavailable):
        integrity.append(
            _reason(
                "PROVIDER_SUBSTITUTION_FAILED",
                "R_not_fed_back",
                "CAPABILITY_GAP",
                f"PSR={metrics['PSR']}: provider.unavailable without a machine-caused provider.replace",
            )
        )
    if failures and len(recovered) < len(failures):
        integrity.append(
            _reason(
                "SELF_RECOVERY_ABSENT",
                "R_not_fed_back",
                "CAPABILITY_GAP",
                f"RR={metrics['RR']}: failure without Recover|Replan|Substitute|TypedBlock",
            )
        )
    reasons.extend(integrity)
    unattributed_ws = sorted(
        (w for w in workorders if unattributed[w]), key=g.pos.__getitem__
    )
    p1_first = sorted(p1_events, key=g.pos.__getitem__)[:3]
    if unattributed_ws or p1_events:
        reasons.append(
            _reason(
                "UNATTRIBUTED_EXOGENOUS_CAUSE",
                "mu_on_O",
                "EVIDENCE_FAILURE",
                f"{len(unattributed_ws)} workorders are caused by post-epoch inputs with "
                f"no producer in the log: "
                f"{[[w, unattributed[w][:2]] for w in unattributed_ws[:4]]}; "
                f"{len(p1_events)} post-epoch events link unattributed objects (P1): "
                f"{[[e, [list(x) for x in p1_events[e][:2]]] for e in p1_first]}",
            )
        )
    if not actuations:
        reasons.append(
            _reason(
                "NO_ACTUATION",
                "admission_vacuous",
                "CAPABILITY_GAP",
                "the episode never actuates; a loop without DO cannot close",
            )
        )
    if human_edges:
        reasons.append(
            _reason(
                "HUMAN_CAUSALITY_AFTER_EPOCH",
                "R_not_fed_back",
                "AUTHORITY_FAILURE",
                f"{len(human_edges)} human causal edges after t0={start}: "
                f"{[list(h) for h in human_edges[:4]]}",
            )
        )
    if stale_transitions:
        reasons.append(
            _reason(
                "STALE_REOBSERVE",
                "R_not_fed_back",
                "SUBJECT_FAILURE",
                f"{len(stale_transitions)} receipt -> reobserve -> workorder transitions "
                "not counted (the next action does not observe the state receipt[n] "
                f"left): {[list(t) for t in stale_transitions[:3]]}",
            )
        )
    if closed_cycles == 0:
        reasons.append(
            _reason(
                "AUTOMATION_NOT_AUTONOMY",
                "R_not_fed_back",
                "CAPABILITY_GAP",
                "no receipt[n] -> reobserve[n+1] -> workorder[n+1] edge with a self-generated "
                "cause chain and a receipt binding a fresh in-iteration consequence "
                f"(workorders={len(workorders)}, receipts={len(receipts)}, "
                f"actuations={len(actuations)})",
            )
        )
    blocked = [
        g.eattr[e].get("reason")
        for e in events
        if g.act[e] == "goal.blocked" and not g.human[e]
    ]
    if integrity:
        klass = "FAILED"
    elif blocked:
        klass = (
            "BLOCKED_AUTHORITY" if blocked[0] == "authority" else "BLOCKED_INFORMATION"
        )
    elif human_edges:
        klass = "ASSISTED"
    elif closed_cycles == 0 or not actuations or stale_transitions or p1_events:
        # repair round 5: a loop with any stale transition is not AUTONOMOUS;
        # repair round 8 (P1): nor is one with any unattributed post-epoch link
        klass = "FAILED"
    else:
        klass = "AUTONOMOUS"
    return {
        "episode": ep,
        "epoch_event": start,
        "initial_subject_sha": initial_subject,
        "class": klass,
        "human_events_recorded": len(human_events),
        "metrics": metrics,
        "reasons": reasons,
    }


def _aggregate(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    def total(key: str) -> int:
        return sum(ep["metrics"][key] for ep in episodes)

    human = total("human_causal_edges_after_epoch")
    hirs = [ep["metrics"]["HIR"] for ep in episodes]
    return {
        "episodes": len(episodes),
        "ALD_max": max((ep["metrics"]["ALD"] for ep in episodes), default=0),
        # undefined (0/0) is never defaulted to 0: None propagates and fails the gate
        "HIR_max": None if not hirs or None in hirs else max(hirs),
        "UAR": _ratio(total("unreceipted_actuations"), total("actuations")),
        "actuations": total("actuations"),
        "human_causal_edges_after_epoch": human,
        "closed_loop_cycles": total("closed_loop_cycles"),
        "unreceipted_actuations": total("unreceipted_actuations"),
        "duplicate_consequences": total("duplicate_consequences"),
        "orphan_receipts": total("orphan_receipts"),
        "stale_subject_receipts": total("stale_subject_receipts"),
        "unauthorized_actuations": total("unauthorized_actuations"),
    }


# ── entry points ────────────────────────────────────────────────────────────


def _envelope_digests(document: Any, g: _Graph) -> dict[str, str]:
    """Per episode: sha256 of the canonical frozen envelope objects (r9 claim anchor)."""
    raw = {
        str(o.get("id")): o
        for o in (document.get("objects") or ())
        if isinstance(o, Mapping)
    }
    return {
        ep: "sha256:"
        + _sha256(
            canonical([raw[o] for o in sorted(g.frozen[ep]) if o in raw]).encode(
                "utf-8"
            )
        )
        for ep in sorted(g.start)
    }


def _seal(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt["receipt_digest"] = "sha256:" + _sha256(canonical(receipt).encode("utf-8"))
    return receipt


def evaluate_document(
    document: Any,
    *,
    log_sha256: str,
    profile: Mapping[str, Any] | None = None,
    court_subject_sha: str | None = None,
    log_locator: str | None = None,
    seal_report: Mapping[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Run ALOOP-001 over an already-parsed OCEL 2.0 document.

    ``seal_report`` is :func:`autofde_lab.aloop.seal.verify_seal`'s report, or
    ``None`` for an unsealed log (verdict ceiling
    ``CONSISTENT_UNDER_ASSUMED_COMPLETENESS``).
    """
    prof = profile if profile is not None else load_profile()
    threshold = prof["qualification"][COURT_ID]
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "court": COURT_ID,
        "court_version": COURT_VERSION,
        "court_source_sha256": _court_source_sha256(prof),
        "profile": prof["profile"],
        "profile_sha256": prof["_profile_sha256"],
        "court_subject_sha": court_subject_sha,
        "log": {"sha256": log_sha256, "locator": log_locator},
        "authority": "NONE (court verdict only; grants no DO authority)",
        "evidence_ceiling": (
            "OCEL is the flight recorder, not proof: this verdict holds only for the "
            "causal graph derivable from the admitted log bytes named above."
        ),
        "qualification_thresholds": threshold,
        "sealing": dict(seal_report)
        if seal_report is not None
        else {"profile": None, "sealed": False, "complete": None},
    }
    if seal_report is not None and seal_report.get("refusals"):
        receipt.update(
            {
                "verdict": "REFUSED",
                "exit_code": EXIT_REFUSED,
                "standing": "REFUSED",
                "rules_consistent": False,
                "refusals": list(seal_report["refusals"]),
                "episodes": [],
                "metrics": None,
                "log_subjects": [],
            }
        )
        return EXIT_REFUSED, _seal(receipt)
    try:
        log = _admit(document, prof)
        graph = _Graph(log, prof)
    except AloopRefusal as refusal:
        receipt.update(
            {
                "verdict": "REFUSED",
                "exit_code": EXIT_REFUSED,
                "standing": "REFUSED",
                "rules_consistent": False,
                "refusals": [refusal.as_json()],
                "episodes": [],
                "metrics": None,
                "log_subjects": [],
            }
        )
        return EXIT_REFUSED, _seal(receipt)

    receipt["log"].update({"events": len(log.events), "objects": len(log.objects)})
    episodes = [
        _episode_report(graph, ep, prof) for ep in sorted(set(graph.episode.values()))
    ]
    metrics = _aggregate(episodes)
    unmet: list[dict[str, str]] = []
    if metrics["ALD_max"] < threshold["min_consecutive_self_generated_transitions"]:
        unmet.append(
            _reason(
                "INSUFFICIENT_LOOP_DEPTH",
                "R_not_fed_back",
                "CAPABILITY_GAP",
                f"ALD={metrics['ALD_max']} < {threshold['min_consecutive_self_generated_transitions']}",
            )
        )
    if metrics["HIR_max"] is None:
        unmet.append(
            _reason(
                "HIR_UNDEFINED",
                "admission_vacuous",
                "EVIDENCE_FAILURE",
                "HIR is 0/0: no caused post-epoch event to measure",
            )
        )
    elif metrics["HIR_max"] != threshold["HIR"]:
        unmet.append(
            _reason(
                "HIR_NONZERO",
                "R_not_fed_back",
                "AUTHORITY_FAILURE",
                f"HIR={metrics['HIR_max']}",
            )
        )
    if metrics["actuations"] < threshold["min_actuations"]:
        unmet.append(
            _reason(
                "NO_ACTUATION",
                "admission_vacuous",
                "CAPABILITY_GAP",
                f"actuations={metrics['actuations']} < {threshold['min_actuations']}; "
                "UAR is undefined, not 0",
            )
        )
    elif metrics["UAR"] != threshold["UAR"]:
        unmet.append(
            _reason(
                "UAR_NONZERO",
                "R_missing_consequence",
                "EVIDENCE_FAILURE",
                f"UAR={metrics['UAR']}",
            )
        )
    for ep in episodes:
        if ep["class"] != "AUTONOMOUS":
            unmet.append(
                _reason(
                    f"EPISODE_{ep['class']}",
                    ep["reasons"][0]["broken_term"]
                    if ep["reasons"]
                    else "R_not_fed_back",
                    ep["reasons"][0]["failure_class"]
                    if ep["reasons"]
                    else "CAPABILITY_GAP",
                    f"episode {ep['episode']}",
                )
            )
    rules_consistent = not unmet
    witnessed = bool(
        seal_report is not None
        and seal_report.get("sealed") is True
        and seal_report.get("complete") is True
    )
    qualified = rules_consistent and witnessed
    envelopes = _envelope_digests(document, graph)
    envelope_sha = "sha256:" + _sha256(canonical(envelopes).encode("utf-8"))
    for ep in episodes:
        ep["rule_class"] = ep["class"]
        ep["envelope_sha256"] = envelopes.get(ep["episode"])
        if ep["class"] == "AUTONOMOUS" and not witnessed:
            # r9: AUTONOMOUS is a claim about absence (no human cause, nothing
            # omitted); an unsealed or unwitnessed log cannot carry it.
            ep["class"] = CONSISTENT
    if qualified:
        verdict, code, standing = "QUALIFIED", EXIT_QUALIFIED, "PARTIAL_ALIVE"
        claim = (
            "sealed+complete: every OCEL event is recorder-signed and "
            "hash-chained, every witnessed commit and post-t0 human message maps "
            "to exactly one sealed event, and every ALOOP-001 rule holds"
        )
    elif rules_consistent:
        verdict, code, standing = (
            CONSISTENT,
            EXIT_CONSISTENT_UNDER_ASSUMED_COMPLETENESS,
            "PARTIAL_ALIVE",
        )
        claim = (
            f"consistent under assumed completeness relative to envelope "
            f"{envelope_sha}: every ALOOP-001 rule holds over the log bytes, but "
            "the log is not "
            + (
                "complete against external witnesses"
                if seal_report is not None and seal_report.get("sealed")
                else "sealed"
            )
            + ", so the absence of human causation and of omitted events is "
            "assumed, not observed"
        )
    else:
        verdict, code, standing = "NOT_QUALIFIED", EXIT_NOT_QUALIFIED, "BLOCKED"
        claim = "typed failure: see unmet and episode reasons"
    receipt.update(
        {
            "verdict": verdict,
            "exit_code": code,
            "standing": standing,
            "rules_consistent": rules_consistent,
            "envelope_sha256": envelope_sha,
            "claim": claim,
            "standing_note": (
                "ALOOP-001 only; AUTONOMOUS_LOOP_ALIVE requires ALOOP-002..010 benchmark results"
            ),
            "refusals": [],
            "unmet": unmet,
            "episodes": episodes,
            "metrics": metrics,
            "log_subjects": sorted(
                {
                    ep["initial_subject_sha"]
                    for ep in episodes
                    if ep["initial_subject_sha"]
                }
            ),
        }
    )
    return code, _seal(receipt)


def evaluate_path(
    path: Path | str,
    *,
    profile_path: Path | None = None,
    court_subject_sha: str | None = None,
    log_locator: str | None = None,
    seal: Any = None,
) -> tuple[int, dict[str, Any]]:
    """Read an OCEL 2.0 JSON file from disk and run ALOOP-001 over its exact bytes.

    ``seal`` is an :class:`autofde_lab.aloop.seal.SealInputs` (sealed-recorder
    ledger + verification key + completeness witnesses) or ``None``.
    """
    raw = Path(path).read_bytes()
    digest = _sha256(raw)
    profile = load_profile(profile_path)
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        document = {"__malformed__": str(exc)}
    seal_report = None
    if seal is not None:
        from autofde_lab.aloop.seal import verify_seal

        seal_report = verify_seal(document, seal, raw)
    return evaluate_document(
        document,
        log_sha256=digest,
        profile=profile,
        court_subject_sha=court_subject_sha,
        log_locator=log_locator,
        seal_report=seal_report,
    )


def write_receipt(receipt: Mapping[str, Any], path: Path) -> None:
    """Persist a receipt as indented, key-sorted JSON with a trailing newline."""
    Path(path).write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


def iter_reasons(receipt: Mapping[str, Any]) -> Iterable[str]:
    """All typed codes in a receipt -- refusals, unmet thresholds, episode reasons."""
    for r in receipt.get("refusals") or ():
        yield r["code"]
    for r in receipt.get("unmet") or ():
        yield r["code"]
    for ep in receipt.get("episodes") or ():
        for r in ep["reasons"]:
            yield r["code"]
