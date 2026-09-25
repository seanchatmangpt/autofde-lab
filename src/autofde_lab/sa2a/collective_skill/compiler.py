"""Compile qualified skill courts into powerless SA2A candidates and experience."""

from __future__ import annotations

import hashlib
import json

from autofde_lab.sa2a.collective_skill.types import (
    CourtAdmissionReceipt,
    CourtSpec,
)
from autofde_lab.sa2a.experience.compiler import EpisodeEvidence, ExperienceCompiler
from autofde_lab.sa2a.experience.types import MachineExperience
from autofde_lab.sa2a.unknown.resolution import (
    AdmissionReceipt as Sa2aAdmissionReceipt,
)
from autofde_lab.sa2a.unknown.resolution import (
    CandidateResolution,
    EpistemicState,
    UnknownResolutionPipeline,
)

EXPECTED_MARKETPLACE_REPOSITORY = "seanchatmangpt/ggen-marketplace"
EXPECTED_PACK_NAME = "collective-skill-court-pack"
EXPECTED_PACK_VERSION = "26.9.24"
EXPECTED_MARKETPLACE_COMMIT = "5eb71f7ed947f705a8d6b145cb9b0be82855d793"
EXPECTED_AUTHORITY_CEILING = "OBSERVE|SELECT|CONSTRUCT"


class CollectiveSkillCompiler:
    """Fail-closed bridge from manufactured court evidence to SA2A machinery."""

    def admit(self, spec: CourtSpec) -> CourtAdmissionReceipt:
        """Admit only Oracle-pass / NOP-fail / mutation-reject construct-only courts."""
        spec.validate()
        reasons: list[str] = []

        if spec.marketplace.repository != EXPECTED_MARKETPLACE_REPOSITORY:
            reasons.append("MARKETPLACE_REPOSITORY_MISMATCH")
        if spec.marketplace.pack_name != EXPECTED_PACK_NAME:
            reasons.append("MARKETPLACE_PACK_MISMATCH")
        if spec.marketplace.pack_version != EXPECTED_PACK_VERSION:
            reasons.append("MARKETPLACE_PACK_VERSION_MISMATCH")
        if spec.marketplace.commit_sha != EXPECTED_MARKETPLACE_COMMIT:
            reasons.append("MARKETPLACE_COMMIT_MISMATCH")
        if spec.work_order.repository != "seanchatmangpt/autofde-lab":
            reasons.append("SJIRA_REPOSITORY_MISMATCH")
        if spec.work_order.authority_ceiling != EXPECTED_AUTHORITY_CEILING:
            reasons.append("AUTHORITY_CEILING_EXCEEDED")
        if not spec.oracle.observed_success:
            reasons.append("ORACLE_FAILED")
        if spec.noop.observed_success:
            reasons.append("NOOP_PASSED")

        for mutation in spec.mutations:
            if mutation.observed_success:
                reasons.append(f"MUTATION_SURVIVED:{mutation.probe_id}")

        admitted = not reasons
        standing = "ADMITTED" if admitted else "REFUSED"
        reason_key = "|".join(reasons)
        token = hashlib.sha256(
            f"{spec.digest}:{standing}:{reason_key}".encode("utf-8")
        ).hexdigest()[:16]
        return CourtAdmissionReceipt(
            receipt_id=f"cskill-rec-{token}",
            court_digest=spec.digest,
            admitted=admitted,
            standing=standing,
            reasons=tuple(reasons) if reasons else ("COURT_CONFORMS",),
        )

    def to_candidate(
        self,
        spec: CourtSpec,
        receipt: CourtAdmissionReceipt,
    ) -> CandidateResolution:
        """Project an admitted court into the existing powerless SA2A candidate type."""
        spec.validate()
        if receipt.court_digest != spec.digest:
            raise ValueError("court receipt is not bound to this CourtSpec")
        if not receipt.admitted:
            raise ValueError("refused court cannot become an SA2A candidate")

        assertion = json.dumps(
            {
                "court_digest": spec.digest,
                "semantic_class_id": spec.semantic_class_id,
                "standing": "CANDIDATE",
                "authority": "none",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        probes = (spec.oracle, spec.noop, *spec.mutations)
        evidence = {
            "court_admission_receipt": receipt.digest,
            "source": {
                "id": spec.source.source_id,
                "kind": spec.source.source_kind,
                "digest": spec.source.source_digest,
                "provenance_uri": spec.source.provenance_uri,
            },
            "marketplace": {
                "identity": spec.marketplace.identity,
                "pack_source_digest": spec.marketplace.pack_source_digest,
            },
            "sjira": {
                "work_order": spec.work_order.identity,
                "repository": spec.work_order.repository,
                "base_sha": spec.work_order.base_sha,
                "evidence_ceiling": spec.work_order.evidence_ceiling,
                "authority_ceiling": spec.work_order.authority_ceiling,
            },
            "subject_sha": spec.exact_subject_sha,
            "probes": [
                {
                    "id": item.probe_id,
                    "kind": item.kind,
                    "observed_success": item.observed_success,
                    "evidence_digest": item.evidence_digest,
                }
                for item in probes
            ],
            "grants_do_authority": False,
        }
        candidate_token = hashlib.sha256(spec.digest.encode("utf-8")).hexdigest()[:16]
        return CandidateResolution(
            candidate_id=f"collective-skill-{candidate_token}",
            query_id=spec.work_order.identity,
            proposed_assertion=assertion,
            evidence_payload=evidence,
            source_identity=spec.marketplace.identity,
            consumed_ticks=0,
            consumed_tokens=0,
        )

    def compile_machine_experience(
        self,
        spec: CourtSpec,
        receipt: CourtAdmissionReceipt,
        *,
        episode_evidence: EpisodeEvidence,
        equivalence_predicate_id: str,
        experience_compiler: ExperienceCompiler | None = None,
    ) -> MachineExperience:
        """Compile an admitted court through SA2A while retaining CANDIDATE standing."""
        candidate = self.to_candidate(spec, receipt)
        expected_hash = candidate.candidate_hash

        def court(candidate_under_test: CandidateResolution) -> Sa2aAdmissionReceipt:
            reasons: list[str] = []
            if candidate_under_test.candidate_hash != expected_hash:
                reasons.append("CANDIDATE_IDENTITY_MISMATCH")
            if candidate_under_test.authority != "none":
                reasons.append("CANDIDATE_AUTHORITY_PRESENT")
            if (
                candidate_under_test.evidence_payload.get("grants_do_authority")
                is not False
            ):
                reasons.append("AMBIENT_DO_AUTHORITY")
            if (
                candidate_under_test.evidence_payload.get("court_admission_receipt")
                != receipt.digest
            ):
                reasons.append("COURT_RECEIPT_MISMATCH")

            admitted = not reasons
            return Sa2aAdmissionReceipt(
                receipt_id=receipt.receipt_id,
                candidate_hash=candidate_under_test.candidate_hash,
                admitted=admitted,
                epistemic_standing=(
                    EpistemicState.KNOWN if admitted else EpistemicState.REFUSED
                ),
                reasons=tuple(reasons)
                if reasons
                else ("COLLECTIVE_SKILL_COURT_ADMITTED",),
                admitted_assertion=(
                    candidate_under_test.proposed_assertion if admitted else None
                ),
            )

        pipeline = UnknownResolutionPipeline(admission_court=court)
        sa2a_receipt = pipeline.admit_candidate(candidate)
        if not sa2a_receipt.admitted:
            raise ValueError(
                "collective-skill candidate failed SA2A admission: "
                + ",".join(sa2a_receipt.reasons)
            )

        compiler = experience_compiler or ExperienceCompiler()
        return compiler.compile(
            semantic_class_id=spec.semantic_class_id,
            admitted_solution=candidate,
            admission_receipt=sa2a_receipt,
            episode_evidence=episode_evidence,
            equivalence_predicate_id=equivalence_predicate_id,
            invalidation_set={
                "court": spec.digest,
                "skill_source": spec.source.source_digest,
                "marketplace_pack": spec.marketplace.pack_source_digest,
                "marketplace_commit": spec.marketplace.commit_sha,
                "subject_sha": spec.exact_subject_sha,
                "sjira_work_order": spec.work_order.identity,
            },
        )
