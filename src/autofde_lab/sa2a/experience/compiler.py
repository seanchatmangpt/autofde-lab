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
from autofde_lab.sa2a.unknown.resolution import (
    AdmissionReceipt as UnknownAdmissionReceipt,
)
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
        """Store `artifact` under its `rule_id`, refusing a genuine key collision.

        Hardening (2026-09-17): `rule_id` is `sha256(candidate_id)[:12]` -- 48 bits
        of a content-addressed digest, not a guaranteed-unique identity. Confirmed
        live: two DIFFERENT `CompiledDeterministicRule` objects sharing the same
        `rule_id` (an astronomically unlikely but real collision, or a caller bug
        constructing an artifact with a hand-set `rule_id`) previously silently
        overwrote whichever artifact was stored first -- with no detection, and no
        trace that the overwrite ever happened. Downstream, `ExperienceQualifier`
        re-reads an artifact by `rule_id` on every (re)qualification (ARD §19's real
        probe step) and every referencing `MachineExperience.compiled_artifact_ids`
        entry assumes it still points at the content it was admitted against -- a
        silent overwrite would corrupt requalification for the FIRST experience
        without ever refusing anything. Re-storing byte-identical content under the
        same key (an idempotent retry of the same compile) is harmless and allowed;
        storing genuinely different content under an already-occupied key is refused.
        """
        existing = self._artifacts.get(artifact.rule_id)
        if existing is not None and existing != artifact:
            raise ValueError(
                f"ArtifactRegistry.store() refused: rule_id {artifact.rule_id!r} "
                f"already holds a DIFFERENT artifact (existing fingerprint "
                f"{existing.fingerprint!r} != new fingerprint {artifact.fingerprint!r}) "
                "-- a silent overwrite would corrupt any experience already admitted "
                "against the existing artifact"
            )
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
        # Hardening (2026-09-17): `CandidateResolution.candidate_hash` (owned by
        # unknown/resolution.py, not this module) is a derived property that
        # `json.dumps()`s `evidence_payload` -- a field typed `Mapping[str, Any]`
        # with no JSON-serializability constraint of its own. Confirmed live: a
        # candidate whose evidence_payload holds a `set` (or any other
        # non-JSON-serializable value) makes `.candidate_hash` raise a raw,
        # uncaught `TypeError` at THIS call site -- inside compile()'s own code,
        # not merely before it. `compile()` already treats "this candidate's
        # provenance doesn't check out" as its own refusal domain (the two
        # ValueErrors immediately around this one), so a candidate whose hash
        # can't even be computed gets the same typed-refusal treatment rather
        # than an unguarded TypeError escaping from a property read deep in a
        # dependency this module doesn't own.
        try:
            solution_hash = admitted_solution.candidate_hash
        except TypeError as exc:
            raise ValueError(
                "ExperienceCompiler.compile() could not compute candidate_hash for "
                f"candidate {admitted_solution.candidate_id!r}: evidence_payload is not "
                f"JSON-serializable ({exc!r})"
            ) from exc
        if admission_receipt.candidate_hash != solution_hash:
            raise ValueError(
                "admission_receipt does not correspond to admitted_solution "
                f"(receipt hash {admission_receipt.candidate_hash} != candidate hash "
                f"{solution_hash})"
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
            source_candidate_digest=solution_hash,
            source_admission_receipt=admission_receipt.receipt_id,
            discovery_identity=episode_evidence.discovery_identity,
            discovery_resource_receipt=episode_evidence.discovery_resource_receipt,
            solution_candidate_digest=solution_hash,
            solution_admission_receipt=admission_receipt.receipt_id,
            compiled_artifact_ids=(artifact_id,),
            equivalence_predicate_id=equivalence_predicate_id,
            invalidation_set=dict(invalidation_set or {}),
            state=ExperienceState.CANDIDATE,
        )
