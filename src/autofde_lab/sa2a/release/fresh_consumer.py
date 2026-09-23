"""Fresh-consumer standing verifier for the Episode 1 / Episode 2 pair (ARD §45, §22).

Ports the exact discipline of
`autofde_lab.hub.domain.gym_procedure.standalone_verifier` (this repo's own prior,
stronger-than-anything-else-in-sa2a fresh-consumer implementation, flagged by the
v26.9.17 gap audit as "the single strongest reuse candidate for closing PRD §6.22/
ARD §45") to the sa2a Episode/MachineExperience evidence: a real, SEPARATE PROCESS
(invoked via `subprocess.run([sys.executable, "-m", ...])`, never imported and called
in-process) that reads ONLY the durable JSON checkpoint + OCEL files
`Episode1Runner`/`Episode2Runner` already write to `state_dir`, and recomputes
standing from them alone.

This directly answers the audit's own finding against the ONE fresh-consumer
mechanism that already existed for sa2a:

    "ReplayCourt.verify_fresh_consumer_isolation only does in-process `del`-based
    reference severance and re-imports/re-instantiates the producer's own
    AuthorityBroker/ReplayEngine classes in the same interpreter... not a
    subprocess boundary."

`assert_no_runtime_imports()` below checks, not merely intends, that this module
never imported `autofde_lab.sa2a.episode` or `autofde_lab.sa2a.experience` --
combined with running as a genuinely separate OS process (so producer in-memory
state cannot leak even if some future edit added such an import elsewhere in this
process's call stack), this is a real process boundary, not merely an import
discipline.

Every recomputed field is read from the RAW JSON, never from a trusted boolean the
producer already computed -- `frontier_clean` in particular is RE-DERIVED from the
raw `intelligence_usage` counters and compared against the producer's own stored
value; a mismatch is itself reported as evidence, not silently trusted.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union, cast

#: Modules whose presence would mean this verifier is not independent.
FORBIDDEN_RUNTIME_MODULES: tuple[str, ...] = (
    "autofde_lab.sa2a.episode.episode1",
    "autofde_lab.sa2a.episode.episode2",
    "autofde_lab.sa2a.experience.compiler",
    "autofde_lab.sa2a.experience.admission",
    "autofde_lab.sa2a.experience.qualification",
)

REQUIRED_CHAIN: tuple[tuple[str, str], ...] = (
    (
        "episode1->experience",
        "did Episode 1 produce an ACTIVE MachineExperience for a real KnownRoute?",
    ),
    (
        "episode1_ocel->experience",
        "does Episode 1's own OCEL evidence relate that exact experience/route, not just the checkpoint's word for it?",
    ),
    (
        "episode2->same_route",
        "did Episode 2 resolve the SAME experience/route Episode 1 produced?",
    ),
    (
        "episode2_ocel->route",
        "does Episode 2's own OCEL evidence relate that exact route?",
    ),
    (
        "episode2->fresh_identity",
        "did Episode 2 use an actuation identity distinct from Episode 1's?",
    ),
    (
        "episode2->frontier_clean_recomputed",
        "does frontier_clean, RECOMPUTED from raw counters, match what Episode 2 claimed?",
    ),
    (
        "episode2->anti_vacuity",
        "did Episode 2's route genuinely execute and get independently verified, not merely classify KNOWN?",
    ),
)


@dataclass(frozen=True, slots=True)
class Edge:
    name: str
    question: str
    established: bool
    basis: str


@dataclass(frozen=True, slots=True)
class IndependentStanding:
    state_dir: str
    episode1_id: str
    episode2_id: str
    edges: tuple[Edge, ...]
    artifacts_seen: tuple[str, ...]
    artifacts_absent: tuple[str, ...]
    #: Hardening pass (2026-09-17): a file that EXISTS but fails to parse (truncated
    #: write from a crash mid-checkpoint, or genuine tampering) is a DIFFERENT failure
    #: class from one that never existed -- conflating them would let real corruption
    #: report as ordinary "not run yet" absence. Kept as its own tuple, not folded
    #: into `artifacts_absent`.
    artifacts_corrupt: tuple[str, ...] = ()

    def unestablished(self) -> list[str]:
        return [e.name for e in self.edges if not e.established]

    def verdict(self) -> str:
        if self.artifacts_corrupt:
            return f"UNKNOWN:ARTIFACTS_CORRUPT:{','.join(self.artifacts_corrupt)}"
        if self.artifacts_absent:
            return f"UNKNOWN:ARTIFACTS_ABSENT:{','.join(self.artifacts_absent)}"
        missing = self.unestablished()
        if missing:
            return f"UNKNOWN:CHAIN_INCOMPLETE:{','.join(missing)}"
        return "CONFORMANT_EVIDENCE_RECONSTRUCTED"

    def report(self) -> list[str]:
        return [
            f"{'OK ' if e.established else '-- '}{e.name}: {e.basis}"
            for e in self.edges
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_dir": self.state_dir,
            "episode1_id": self.episode1_id,
            "episode2_id": self.episode2_id,
            "verdict": self.verdict(),
            "edges": [
                {
                    "name": e.name,
                    "question": e.question,
                    "established": e.established,
                    "basis": e.basis,
                }
                for e in self.edges
            ],
            "artifacts_seen": list(self.artifacts_seen),
            "artifacts_absent": list(self.artifacts_absent),
            "artifacts_corrupt": list(self.artifacts_corrupt),
        }


class _Corrupt:
    """Sentinel: the file exists but its content could not be parsed as JSON."""


_CORRUPT = _Corrupt()


def _load_json(path: Path) -> Union[dict, _Corrupt, None]:
    """Returns the parsed dict, `_CORRUPT` if the file exists but fails to parse
    (truncated write, tampering, non-JSON content), or `None` if it doesn't exist.
    Never raises -- this verifier is the trust anchor and must degrade to a typed
    UNKNOWN verdict on any malformed input, never crash.
    """
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return _CORRUPT
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return _CORRUPT
    if not isinstance(data, dict):
        return _CORRUPT
    return data


def _ocel_event_objects(ocel: dict, activity: str) -> list[list[str]]:
    """Object ids referenced by every event of `activity` (real E2O links only).

    Mutation-hardening (2026-09-17): a malformed-but-valid-JSON OCEL file --
    `events` not a list, an individual event not a dict, `relationships` not a
    list, or an individual relationship not a dict -- must degrade to "this
    edge cannot be established" (an empty/short object list, which the caller's
    `any(...)` check correctly reads as no matching E2O link), never raise
    inside this module. This is the trust-anchor verifier; every non-conforming
    shape is skipped in place, not propagated as an exception. Confirmed live:
    before this guard, `events: "not-a-list"` and `relationships: "oops"` both
    raised `AttributeError: 'str' object has no attribute 'get'` out of
    `verify()` itself -- exactly the crash this module's own docstring
    (line ~128) says it must never do.
    """
    out: list[list[str]] = []
    events = ocel.get("events", []) or []
    if not isinstance(events, list):
        return out
    for event in events:
        if not isinstance(event, dict) or event.get("type") != activity:
            continue
        relationships = event.get("relationships", []) or []
        if not isinstance(relationships, list):
            relationships = []
        out.append(
            [r.get("objectId", "") for r in relationships if isinstance(r, dict)]
        )
    return out


def verify(state_dir: Path, episode1_id: str, episode2_id: str) -> IndependentStanding:
    """Reconstruct standing for one Episode1/Episode2 pair from durable artifacts alone."""
    paths = {
        "ep1_checkpoint": state_dir / f"{episode1_id}.json",
        "ep1_ocel": state_dir / f"{episode1_id}.ocel2.json",
        "ep2_checkpoint": state_dir / f"{episode2_id}.json",
        "ep2_ocel": state_dir / f"{episode2_id}.ocel2.json",
    }
    seen = [k for k, p in paths.items() if p.is_file()]
    absent = [k for k, p in paths.items() if not p.is_file()]
    if absent:
        return IndependentStanding(
            str(state_dir), episode1_id, episode2_id, (), tuple(seen), tuple(absent)
        )

    loaded = {k: _load_json(p) for k, p in paths.items()}
    corrupt = [k for k, v in loaded.items() if isinstance(v, _Corrupt)]
    if corrupt:
        return IndependentStanding(
            str(state_dir),
            episode1_id,
            episode2_id,
            (),
            tuple(seen),
            (),
            artifacts_corrupt=tuple(corrupt),
        )
    # Every value is now a real dict (or None, handled by `or {}` below) -- `corrupt`
    # being empty proves no `_Corrupt` sentinel survived, so this narrowing is safe.
    checkpoints = cast(Dict[str, Optional[dict]], loaded)

    ep1 = checkpoints["ep1_checkpoint"] or {}
    ep1_ocel = checkpoints["ep1_ocel"] or {}
    ep2 = checkpoints["ep2_checkpoint"] or {}
    ep2_ocel = checkpoints["ep2_ocel"] or {}

    results: list[Edge] = []

    def add(name: str, question: str, established: bool, basis: str) -> None:
        results.append(Edge(name, question, established, basis))

    ep1_experience_id = ep1.get("experience_id", "")
    ep1_route_id = ep1.get("known_route_id", "")
    ep1_active = (
        bool(ep1_experience_id)
        and bool(ep1_route_id)
        and ep1.get("classification") == "KNOWN"
    )
    add(
        "episode1->experience",
        REQUIRED_CHAIN[0][1],
        ep1_active,
        f"episode1.experience_id={ep1_experience_id!r} known_route_id={ep1_route_id!r} classification={ep1.get('classification')!r}",
    )

    ep1_ocel_objs = _ocel_event_objects(ep1_ocel, "Episode1Completed")
    ep1_ocel_binds = (
        any(episode1_id in objs and ep1_experience_id in objs for objs in ep1_ocel_objs)
        if ep1_experience_id
        else False
    )
    add(
        "episode1_ocel->experience",
        REQUIRED_CHAIN[1][1],
        ep1_ocel_binds,
        f"{len(ep1_ocel_objs)} Episode1Completed event(s); "
        f"{'an' if ep1_ocel_binds else 'no'} explicit event relates episode1_id and experience_id together",
    )

    ep2_experience_id = ep2.get("experience_id", "")
    ep2_route_id = ep2.get("known_route_id", "")
    same_route = (
        bool(ep1_active)
        and ep2_experience_id == ep1_experience_id
        and ep2_route_id == ep1_route_id
    )
    add(
        "episode2->same_route",
        REQUIRED_CHAIN[2][1],
        same_route,
        f"episode2.experience_id={ep2_experience_id!r}/known_route_id={ep2_route_id!r} vs "
        f"episode1.experience_id={ep1_experience_id!r}/known_route_id={ep1_route_id!r}",
    )

    ep2_ocel_objs = _ocel_event_objects(ep2_ocel, "Episode2Completed")
    ep2_ocel_binds = (
        any(episode2_id in objs and ep2_route_id in objs for objs in ep2_ocel_objs)
        if ep2_route_id
        else False
    )
    add(
        "episode2_ocel->route",
        REQUIRED_CHAIN[3][1],
        ep2_ocel_binds,
        f"{len(ep2_ocel_objs)} Episode2Completed event(s); "
        f"{'an' if ep2_ocel_binds else 'no'} explicit event relates episode2_id and known_route_id together",
    )

    ep1_actuation = ep1.get("actuation_identity", "")
    ep2_actuation = ep2.get("actuation_identity", "")
    fresh_identity = (
        bool(ep1_actuation) and bool(ep2_actuation) and ep1_actuation != ep2_actuation
    )
    add(
        "episode2->fresh_identity",
        REQUIRED_CHAIN[4][1],
        fresh_identity,
        f"episode1.actuation_identity={ep1_actuation!r} episode2.actuation_identity={ep2_actuation!r}",
    )

    usage = ep2.get("intelligence_usage", {}) or {}
    recomputed_clean = (
        ep2.get("classification") == "KNOWN"
        and bool(ep2.get("route_executed"))
        and bool(ep2.get("required_postcondition_verified"))
        and int(usage.get("explore_unknown_invocations", -1)) == 0
        and int(usage.get("frontier_model_calls", -1)) == 0
        and float(usage.get("discovery_cost", -1.0)) == 0.0
        and int(usage.get("worker_allocations", -1)) == 0
    )
    stored_clean = bool(ep2.get("frontier_clean"))
    frontier_matches = recomputed_clean == stored_clean
    add(
        "episode2->frontier_clean_recomputed",
        REQUIRED_CHAIN[5][1],
        frontier_matches,
        f"recomputed={recomputed_clean} stored={stored_clean} "
        f"(from raw counters: {usage})"
        + ("" if frontier_matches else " -- MISMATCH, producer's claim not trusted"),
    )

    anti_vacuity = (
        ep2.get("classification") == "KNOWN"
        and bool(ep2.get("route_executed"))
        and bool(ep2.get("required_postcondition_verified"))
        and bool(ep2.get("final_receipt_digest"))
    )
    add(
        "episode2->anti_vacuity",
        REQUIRED_CHAIN[6][1],
        anti_vacuity,
        f"route_executed={ep2.get('route_executed')} required_postcondition_verified={ep2.get('required_postcondition_verified')} "
        f"final_receipt_digest={'present' if ep2.get('final_receipt_digest') else 'ABSENT'}",
    )

    return IndependentStanding(
        str(state_dir), episode1_id, episode2_id, tuple(results), tuple(seen), ()
    )


def assert_no_runtime_imports() -> None:
    leaked = [m for m in FORBIDDEN_RUNTIME_MODULES if m in sys.modules]
    if leaked:
        raise RuntimeError(
            f"VERIFIER_NOT_INDEPENDENT: the producing runtime is imported in this process "
            f"({leaked}); standing computed here would not be external to the actor"
        )


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(
            "usage: fresh_consumer.py <state_dir> <episode1_id> <episode2_id>",
            file=sys.stderr,
        )
        return 2
    standing = verify(Path(argv[1]), argv[2], argv[3])
    assert_no_runtime_imports()
    print(json.dumps(standing.to_dict(), indent=2, sort_keys=True))
    return 0 if standing.verdict() == "CONFORMANT_EVIDENCE_RECONSTRUCTED" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
