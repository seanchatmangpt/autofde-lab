# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Capability ontology for scikit-decide, generated from the live registry.

This is deliberately **not** a hand-maintained catalog. Every capability
here is discovered at generation time from:

* ``pyproject.toml`` entry points, via
  :func:`skdecide.utils.get_registered_domains` /
  :func:`~skdecide.utils.get_registered_solvers` — the authoritative registry;
* each solver's ``get_domain_requirements()`` (``src/skdecide/solvers.py:85``),
  which derives the required domain characteristics from the solver's
  ``T_domain`` MRO — so applicability is *derived*, never asserted;
* an actual import attempt per capability, which is the standing evidence.

A hand-written list of capabilities that happens to sit next to real logic
would not be ontology-backed. The test consumes the emitted Turtle file, so
a capability that is registered but missing from the ontology, or present in
the ontology but no longer registered, makes the coverage assertion fail.

Standing vocabulary follows `CLAUDE.md` §1 and `docs/ecosystem-standing.md`.

Note on `_load_registered_entry` (``src/skdecide/utils.py:94``): it swallows
exceptions and returns ``None`` with a warning. A failed load is therefore
positive ``UNSUPPORTED`` evidence, not absence — recorded as such here so a
silently-unloadable solver cannot simply vanish from the tally.
"""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

SKD = "urn:skdecide:capability:"
SKDT = "urn:skdecide:term:"

#: `CLAUDE.md` §1 standing vocabulary.
STANDING_ALIVE = "ALIVE"
STANDING_PARTIAL = "PARTIAL_ALIVE"
STANDING_BLOCKED = "BLOCKED"
STANDING_BUILD_BROKEN = "BUILD_BROKEN"
STANDING_UNKNOWN = "UNKNOWN"
STANDING_UNSUPPORTED = "UNSUPPORTED"

#: PDDL requirements the C++ backend parses but does NOT implement. Kept in
#: sync with `skdecide.fabric.pddl_engine.UNIMPLEMENTED_REQUIREMENTS`; encoded
#: in the ontology so the silent-wrong-answer hazard is a first-class fact
#: about the capability surface rather than a comment in one module.
PDDL_REQUIREMENT_STATUS: Dict[str, str] = {
    ":strips": STANDING_ALIVE,
    ":typing": STANDING_ALIVE,
    ":equality": STANDING_ALIVE,
    ":negative-preconditions": STANDING_ALIVE,
    ":disjunctive-preconditions": STANDING_ALIVE,
    ":existential-preconditions": STANDING_ALIVE,
    ":universal-preconditions": STANDING_ALIVE,
    ":conditional-effects": STANDING_ALIVE,
    ":fluents": STANDING_ALIVE,
    ":numeric-fluents": STANDING_ALIVE,
    ":action-costs": STANDING_ALIVE,
    ":probabilistic-effects": STANDING_ALIVE,
    # Parsed, never implemented -- these produce WRONG plans silently.
    ":derived-predicates": STANDING_UNSUPPORTED,
    ":constraints": STANDING_UNSUPPORTED,
    ":preferences": STANDING_UNSUPPORTED,
    # Hard-fails at evaluation time rather than silently.
    ":durative-actions": STANDING_UNSUPPORTED,
}


@dataclass
class Capability:
    """One registered domain or solver, with derived applicability facts."""

    identifier: str
    kind: str  # "Domain" | "Solver"
    entry_point: str
    standing: str
    evidence: str
    owning_module: Optional[str] = None
    extras: Optional[str] = None
    requirements: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()

    @property
    def iri(self) -> str:
        return f"{SKD}{self.kind.lower()}/{self.identifier}"


def _entry_points(group: str) -> Dict[str, importlib.metadata.EntryPoint]:
    try:
        entries = importlib.metadata.entry_points(group=group)
    except TypeError:  # pragma: no cover - very old importlib
        entries = importlib.metadata.entry_points().get(group, [])
    return {entry.name: entry for entry in entries}


def _probe(kind: str, name: str, entry) -> Capability:
    """Import a capability and record the outcome as standing evidence."""
    from skdecide import utils

    loader = (
        utils.load_registered_domain
        if kind == "Domain"
        else utils.load_registered_solver
    )
    extras = ",".join(entry.extras) if getattr(entry, "extras", None) else None

    try:
        loaded = loader(name)
    except Exception as exc:  # noqa: BLE001
        return Capability(
            identifier=name,
            kind=kind,
            entry_point=entry.value,
            standing=STANDING_UNSUPPORTED,
            evidence=f"load raised {type(exc).__name__}: {exc}",
            extras=extras,
        )

    if loaded is None:
        # utils._load_registered_entry swallowed an ImportError. This is
        # positive UNSUPPORTED evidence, not absence.
        return Capability(
            identifier=name,
            kind=kind,
            entry_point=entry.value,
            standing=STANDING_UNSUPPORTED,
            evidence="load_registered_* returned None (dependency missing)",
            extras=extras,
        )

    requirements: Tuple[str, ...] = ()
    limitations: List[str] = []
    if kind == "Solver":
        try:
            requirements = tuple(
                sorted(req.__name__ for req in loaded.get_domain_requirements())
            )
        except Exception as exc:  # noqa: BLE001
            limitations.append(f"get_domain_requirements failed: {exc}")

    return Capability(
        identifier=name,
        kind=kind,
        entry_point=entry.value,
        standing=STANDING_ALIVE,
        evidence=f"imported {loaded.__module__}.{loaded.__qualname__}",
        owning_module=loaded.__module__,
        extras=extras,
        requirements=requirements,
        limitations=tuple(limitations),
    )


def collect_capabilities() -> List[Capability]:
    """Discover every registered domain and solver, with live standing."""
    capabilities: List[Capability] = []
    for kind, group in (
        ("Domain", "skdecide.domains"),
        ("Solver", "skdecide.solvers"),
    ):
        for name, entry in sorted(_entry_points(group).items()):
            capabilities.append(_probe(kind, name, entry))
    return capabilities


def _literal(text: str) -> str:
    escaped = (
        str(text)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
    )
    return f'"{escaped}"'


def emit_turtle(capabilities: List[Capability]) -> str:
    """Render the capability graph as Turtle."""
    out: List[str] = [
        f"@prefix skd: <{SKD}> .",
        f"@prefix skdt: <{SKDT}> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        "# GENERATED by skdecide.fabric.ontology -- do not hand-edit.",
        "# Source of truth: pyproject.toml entry points + live import probe",
        "# + Solver.get_domain_requirements() MRO derivation.",
        "",
    ]

    for capability in capabilities:
        out.append(f"<{capability.iri}> a skdt:{capability.kind} ;")
        out.append(f"    skdt:identifier {_literal(capability.identifier)} ;")
        out.append(f"    skdt:entryPoint {_literal(capability.entry_point)} ;")
        out.append(f"    skdt:standing {_literal(capability.standing)} ;")
        out.append(f"    skdt:evidence {_literal(capability.evidence)} ;")
        if capability.owning_module:
            out.append(
                f"    skdt:owningModule {_literal(capability.owning_module)} ;"
            )
        if capability.extras:
            out.append(f"    skdt:extrasMarker {_literal(capability.extras)} ;")
        for requirement in capability.requirements:
            out.append(
                f"    skdt:requiresCharacteristic <{SKD}characteristic/{requirement}> ;"
            )
        for limitation in capability.limitations:
            out.append(f"    skdt:knownLimitation {_literal(limitation)} ;")
        out.append(
            f"    skdt:capabilityCount "
            f'"{len(capability.requirements)}"^^xsd:integer .'
        )
        out.append("")

    for requirement, status in sorted(PDDL_REQUIREMENT_STATUS.items()):
        iri = f"{SKD}pddl-requirement/{requirement.lstrip(':')}"
        out.append(f"<{iri}> a skdt:PddlRequirement ;")
        out.append(f"    skdt:identifier {_literal(requirement)} ;")
        out.append(f"    skdt:standing {_literal(status)} ;")
        if status == STANDING_UNSUPPORTED:
            out.append(
                "    skdt:knownLimitation "
                + _literal(
                    "parsed by the C++ backend but not implemented in its "
                    "semantics; planning would silently return an incorrect "
                    "plan, so skdecide.fabric.pddl_engine refuses it"
                )
                + " ;"
            )
        out.append(f"    rdfs:label {_literal(requirement)} .")
        out.append("")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Minimal reader for the subset of Turtle emitted above.
# ---------------------------------------------------------------------------


def parse_turtle(text: str) -> Dict[str, Dict[str, List[str]]]:
    """Parse the Turtle subset this module emits.

    Deliberately a *subset* reader, not a general Turtle parser: `rdflib` is
    not a dependency of this package, and adding one to read a file we also
    write would be circular. Scope is documented rather than implied --
    it handles ``<iri> pred obj ;`` / ``.`` statements with quoted literals,
    IRIs, and ``^^`` typed literals, which is exactly what `emit_turtle`
    produces. It is not suitable for arbitrary Turtle.
    """
    graph: Dict[str, Dict[str, List[str]]] = {}
    subject: Optional[str] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("@prefix"):
            continue

        terminal = line.endswith(".")
        line = line.rstrip(" .;")

        if line.startswith("<") and "> a " in line:
            subject, _, remainder = line.partition("> a ")
            subject = subject.lstrip("<")
            graph.setdefault(subject, {}).setdefault("a", []).append(
                remainder.strip()
            )
            continue

        if subject is None:
            continue

        predicate, _, obj = line.partition(" ")
        obj = obj.strip()
        if obj.startswith('"'):
            closing = obj.rfind('"')
            value = obj[1:closing].replace('\\"', '"').replace("\\n", "\n")
        elif obj.startswith("<"):
            value = obj.strip("<>")
        else:
            value = obj
        graph[subject].setdefault(predicate, []).append(value)

        if terminal:
            subject = subject  # statement block ends; subject reused on next `a`

    return graph


def generate(output_path: str) -> List[Capability]:
    """Regenerate the ontology file from the live registry."""
    capabilities = collect_capabilities()
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(emit_turtle(capabilities))
    return capabilities


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "ontology/skdecide-capabilities.ttl"
    caps = generate(target)
    alive = sum(1 for c in caps if c.standing == STANDING_ALIVE)
    print(f"generated {target}: {len(caps)} capabilities, {alive} ALIVE")
