"""ExperienceAdmissionGate: CandidateMachineExperience -> ADMITTED/REFUSED (ARD §18).

Fail-closed, staged, modeled directly on `autofde_lab.sa2a.admission.pipeline.
AdmissionPipeline`'s proven design (parse/structural -> provenance -> meta-admission
-> issue receipt) rather than calling that pipeline directly: `AdmissionPipeline.admit()`
validates RDF/Turtle candidate graphs (ShEx/SHACL/Datalog/N3/SPARQL falsifiers) --
a MachineExperience is a structured Python record, not an RDF graph, so the pipeline's
stage machinery does not apply to its candidate shape. Where a compiled artifact DOES
carry a SHACL shape, meta-admission is delegated to the real
`autofde_lab.sa2a.admission.meta_admission.MetaAdmissionRegistry` (reused, not
reimplemented) when the caller supplies one; otherwise this gate performs its own
real, fail-closed structural/provenance/artifact-integrity checks.

Any failure returns REFUSED with no mutation to canonical state -- this gate never
writes the experience anywhere; the caller (Episode1Runner) decides what to do with a
REFUSED result. This mirrors AdmissionPipeline's own "Received != Admitted; failed
admission produces no canonical mutation" invariant (PRD §6.3), applied one layer up.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from autofde_lab.sa2a.admission.meta_admission import MetaAdmissionRegistry, ValidatorKind
from autofde_lab.sa2a.experience.compiler import ArtifactRegistry
from autofde_lab.sa2a.experience.types import ExperienceState, MachineExperience

REFUSED_EMPTY_ARTIFACTS = "REFUSED_EXPERIENCE_EMPTY_ARTIFACTS"
REFUSED_ARTIFACT_NOT_FOUND = "REFUSED_EXPERIENCE_ARTIFACT_NOT_FOUND"
REFUSED_MISSING_PROVENANCE = "REFUSED_EXPERIENCE_MISSING_PROVENANCE"
REFUSED_META_ADMISSION = "REFUSED_EXPERIENCE_META_ADMISSION"


@dataclass(frozen=True, slots=True)
class ExperienceAdmissionResult:
    experience: MachineExperience
    receipt_id: str
    admitted: bool
    refusal_code: Optional[str] = None
    reasons: tuple[str, ...] = ()


class ExperienceAdmissionGate:
    """Admits or refuses a CANDIDATE MachineExperience (ARD §18)."""

    def __init__(
        self,
        artifact_registry: ArtifactRegistry,
        meta_admission_registry: Optional[MetaAdmissionRegistry] = None,
    ) -> None:
        self._artifacts = artifact_registry
        self._meta_admission = meta_admission_registry

    def admit(self, experience: MachineExperience) -> ExperienceAdmissionResult:
        if experience.state != ExperienceState.CANDIDATE:
            return self._refuse(
                experience,
                REFUSED_MISSING_PROVENANCE,
                (f"expected state CANDIDATE, got {experience.state.value}",),
            )

        reasons: list[str] = []

        # Stage 1: structural -- must reference at least one compiled artifact,
        # and every source/solution provenance field must be non-empty.
        if not experience.compiled_artifact_ids:
            reasons.append(REFUSED_EMPTY_ARTIFACTS)
        for field_name in (
            "source_episode_id",
            "source_candidate_digest",
            "source_admission_receipt",
            "discovery_identity",
            "solution_candidate_digest",
            "solution_admission_receipt",
            "equivalence_predicate_id",
        ):
            if not getattr(experience, field_name):
                reasons.append(f"{REFUSED_MISSING_PROVENANCE}:{field_name}")

        if reasons:
            return self._refuse(experience, reasons[0], tuple(reasons))

        # Stage 2: artifact integrity -- every referenced compiled artifact must
        # actually exist in the registry the compiler wrote it into.
        missing = [aid for aid in experience.compiled_artifact_ids if self._artifacts.get(aid) is None]
        if missing:
            return self._refuse(
                experience,
                REFUSED_ARTIFACT_NOT_FOUND,
                tuple(f"artifact not found: {aid}" for aid in missing),
            )

        # Stage 3: meta-admission -- when a compiled artifact carries a SHACL shape
        # and the caller supplied a real MetaAdmissionRegistry, that shape must
        # itself already have standing (reuses MetaAdmissionRegistry.admit_validator,
        # never reimplements it).
        if self._meta_admission is not None:
            for aid in experience.compiled_artifact_ids:
                artifact = self._artifacts.get(aid)
                if artifact is not None and artifact.shacl_shape:
                    decision = self._meta_admission.admit_validator(
                        validator_id=aid,
                        kind=ValidatorKind.SHACL_SHAPE,
                        artifact_content=artifact.shacl_shape,
                        source_root=experience.discovery_identity,
                        issuer_identity=experience.source_episode_id,
                        receipt_hash=experience.solution_admission_receipt,
                    )
                    if not decision.admitted:
                        return self._refuse(
                            experience,
                            REFUSED_META_ADMISSION,
                            (decision.reason or "meta-admission refused",),
                        )

        admitted_experience = experience.with_state(ExperienceState.ADMITTED)
        return ExperienceAdmissionResult(
            experience=admitted_experience,
            receipt_id=f"expadm-{uuid.uuid4().hex[:12]}",
            admitted=True,
            reasons=("STRUCTURAL_OK", "ARTIFACTS_PRESENT"),
        )

    @staticmethod
    def _refuse(
        experience: MachineExperience, code: str, reasons: tuple[str, ...]
    ) -> ExperienceAdmissionResult:
        refused = (
            experience.with_state(ExperienceState.REFUSED, refusal_code=code)
            if experience.state != ExperienceState.REFUSED
            else experience
        )
        return ExperienceAdmissionResult(
            experience=refused,
            receipt_id=f"expadm-{uuid.uuid4().hex[:12]}",
            admitted=False,
            refusal_code=code,
            reasons=reasons,
        )
