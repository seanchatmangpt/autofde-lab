"""W678 AIRo wiring pin: autofde-lab row of the xaas AIRo-wiring ledger.

Ledger (/Users/sac/xaas/docs/cro/artifacts/airo-wiring-ledger.md, row w604)
claims for autofde-lab:
  * ontology/airo_risk_description.ttl exists at 8,071 B
  * real rdflib parse (no mocks), typed as airo:AISystem
  * 8/8 cited evidence paths on disk
  * pytest court passes

This pin re-verifies every one of those claims against the real disk state with
real imports and real parses (Chicago-style: no mocks, assert on final state).
It is an independent pin, not a copy of the w604 court.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.namespace import RDFS

REPO = Path(__file__).resolve().parents[2]
TTL = REPO / "ontology" / "airo_risk_description.ttl"
LEDGER_SIZE_BYTES = 8071
EXPECTED_SYSTEM = URIRef("https://autofde-lab.example/airo/beam-diagnosis-system")
AIRO = Namespace("https://w3id.org/airo#")


@pytest.fixture(scope="module")
def graph() -> Graph:
    g = Graph()
    g.parse(TTL.as_uri(), format="turtle")
    return g


def test_ledger_claim_ttl_size_8071_bytes() -> None:
    assert TTL.is_file(), f"missing: {TTL}"
    size = TTL.stat().st_size
    assert size == LEDGER_SIZE_BYTES, (
        f"ledger pins 8,071 B but disk shows {size} B — drift finding"
    )


def test_real_rdflib_parse_typed_airo_ai_system(graph: Graph) -> None:
    assert len(graph) > 0, "empty graph — real parse produced zero triples"
    assert (EXPECTED_SYSTEM, RDF.type, AIRO.AISystem) in graph


def test_ledger_claim_cited_paths_on_disk(graph: Graph) -> None:
    """Ledger says '8/8 cited paths on disk'.

    Drift finding (W678): the graph has 7 *distinct* file: citations — the
    9 seeAlso triples cite STATUS.md and the batch-results .tsv twice each.
    All distinct cited paths exist on disk, so the substance of the ledger
    claim holds; the count as literally written (8) is wrong.
    """
    cited = set(graph.objects(None, RDFS.seeAlso))
    file_uris = {u for u in cited if str(u).startswith("file:")}
    assert len(file_uris) == 7, f"expected 7 distinct cited paths, got {len(file_uris)}"
    missing = [
        u for u in file_uris
        if not (REPO / str(u)[len("file:"):]).is_file()
    ]
    assert not missing, f"cited evidence paths missing from disk: {missing}"


def test_cited_tests_are_real_test_files(graph: Graph) -> None:
    for u in graph.objects(None, RDFS.seeAlso):
        rel = str(u)
        if "tests/" in rel:
            path = REPO / rel[len("file:"):]
            assert "test_" in path.name, path
            assert path.is_file(), path


def test_no_placeholder_subjects_or_empty_labels(graph: Graph) -> None:
    for s in set(graph.subjects(RDF.type, None)):
        assert any(graph.objects(s, RDFS.label)), s
    risks = set(graph.subjects(RDF.type, AIRO.Risk))
    controls = set(graph.subjects(RDF.type, AIRO.RiskControl))
    assert len(risks) >= 2
    assert len(controls) >= 3


def test_w604_court_still_passes_via_pytest() -> None:
    """The ledger claims a pytest court: verify it really collects/passes."""
    r = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/ontology/test_airo_risk_description.py",
         "--no-header", "-p", "no:cacheprovider"],
        cwd=REPO, capture_output=True, text=True, timeout=120,
    )
    combined = r.stdout + r.stderr
    assert "6 passed" in combined, (
        f"w604 court did not report 6 passed:\n{combined}"
    )