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

The verdict is a pure function of (log bytes, profile bytes, court source):
the receipt carries no wall-clock value, so a cold replay is byte-identical.
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
    "AloopRefusal",
    "load_profile",
    "evaluate_document",
    "evaluate_path",
    "canonical",
]

COURT_ID = "ALOOP-001"
COURT_VERSION = "aloop-001/v26.9.25-r2"
RECEIPT_SCHEMA = "autofde-lab/aloop-court-receipt/v1"

EXIT_QUALIFIED = 0
EXIT_REFUSED = 2
EXIT_NOT_QUALIFIED = 3

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROFILE = REPO_ROOT / "schemas" / "aloop" / "ocel2-aloop-profile.json"

_HUMAN = "human.intervene"
_WORKORDER = "workorder.issue"
_RECEIPT = "receipt.persist"
_REOBSERVE = "reobserve"
_START = "episode.start"


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

        self.producers: dict[str, list[str]] = defaultdict(list)
        for e in self.events:
            for q, o in self.links[e.id]:
                if q in producing or (q == "consequence" and e.activity in actuations):
                    if e.id not in self.producers[o]:
                        self.producers[o].append(e.id)
        for o, ps in sorted(self.producers.items()):
            if len(ps) > 1 and self.otype[o] != "Consequence":
                _refuse("MULTIPLE_PRODUCERS", f"object {o} produced by {ps}")

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
        self._o2o_human_cache: dict[str, str | None] = {}
        self.human_edges: list[tuple[str, str, str]] = []
        # ``human[e]``: e is a post-epoch human act, or has a *direct* human
        # causal in-edge. Deliberately not transitive: one human act does not
        # poison every later iteration; each iteration's own segment is judged.
        self.human: dict[str, bool] = {}
        self.post: dict[str, bool] = {}
        for e in self.events:
            start_pos = self.pos[self.start[self.episode[e.id]]]
            self.post[e.id] = self.pos[e.id] > start_pos
        # Repair round 2 (B1): a human act taints every object it links, under
        # any qualifier -- not only what it ``output``s. Post-epoch: always;
        # pre-epoch: unless the object is on the lawful channel (Objective,
        # Authority). ``touched[o]`` is the earliest such human event.
        exempt = set(profile["humanTouch"]["exemptQualifiers"])
        self.touched: dict[str, str] = {}
        for e in self.events:
            if e.activity != _HUMAN:
                continue
            for q, o in self.links[e.id]:
                if q in exempt or o in self.touched:
                    continue
                if self.post[e.id] or self.otype[o] not in allowed_pre:
                    self.touched[o] = e.id
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
                h = self.touched.get(o)
                if (
                    h is not None
                    and h != eid
                    and h not in direct
                    and self.pos[h] < self.pos[eid]
                ):
                    self.human_edges.append((f"<touch:{h}>", eid, o))
                    hit = True
            for p, o in self.preds[eid]:
                if self.act[p] == _HUMAN:
                    outputs_ok = all(
                        self.otype[x] in allowed_pre
                        for q, x in self.links[p]
                        if q == "output"
                    )
                    if self.post[p] or not outputs_ok:
                        self.human_edges.append((p, eid, o))
                        hit = True
            for o in self.exogenous[eid]:
                if self.otype[o] == "Human" or self.oattr[o].get("origin") == "human":
                    self.human_edges.append(("<exogenous>", eid, o))
                    hit = True
            for q, o in self.links[eid]:
                if q not in causal:
                    continue
                via = self.o2o_human(o)
                if via is not None:
                    self.human_edges.append((f"<o2o:{via}>", eid, o))
                    hit = True
            if e.activity != _HUMAN:
                for q, o in self.links[eid]:
                    if q == "originAuthority" and self.otype[o] == "Human":
                        self.human_edges.append(("<originAuthority>", eid, o))
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

    def is_human_object(self, o: str) -> bool:
        return (
            self.otype[o] == "Human"
            or self.oattr[o].get("origin") == "human"
            or o in self.touched
        )

    def o2o_human(self, obj: str) -> str | None:
        """The Human-side object ``obj`` reaches over O2O links, or ``None``.

        Traversal does not enter the lawful pre-epoch channel (``Objective``,
        ``Authority``): those are human-originated by design and admitted at t0.
        A consumed object that *is* of such a type is likewise not tainted.
        """
        if obj in self._o2o_human_cache:
            return self._o2o_human_cache[obj]
        found: str | None = None
        if self.otype[obj] not in self.allowed_pre:
            seen = {obj}
            queue = deque(t for _, t in self.o2o[obj])
            while queue and found is None:
                n = queue.popleft()
                if n in seen or n not in self.otype:
                    continue
                seen.add(n)
                if self.is_human_object(n):
                    found = n
                elif self.otype[n] not in self.allowed_pre:
                    queue.extend(t for _, t in self.o2o[n])
        self._o2o_human_cache[obj] = found
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
                if not g.is_human_object(o) and g.o2o_human(o) is None
            }
        )

    unattributed = {w: iteration_exogenous(w) for w in workorders}
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
    if unattributed_ws:
        reasons.append(
            _reason(
                "UNATTRIBUTED_EXOGENOUS_CAUSE",
                "mu_on_O",
                "EVIDENCE_FAILURE",
                f"{len(unattributed_ws)} workorders are caused by post-epoch inputs with "
                f"no producer in the log: "
                f"{[[w, unattributed[w][:2]] for w in unattributed_ws[:4]]}",
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
    elif closed_cycles == 0 or not actuations:
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
) -> tuple[int, dict[str, Any]]:
    """Run ALOOP-001 over an already-parsed OCEL 2.0 document."""
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
    }
    try:
        log = _admit(document, prof)
        graph = _Graph(log, prof)
    except AloopRefusal as refusal:
        receipt.update(
            {
                "verdict": "REFUSED",
                "exit_code": EXIT_REFUSED,
                "standing": "REFUSED",
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
    qualified = not unmet
    receipt.update(
        {
            "verdict": "QUALIFIED" if qualified else "NOT_QUALIFIED",
            "exit_code": EXIT_QUALIFIED if qualified else EXIT_NOT_QUALIFIED,
            "standing": "PARTIAL_ALIVE" if qualified else "BLOCKED",
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
    return (EXIT_QUALIFIED if qualified else EXIT_NOT_QUALIFIED), _seal(receipt)


def evaluate_path(
    path: Path | str,
    *,
    profile_path: Path | None = None,
    court_subject_sha: str | None = None,
    log_locator: str | None = None,
) -> tuple[int, dict[str, Any]]:
    """Read an OCEL 2.0 JSON file from disk and run ALOOP-001 over its exact bytes."""
    raw = Path(path).read_bytes()
    digest = _sha256(raw)
    profile = load_profile(profile_path)
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        document = {"__malformed__": str(exc)}
    return evaluate_document(
        document,
        log_sha256=digest,
        profile=profile,
        court_subject_sha=court_subject_sha,
        log_locator=log_locator,
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
