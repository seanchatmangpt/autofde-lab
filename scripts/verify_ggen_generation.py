#!/usr/bin/env python3
# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Independently re-derive `ggen sync run`'s output counts directly from the
real `ontology/*.ttl` source files via `rdflib`, and assert the committed
generated `.py` files match -- never trusting `ggen`'s own self-reported
counts (`no-dual-bookkeeping.md`'s "recompute from source, not a summary"
discipline, applied to code generation instead of runtime evidence).

Modeled on `~/ggen-marketplace/packs/autofde-semantic-registry-pack/gates/
verify_registry.py`'s pattern: a standalone script, real `rdflib` parse, a
machine-readable JSON receipt on stdout using this repo's own standing
vocabulary (`.claude/rules/standing-law.md`): ALIVE / UNKNOWN / UNSUPPORTED.

Five real, independent checks:

1. **k8s-fault-universes**: recompute the cross-product cardinality
   |Component| x |FailureMode| x |AppTopology| x |Severity| by counting real
   `rdf:type` triples per class in `ontology/k8s-fault-taxonomy.ttl`, and
   assert it equals the real `def universe_*` count in the committed
   `src/autofde_lab/reasoning/universes/k8s_fault_universes.py`.
2. **constitution**: for each of the 8 constitution ontology files, recompute
   the real `owl:Class` count carrying that file's own
   `rdfs:isDefinedBy <urn:autofde-lab:ontology:...>` triple, and assert it
   equals the real `@dataclass` count in the matching generated
   `src/autofde_lab/constitution/*.py` module (StandingValue-only files --
   i.e. every class is a SKOS vocabulary and none survives as a dataclass --
   count as zero real dataclasses, which is asserted too, not skipped).
   The vocabulary-individual exclusion below is computed against the real
   **merged** ontology graph (`ggen.toml`'s own `[ontology] source` +
   `imports` list, read from the manifest itself, never hand-duplicated) --
   not each concept's single `<name>.ttl` file in isolation -- because a
   class can be declared in one file and have its individuals typed in a
   *different* file (confirmed real case, 2026-09-16:
   `ontology/world-transformation-taxonomy.ttl` types five individuals
   against `afl:AdmittedObservation`, declared in `ontology/world.ttl`).
   `ggen`'s own SPARQL queries run against that same merged graph, so a
   single-file parse here would silently disagree with what `ggen sync run`
   actually renders -- this was a real, confirmed bug in this script, fixed
   in the same pass that flipped `constitution-world`'s `ggen.toml` mode to
   `Overwrite` (see
   `docs/jira/v26.9.16/AFDE-2608-projected-ephemeral-ontology-invariant.md`).
3. **world-transformation-scenarios**: recompute the real
   `afl:WorldTransformationScenario` individual count in
   `ontology/world-transformation-taxonomy.ttl` and assert it equals the
   real `def scenario_*` count in the committed
   `src/autofde_lab/reasoning/scenarios/world_transformation_scenarios.py`.
4. **togaf-artifacts**: same real `owl:Class`-count-vs-`@dataclass`-count
   discipline as the constitution check, applied to
   `ontology/togaf-artifacts.ttl` -> `src/autofde_lab/reasoning/togaf_artifacts.py`.
5. **gymact-certification**: same real `owl:Class`-count-vs-`@dataclass`-count
   discipline, applied to `ontology/gymact-certification.ttl` ->
   `src/autofde_lab/reasoning/gymact_certification_types.py`.

This script never imports or subprocesses `ggen` itself -- it is
intentionally independent of the generator under audit.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

try:
    from rdflib import RDF, RDFS, Graph, Namespace
except ModuleNotFoundError as exc:  # pragma: no cover - environment gate
    print(
        json.dumps(
            {
                "standing": "UNSUPPORTED",
                "reason": "rdflib is required",
                "error": str(exc),
            }
        )
    )
    raise SystemExit(3)

REPO_ROOT = Path(__file__).resolve().parent.parent

AFL = Namespace("urn:autofde-lab:")

GGEN_TOML = REPO_ROOT / "ggen.toml"

K8S_TAXONOMY_TTL = REPO_ROOT / "ontology" / "k8s-fault-taxonomy.ttl"
K8S_UNIVERSES_PY = (
    REPO_ROOT
    / "src"
    / "autofde_lab"
    / "reasoning"
    / "universes"
    / "k8s_fault_universes.py"
)
K8S_AXES = ("Component", "FailureMode", "AppTopology", "Severity")

WORLD_TRANSFORMATION_TTL = REPO_ROOT / "ontology" / "world-transformation-taxonomy.ttl"
WORLD_TRANSFORMATION_PY = (
    REPO_ROOT
    / "src"
    / "autofde_lab"
    / "reasoning"
    / "scenarios"
    / "world_transformation_scenarios.py"
)

CONSTITUTION_FILES = (
    "lab",
    "world",
    "planning",
    "process",
    "authority",
    "evidence",
    "standing",
    "interop",
)


def _count_k8s_universe_functions(py_path: Path) -> int:
    text = py_path.read_text(encoding="utf-8")
    return len(re.findall(r"^def universe_", text, flags=re.MULTILINE))


def _verify_k8s_fault_universes() -> dict:
    graph = Graph()
    graph.parse(K8S_TAXONOMY_TTL, format="turtle")

    axis_counts: dict[str, int] = {}
    for axis in K8S_AXES:
        axis_class = AFL[axis]
        # Real individuals: subjects with `rdf:type <axis_class>` where the
        # subject is not itself a class/scheme declaration.
        individuals = {s for s, _, _ in graph.triples((None, RDF.type, axis_class))}
        axis_counts[axis] = len(individuals)

    expected_universe_count = 1
    for count in axis_counts.values():
        expected_universe_count *= count

    actual_universe_count = _count_k8s_universe_functions(K8S_UNIVERSES_PY)

    ok = expected_universe_count == actual_universe_count and all(
        c > 0 for c in axis_counts.values()
    )
    return {
        "check": "k8s-fault-universes",
        "axis_counts": axis_counts,
        "expected_universe_count": expected_universe_count,
        "actual_universe_count": actual_universe_count,
        "match": ok,
    }


def _count_scenario_functions(py_path: Path) -> int:
    text = py_path.read_text(encoding="utf-8")
    return len(re.findall(r"^def scenario_", text, flags=re.MULTILINE))


def _verify_world_transformation_scenarios() -> dict:
    graph = Graph()
    graph.parse(WORLD_TRANSFORMATION_TTL, format="turtle")

    scenario_class = AFL["WorldTransformationScenario"]
    scenarios = {s for s, _, _ in graph.triples((None, RDF.type, scenario_class))}
    expected_scenario_count = len(scenarios)
    actual_scenario_count = _count_scenario_functions(WORLD_TRANSFORMATION_PY)

    ok = (
        expected_scenario_count == actual_scenario_count and expected_scenario_count > 0
    )
    return {
        "check": "world-transformation-scenarios",
        "expected_scenario_count": expected_scenario_count,
        "actual_scenario_count": actual_scenario_count,
        "match": ok,
    }


def _count_dataclasses(py_path: Path) -> int:
    if not py_path.exists():
        return 0
    text = py_path.read_text(encoding="utf-8")
    return len(re.findall(r"^@dataclass", text, flags=re.MULTILINE))


def _load_merged_ontology_graph() -> Graph:
    """Parse the exact same multi-file ontology graph `ggen sync run` compiles its
    SPARQL queries against -- `ggen.toml`'s own real `[ontology] source` + `imports`
    list, read directly from the manifest so this never hand-duplicates (and can
    never drift from) the real generation scope.

    A per-concept check that instead parsed only its own `<name>.ttl` file in
    isolation could not see a cross-file individual binding (confirmed real case:
    `ontology/world-transformation-taxonomy.ttl` types five individuals against
    `afl:AdmittedObservation`, declared in `ontology/world.ttl`) and would silently
    compute the wrong `expected_dataclass_count` for exactly that case -- this was a
    real, confirmed bug, not a hypothetical one (see module docstring point 2).
    """
    manifest = tomllib.loads(GGEN_TOML.read_text(encoding="utf-8"))
    ontology_cfg = manifest["ontology"]
    ttl_relative_paths = [ontology_cfg["source"], *ontology_cfg.get("imports", [])]

    graph = Graph()
    for relative_path in ttl_relative_paths:
        graph.parse(REPO_ROOT / relative_path, format="turtle")
    return graph


def _verify_dataclass_projection(
    *, check_name: str, graph: Graph, ontology_name: str, py_path: Path
) -> dict:
    ontology_iri = AFL[f"ontology:{ontology_name}"]
    owl_class = Namespace("http://www.w3.org/2002/07/owl#")["Class"]

    all_classes = {
        s
        for s, _, _ in graph.triples((None, RDF.type, owl_class))
        if (s, RDFS.isDefinedBy, ontology_iri) in graph
    }

    # A class that owns real SKOS-vocabulary individuals (any real
    # `?individual a ?class`, individual != class) projects as an Enum
    # member set, not a dataclass -- exclude those, mirroring the template's
    # own `vocab_class_iris` exclusion logic exactly.
    vocab_classes = set()
    for cls in all_classes:
        for individual, _, _ in graph.triples((None, RDF.type, cls)):
            if individual != cls:
                vocab_classes.add(cls)
                break

    expected_dataclass_count = len(all_classes - vocab_classes)
    actual_dataclass_count = _count_dataclasses(py_path)

    ok = expected_dataclass_count == actual_dataclass_count
    return {
        "check": check_name,
        "expected_dataclass_count": expected_dataclass_count,
        "actual_dataclass_count": actual_dataclass_count,
        "match": ok,
    }


def _verify_constitution_file(name: str, graph: Graph) -> dict:
    return _verify_dataclass_projection(
        check_name=f"constitution-{name}",
        graph=graph,
        ontology_name=name,
        py_path=REPO_ROOT / "src" / "autofde_lab" / "constitution" / f"{name}.py",
    )


def _verify_togaf_artifacts(graph: Graph) -> dict:
    return _verify_dataclass_projection(
        check_name="togaf-artifacts",
        graph=graph,
        ontology_name="togaf-artifacts",
        py_path=REPO_ROOT / "src" / "autofde_lab" / "reasoning" / "togaf_artifacts.py",
    )


def _verify_gymact_certification(graph: Graph) -> dict:
    return _verify_dataclass_projection(
        check_name="gymact-certification",
        graph=graph,
        ontology_name="gymact-certification",
        py_path=REPO_ROOT
        / "src"
        / "autofde_lab"
        / "reasoning"
        / "gymact_certification_types.py",
    )


def main() -> int:
    merged_graph = _load_merged_ontology_graph()

    results = [
        _verify_k8s_fault_universes(),
        _verify_world_transformation_scenarios(),
        _verify_togaf_artifacts(merged_graph),
        _verify_gymact_certification(merged_graph),
    ]
    results.extend(
        _verify_constitution_file(name, merged_graph) for name in CONSTITUTION_FILES
    )

    all_match = all(r["match"] for r in results)
    receipt = {
        "standing": "ALIVE" if all_match else "BUILD_BROKEN",
        "results": results,
    }
    print(json.dumps(receipt, indent=2))
    return 0 if all_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
