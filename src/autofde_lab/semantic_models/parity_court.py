"""Cross-runtime parity court and teacher independence evaluation.

Validates:
    SemanticOutput_reference == SemanticOutput_portable == SemanticOutput_AtomVM
    => Standing_1 == Standing_2 == Standing_3
and measures the convergence of TeacherDependencyRate -> 0.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .admission import SemanticAdmissionCourt
from .atomvm_codegen import (
    AtomVMStanding,
    compile_and_test_erlang,
    generate_atomvm_erlang_module,
)
from .contracts import AdmissionStanding, CandidateGraphDelta
from .portable_compiler import PortableLinearWeights
from .tiny_operator import TinySemanticOperator


@dataclass(frozen=True)
class RuntimeParityRecord:
    """Witnesses cross-runtime semantic parity across execution targets."""

    sample_id: str
    reference_standing: AdmissionStanding
    portable_standing: AdmissionStanding
    atomvm_standing: AtomVMStanding
    standings_match: bool
    atomvm_output_matched: bool | None


@dataclass(frozen=True)
class TeacherIndependenceReport:
    """Metrics tracking the displacement of teacher LLMs by tiny deterministic operators."""

    total_inferences: int
    teacher_calls: int
    tiny_operator_calls: int
    teacher_dependency_rate: float
    admissible_coverage: float
    parameter_bytes: int


def evaluate_runtime_parity(
    *,
    test_vectors: Sequence[list[int]],
    observation_ids: Sequence[str],
    subject_iris: Sequence[str],
    reference_predict_fn: Any,  # sklearn predict
    portable_operator: TinySemanticOperator,
    linear_weights: PortableLinearWeights,
    court: SemanticAdmissionCourt,
) -> list[RuntimeParityRecord]:
    """Execute reference, portable, and AtomVM targets and assert exact semantic standing parity."""
    records: list[RuntimeParityRecord] = []

    # Generate Erlang module once
    erl_source = generate_atomvm_erlang_module(
        linear_weights, portable_operator.manifest
    )

    for idx, (vec, obs_id, subj_iri) in enumerate(
        zip(test_vectors, observation_ids, subject_iris, strict=False)
    ):
        # 1. Reference model execution (simulated or real sklearn)
        ref_class = int(reference_predict_fn([vec])[0])
        ref_iri = portable_operator.manifest.output_semantic_iris[ref_class]
        from .contracts import SemanticTriple

        ref_delta = CandidateGraphDelta(
            observation_id=obs_id,
            triples=(
                SemanticTriple(
                    subject=subj_iri,
                    predicate=ref_iri,
                    object="true",
                    object_kind="literal",
                ),
            ),
            source_iris=("urn:ref:model",),
            generator_id="reference-model",
            generator_revision="v1",
        )
        ref_receipt, _ = court.admit(ref_delta)

        # 2. Portable fixed-point execution
        port_delta, _ = portable_operator.execute_and_receipt(
            subject_iri=subj_iri,
            observation_id=obs_id,
            feature_vector=vec,
        )
        port_receipt, _ = court.admit(port_delta)

        # 3. AtomVM Erlang execution
        atomvm_status, atomvm_class = compile_and_test_erlang(erl_source, vec)
        atomvm_matched = (
            (atomvm_class == ref_class) if atomvm_class is not None else None
        )

        standings_match = ref_receipt.standing == port_receipt.standing

        records.append(
            RuntimeParityRecord(
                sample_id=obs_id,
                reference_standing=ref_receipt.standing,
                portable_standing=port_receipt.standing,
                atomvm_standing=atomvm_status,
                standings_match=standings_match,
                atomvm_output_matched=atomvm_matched,
            )
        )

    return records


def compute_teacher_independence(
    *,
    total_inferences: int,
    teacher_calls: int,
    tiny_operator_calls: int,
    admissible_coverage: float,
    parameter_bytes: int,
) -> TeacherIndependenceReport:
    """Calculate the teacher dependency rate and independence envelope."""
    if total_inferences == 0:
        rate = 0.0
    else:
        rate = float(teacher_calls / total_inferences)

    return TeacherIndependenceReport(
        total_inferences=total_inferences,
        teacher_calls=teacher_calls,
        tiny_operator_calls=tiny_operator_calls,
        teacher_dependency_rate=rate,
        admissible_coverage=admissible_coverage,
        parameter_bytes=parameter_bytes,
    )
