from __future__ import annotations

import hashlib
import dataclasses

from autofde_lab.iec.crowns.model import Verdict, content_id
from autofde_lab.iec.xprod import (
    REQUIRED_SURFACES,
    ProjectionEvidence,
    make_relation_witness,
    qualify_xprod,
)


SUBJECT = "urn:autofde:xprod:v26.9.25:subject-1"


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def fixture():
    materials = {surface: f"producer:{surface}:v26.9.25".encode() for surface in REQUIRED_SURFACES}
    projections = [
        ProjectionEvidence(
            surface=surface,
            exact_subject=SUBJECT,
            producer_digest=sha(materials[surface]),
            artifact_digest=content_id(surface, "artifact", SUBJECT),
            evidence_digest=content_id(surface, "evidence", SUBJECT),
            observer_digest=content_id(surface, "observer", SUBJECT),
        )
        for surface in REQUIRED_SURFACES
    ]
    by_surface = {item.surface: item for item in projections}
    witnesses = [
        make_relation_witness(
            left_surface=left,
            right_surface=right,
            relation="PROJECTION_OF",
            left_artifact_digest=by_surface[left].artifact_digest,
            right_artifact_digest=by_surface[right].artifact_digest,
        )
        for left, right in zip(REQUIRED_SURFACES, REQUIRED_SURFACES[1:])
    ]
    return projections, witnesses, materials


def test_all_required_surfaces_pass_with_recomputed_producers_and_zero_authority() -> None:
    projections, witnesses, materials = fixture()
    first = qualify_xprod(
        exact_subject=SUBJECT,
        projections=projections,
        witnesses=witnesses,
        producer_materials=materials,
    )
    replay = qualify_xprod(
        exact_subject=SUBJECT,
        projections=list(reversed(projections)),
        witnesses=list(reversed(witnesses)),
        producer_materials=materials,
    )
    assert first.verdict is Verdict.PASS
    assert first.authority == "none"
    assert first.failures == ()
    assert replay.replay_digest == first.replay_digest
    assert replay.projection_set_digest == first.projection_set_digest
    assert replay.relation_set_digest == first.relation_set_digest


def test_claimed_producer_digest_is_not_self_authenticating() -> None:
    projections, witnesses, materials = fixture()
    projections[0] = dataclasses.replace(
        projections[0],
        producer_digest="sha256:" + "f" * 64,
    )
    result = qualify_xprod(
        exact_subject=SUBJECT,
        projections=projections,
        witnesses=witnesses,
        producer_materials=materials,
    )
    assert result.verdict is Verdict.COUNTEREXAMPLE
    assert f"PRODUCER_DIGEST_MISMATCH:{REQUIRED_SURFACES[0]}" in result.failures


def test_missing_producer_material_is_evidence_ceiling_not_false_counterexample() -> None:
    projections, witnesses, materials = fixture()
    materials.pop("TLA+")
    result = qualify_xprod(
        exact_subject=SUBJECT,
        projections=projections,
        witnesses=witnesses,
        producer_materials=materials,
    )
    assert result.verdict is Verdict.BLOCKED
    assert "PRODUCER_MATERIAL_MISSING:TLA+" in result.failures


def test_authority_increase_is_a_cross_product_counterexample() -> None:
    projections, witnesses, materials = fixture()
    projections[4] = dataclasses.replace(projections[4], authority_delta=1)
    result = qualify_xprod(
        exact_subject=SUBJECT,
        projections=projections,
        witnesses=witnesses,
        producer_materials=materials,
    )
    assert result.verdict is Verdict.COUNTEREXAMPLE
    assert "AUTHORITY_INCREASE:RECEIPT" in result.failures


def test_relation_witness_must_bind_the_exact_artifacts_and_connect_graph() -> None:
    projections, witnesses, materials = fixture()
    witnesses[2] = dataclasses.replace(
        witnesses[2],
        right_artifact_digest="sha256:" + "0" * 64,
    )
    result = qualify_xprod(
        exact_subject=SUBJECT,
        projections=projections,
        witnesses=witnesses,
        producer_materials=materials,
    )
    assert result.verdict is Verdict.COUNTEREXAMPLE
    assert any(
        item.startswith("RELATION_RIGHT_ARTIFACT_MISMATCH:")
        for item in result.failures
    )
    assert any(
        item.startswith("RELATION_WITNESS_DIGEST_MISMATCH:")
        for item in result.failures
    )


def test_disconnected_relation_graph_fails_even_when_every_projection_exists() -> None:
    projections, witnesses, materials = fixture()
    result = qualify_xprod(
        exact_subject=SUBJECT,
        projections=projections,
        witnesses=witnesses[:-1],
        producer_materials=materials,
    )
    assert result.verdict is Verdict.COUNTEREXAMPLE
    assert "RELATION_GRAPH_DISCONNECTED" in result.failures


def test_exact_subject_and_independent_observer_are_conserved() -> None:
    projections, witnesses, materials = fixture()
    projections[1] = dataclasses.replace(
        projections[1],
        exact_subject="urn:other",
        observer_digest=projections[1].producer_digest,
    )
    result = qualify_xprod(
        exact_subject=SUBJECT,
        projections=projections,
        witnesses=witnesses,
        producer_materials=materials,
    )
    assert result.verdict is Verdict.COUNTEREXAMPLE
    assert "EXACT_SUBJECT_MISMATCH:HDDL" in result.failures
    assert "OBSERVER_NOT_INDEPENDENT:HDDL" in result.failures
