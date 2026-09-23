"""Kernel, schema, work-order, report, and operator projection tests."""

from __future__ import annotations

import json

import pytest

from autofde_lab.iec.cli import main
from autofde_lab.iec.graph_ir import SemanticEdge, SemanticGraph, SemanticNode
from autofde_lab.iec.kernel import KernelAssembler, Residue
from autofde_lab.iec.model import (
    ClaimCeiling,
    Counterexample,
    EquivalenceDimension,
    Failure,
    FailureKind,
)
from autofde_lab.iec.promotion import PromotionKind, PromotionRouter
from autofde_lab.iec.receipts import IECStage, ReceiptChain
from autofde_lab.iec.report import ReportBuilder
from autofde_lab.iec.retirement import RetirementLedger
from autofde_lab.iec.schema import infer_shape, same_shape_candidates
from autofde_lab.iec.workorders import WorkKind, WorkOrderProjector


def tiny_graph() -> SemanticGraph:
    source = SemanticNode.create(kind="Protocol", key="brce")
    verifier = SemanticNode.create(kind="Verifier", key="tla")
    edge = SemanticEdge.create(
        source=source.node_id,
        predicate="verifiedBy",
        target=verifier.node_id,
    )
    return SemanticGraph.build((source, verifier), (edge,))


def test_shape_inference_erases_values_but_preserves_contract() -> None:
    left = {"name": "alpha", "port": 1, "enabled": True}
    right = {"name": "beta", "port": 9000, "enabled": False}
    assert infer_shape(left).shape_id == infer_shape(right).shape_id


def test_shape_inference_distinguishes_changed_contract() -> None:
    left = {"name": "alpha", "port": 1}
    right = {"name": "beta", "port": "9000"}
    assert infer_shape(left).shape_id != infer_shape(right).shape_id


def test_same_shape_is_candidate_not_equivalence() -> None:
    candidates = same_shape_candidates(
        (
            ("a", {"name": "a", "port": 1}),
            ("b", {"name": "b", "port": 2}),
            ("c", {"name": "c", "port": "2"}),
        )
    )
    assert len(candidates) == 1
    assert candidates[0].left_id == "a"
    assert candidates[0].right_id == "b"
    assert candidates[0].standing == "CANDIDATE"


def test_kernel_proposal_keeps_explicit_irreducible_residue() -> None:
    graph = tiny_graph()
    proposal = KernelAssembler().assemble(
        graph=graph,
        covered_observation_ids=("o1", "o2"),
        generator_route_ids=("ggen-route",),
        residue=(
            Residue(
                subject_id="subject",
                path="src/irreducible.py",
                reason="UNSUPPORTED(generator-capability): dynamic native extension",
                generator_failure_id="failure",
            ),
        ),
        verifier_set_ids=("v1",),
        preservation_fence_ids=("f1",),
        repeated_reasoning_units=2,
    )
    assert len(proposal.residue) == 1
    assert proposal.cost.residue_units == 1
    assert proposal.cost.repeated_reasoning_units == 2
    candidate = proposal.as_kernel_candidate()
    assert candidate.covered_observation_ids == ("o1", "o2")


def test_work_order_from_counterexample_carries_regression_witness_requirements() -> None:
    counterexample = Counterexample(
        hypothesis_id="hypothesis",
        dimension=EquivalenceDimension.PROTOCOL,
        verifier_id="tlc/v1",
        expected="authority required",
        actual="unauthorized transition",
        detail="DO reachable without authority",
        evidence_ids=("receipt:counterexample",),
    )
    work = WorkOrderProjector().from_counterexample(
        repository="seanchatmangpt/autofde-lab",
        counterexample=counterexample,
    )
    assert work.kind is WorkKind.REPAIR
    assert work.authority == "NONE"
    assert "counterexample remains as regression witness" in work.acceptance


def test_work_order_from_failure_preserves_typed_failure() -> None:
    failure = Failure(
        kind=FailureKind.BLOCKED_VERIFIER_UNAVAILABLE,
        detail="TLC binary not installed",
        subject_id="subject",
    )
    work = WorkOrderProjector().from_failure(
        repository="seanchatmangpt/autofde-lab",
        failure=failure,
    )
    assert work.kind is WorkKind.DIAGNOSE
    assert "BLOCKED_VERIFIER_UNAVAILABLE" in work.title


def test_promotion_work_order_routes_to_owner_repository() -> None:
    promotion = PromotionRouter().route(
        kind=PromotionKind.RECEIPT_PROFILE,
        artifact_identity="affidavit/brce-model-check/v1",
        source_evidence_ids=("source",),
        verifier_receipt_ids=("verification",),
    )
    work = WorkOrderProjector().from_promotion(promotion)
    assert work.repository == "seanchatmangpt/affidavit"
    assert work.kind is WorkKind.PROMOTE
    assert work.authority == "NONE"


def test_report_refuses_to_masquerade_as_external_do_evidence() -> None:
    with pytest.raises(ValueError, match="cannot certify external DO"):
        from autofde_lab.iec.report import RunReport

        RunReport(
            corpus_revision_id="corpus",
            exact_subject_ids=("subject",),
            receipt_ids=(),
            validation_ids=(),
            failure_ids=(),
            reasoning_class_ids=(),
            external_do_observed=True,
        )


def test_report_binds_receipts_and_reasoning_class_identities() -> None:
    chain = ReceiptChain()
    receipt = chain.append(
        stage=IECStage.OBSERVE,
        subject_ids=("subject",),
        input_ids=("input",),
        output_ids=("output",),
        result="OBSERVED",
    )
    ledger = RetirementLedger()
    reasoning = ledger.observe("classify-artifact", "occurrence-1")
    report = ReportBuilder().build(
        corpus_revision_id="corpus",
        exact_subject_ids=("subject",),
        receipts=(receipt,),
        reasoning_classes=(reasoning,),
        generated_artifact_ids=("artifact",),
    )
    assert report.receipt_ids == (receipt.receipt_id,)
    assert report.reasoning_class_ids == (reasoning.reasoning_class_id,)
    assert not report.external_do_observed


def test_cli_brce_tla_exposes_projection_and_explicit_not_run(capsys) -> None:
    exit_code = main(["brce-tla"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["module_name"] == "BRCEReference"
    assert payload["verification"] == "NOT_RUN"
    assert payload["authority"] == "NONE"
    assert "Actuate ==" in payload["tla"]
    assert "INVARIANT AtMostOneConsequence" in payload["cfg"]
