"""ExperienceCompiler: admitted Episode 1 solution -> CandidateMachineExperience.

v26.9.17 ARD §17: `compile(semantic_class, admitted_solution, episode_evidence) ->
CandidateMachineExperience`; the compiler itself does NOT admit the result.

This is a deliberate rebuild of the shape
`autofde_lab.sa2a.unknown.compilation.MachineExperienceCompiler` already has, not a
duplicate of its content: that class's `compile_candidate_experience()` writes
directly into its own `_rule_registry` (self._rule_registry[pattern] = rule) and the
very next method, `resolve()`, immediately returns the compiled output for any
matching future query -- compiling and becoming resolvable are the same event,
reproducing exactly the PROHIBITED "successful Episode 1 -> automatically KNOWN"
shortcut PRD §6.8 names. `ExperienceCompiler.compile()` below reuses that class's real,
good `CompiledDeterministicRule` artifact shape (imported, not re-derived) but returns
a `MachineExperience` at `ExperienceState.CANDIDATE` with the compiled artifact stored
in a private `ArtifactRegistry` this compiler owns -- nothing can read that artifact
back out until `ExperienceQualifier` (qualification.py) has independently proven it
QUALIFIED and ACTIVE (see that module's docstring for the admission/qualification
gate this decoupling makes possible).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Mapping

from autofde_lab.sa2a.experience.types import ExperienceState, MachineExperience
from autofde_lab.sa2a.unknown.compilation import CompiledDeterministicRule
from autofde_lab.sa2a.unknown.resolution import AdmissionReceipt as UnknownAdmissionReceipt
from autofde_lab.sa2a.unknown.resolution import CandidateResolution


class ArtifactRegistry:
    """Private compiled-artifact store, decoupled from resolvability (ARD §17).

    Only `ExperienceQualifier.qualify()` may read an artifact out of here, and only
    after independently proving the owning MachineExperience reached ACTIVE --
    compiling an artifact and being able to resolve queries against it are two
    separate events, unlike `MachineExperienceCompiler._rule_registry`.
    """

    def __init__(self) -> None:
        self._artifacts: dict[str, CompiledDeterministicRule] = {}

    def store(self, artifact: CompiledDeterministicRule) -> str:
        self._artifacts[artifact.rule_id] = artifact
        return artifact.rule_id

    def get(self, artifact_id: str) -> CompiledDeterministicRule | None:
        return self._artifacts.get(artifact_id)


@dataclass(frozen=True, slots=True)
class EpisodeEvidence:
    """The subset of Episode 1's real evidence a compiled experience must cite (ARD §17)."""

    episode_id: str
    discovery_identity: str
    discovery_resource_receipt: str


class ExperienceCompiler:
    """Compiles one admitted Episode 1 solution into a CANDIDATE MachineExperience."""

    def __init__(self, artifact_registry: ArtifactRegistry | None = None) -> None:
        self.artifact_registry = artifact_registry or ArtifactRegistry()

    def compile(
        self,
        *,
        semantic_class_id: str,
        admitted_solution: CandidateResolution,
        admission_receipt: UnknownAdmissionReceipt,
        episode_evidence: EpisodeEvidence,
        equivalence_predicate_id: str,
        invalidation_set: Mapping[str, str] | None = None,
    ) -> MachineExperience:
        """Compile one admitted candidate into a CANDIDATE MachineExperience.

        `admission_receipt` MUST already carry `admitted=True` -- this compiler never
        compiles unadmitted candidate content into machinery (PRD §6.7's "provenance
        from Episode 1 is preserved" requires the source to genuinely have standing).
        """
        if not admission_receipt.admitted:
            raise ValueError(
                "ExperienceCompiler.compile() requires an ADMITTED admission_receipt; "
                f"got admitted=False for candidate {admitted_solution.candidate_id}"
            )
        if admission_receipt.candidate_hash != admitted_solution.candidate_hash:
            raise ValueError(
                "admission_receipt does not correspond to admitted_solution "
                f"(receipt hash {admission_receipt.candidate_hash} != candidate hash "
                f"{admitted_solution.candidate_hash})"
            )

        rule = CompiledDeterministicRule(
            rule_id=f"rule_{hashlib.sha256(admitted_solution.candidate_id.encode('utf-8')).hexdigest()[:12]}",
            pattern=semantic_class_id,
            deterministic_output=admission_receipt.admitted_assertion,
            shacl_shape=None,
            fingerprint=hashlib.sha256(
                json.dumps(
                    {
                        "pattern": semantic_class_id,
                        "output": admission_receipt.admitted_assertion,
                    },
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest(),
        )
        artifact_id = self.artifact_registry.store(rule)

        experience_id = f"exp-{uuid.uuid4().hex[:12]}"
        return MachineExperience(
            experience_id=experience_id,
            semantic_class_id=semantic_class_id,
            source_episode_id=episode_evidence.episode_id,
            source_candidate_digest=admitted_solution.candidate_hash,
            source_admission_receipt=admission_receipt.receipt_id,
            discovery_identity=episode_evidence.discovery_identity,
            discovery_resource_receipt=episode_evidence.discovery_resource_receipt,
            solution_candidate_digest=admitted_solution.candidate_hash,
            solution_admission_receipt=admission_receipt.receipt_id,
            compiled_artifact_ids=(artifact_id,),
            equivalence_predicate_id=equivalence_predicate_id,
            invalidation_set=dict(invalidation_set or {}),
            state=ExperienceState.CANDIDATE,
        )
