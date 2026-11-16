"""Post-run projection: append-only store -> OCEL v2 -> pm4pytest.

The UI driver only clicks; nothing here is called from a click helper. The store holds only
events the reducer admitted (a refused append raises before writing), so a refused click can
never appear in the projection. Names come from payloads, never from literals in this file."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import store

# Payload field that mints an object, per event kind -> {field: object type}.
# Types for taxonomy come from the payload ("type"); doc/media types are structural.
_MINTS = {
    "entity": {"name": "entity", "dba": "dba"},
    "entity_doc": {"name": "doc"},
    "provider_doc": {"name": "doc"},
    "client": {"name": "client"},
    "site": {"name": "site"},
    "asset": {"name": "asset"},
    "coordinator": {"name": "coordinator"},
    "provider": {"name": "provider"},
    "work_order": {"name": "work_order"},
    "media": {"name": "media"},
}


def activity_of(ev: dict) -> str:
    if ev["kind"] == "media":
        return f"media:{ev['payload']['media_type']}"
    return ev["kind"]


def _minted(ev: dict) -> list[tuple[str, str]]:
    k, p = ev["kind"], ev["payload"]
    if k == "taxonomy":
        return [(p["name"], p["type"])]
    return [(p[f], t) for f, t in _MINTS.get(k, {}).items() if p.get(f)]


def _refs(p: dict, known: dict) -> list[tuple[str, str]]:
    """(field, object id) for every payload value naming an already-registered object."""
    out = []
    for f, v in p.items():
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, str) and x in known:
                out.append((f, x))
    return out


def _stamp(ts: float, prev):
    t = datetime.fromtimestamp(ts, tz=timezone.utc)
    if prev is not None and t <= prev:
        t = prev + timedelta(microseconds=1)  # strictly monotone: seq order is trace order
    return t


def replay_into_session(session, path=None) -> int:
    """Project every stored event into `session` (anything with register_object/emit_event:
    PM4PySession or ProcessTraceCollector). Returns number of events emitted."""
    known: dict[str, str] = {}
    prev, n = None, 0
    for ev in store.read(path):
        p = ev["payload"]
        minted = _minted(ev)
        rels = [{"objectId": o, "qualifier": f} for f, o in _refs(p, known) if o not in dict(minted)]
        for oid, otype in minted:
            session.register_object(oid, otype, {"avatar": ev["avatar"], "first_seq": ev["seq"]})
            known[oid] = otype
            rels.append({"objectId": oid, "qualifier": "created"})
        prev = _stamp(ev["ts"], prev)
        session.emit_event(f"e{ev['seq']}", activity_of(ev), timestamp=prev,
                           attributes={"avatar": ev["avatar"], "seq": ev["seq"]},
                           relationships=rels)
        n += 1
    return n


def trace(path=None) -> list[str]:
    return [activity_of(e) for e in store.read(path)]


def alphabet(path=None) -> set:
    return set(trace(path))


def bounded_transitions(activities) -> dict:
    """allowed_transitions for ConformanceSpec: any activity in the alphabet may follow any
    other; anything outside the alphabet is an FSM_INVALID_TRANSITION."""
    acts = sorted(activities)
    return {a: list(acts) for a in acts}


def write_sqlite(path_store, out_sqlite) -> Path:
    """Project the store into an OCEL v2 sqlite the pm4pytest CLI can judge."""
    from pm4pytest.ocel import ProcessTraceCollector
    c = ProcessTraceCollector()
    replay_into_session(c, path_store)
    return c.write_sqlite(Path(out_sqlite))
