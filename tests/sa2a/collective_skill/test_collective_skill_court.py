"""Focused unit court for collective skill manufacturing and SA2A compilation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from autofde_lab.sa2a.collective_skill import (
    CollectiveSkillCompiler,
    CourtSpec,
    MarketplacePackRef,
    ProbeObservation,
    SjiraWorkOrderRef,
    SkillSource,
)
from autofde_lab.sa2a.experience.compiler import EpisodeEvidence
from autofde_lab.sa2a.experience.types import ExperienceState

MARKETPLACE_SHA = "02c13c468892c040c8abfd5023db4c1a19fa4820"
SUBJECT_SHA = "1" * 40
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64
DIGEST_E = "sha256:" + "e" * 64
DIGEST_F = "sha256:" + "f" * 64


def admitted_spec() -> CourtSpec:
    return CourtSpec(
        court_id="court:chicago-domain-solver:repair-01",
        semantic_class_id="skill:chicago-domain-solver:repair",
        source=SkillSource(
            source_id="skill:chicago-domain-solver",
            source_kind="agent_skill",
            provenance_uri=".claude/skills/chicago-domain-solver/SKILL.md",
            source_digest=DIGEST_A,
        ),
        marketplace=MarketplacePackRef(
            repository="seanchatmangpt/ggen-marketplace",
            commit_sha=MARKETPLACE_SHA,
            pack_name="collective-skill-court-pack",
            pack_version="26.9.24",
            pack_source_digest=DIGEST_B,
        ),
        work_order=SjiraWorkOrderRef(
            identity="AFDE-CSKILL-26924-001",
            repository="seanchatmangpt/autofde-lab",
            base_sha=SUBJECT_SHA,
            evidence_ceiling="REPO_LOCAL_COURT",
            authority_ceiling="OBSERVE|SELECT|CONSTRUCT",
        ),
        exact_subject_sha=SUBJECT_SHA,
        oracle=ProbeObservation("oracle", "oracle", True, DIGEST_C),
        noop=ProbeObservation("noop", "noop", False, DIGEST_D),
        mutations=(
            ProbeObservation("skip-verifier", "mutation", False, DIGEST_E),
            ProbeObservation("ambient-do", "mutation", False, DIGEST_F),
        ),
    )


def test_admitted_court_projects_to_powerless_candidate_and_candidate_experience():
    spec = admitted_spec()
    compiler = CollectiveSkillCompiler()

    receipt = compiler.admit(spec)
    assert receipt.admitted is True
    assert receipt.standing == "ADMITTED"
    assert receipt.authority == "none"

    candidate = compiler.to_candidate(spec, receipt)
    assert candidate.authority == "none"
    assert candidate.evidence_payload["grants_do_authority"] is False
    assert candidate.evidence_payload["sjira"]["work_order"] == "AFDE-CSKILL-26924-001"

    experience = compiler.compile_machine_experience(
        spec,
        receipt,
        episode_evidence=EpisodeEvidence(
            episode_id="episode-skill-court-001",
            discovery_identity="collective-skill-court",
            discovery_resource_receipt="resource-receipt-001",
        ),
        equivalence_predicate_id="eq:collective-skill-court-v1",
    )
    assert experience.state == ExperienceState.CANDIDATE
    assert experience.known_route_id == ""
    assert experience.invalidation_set["court"] == spec.digest
    assert experience.invalidation_set["marketplace_pack"] == DIGEST_B
    assert experience.invalidation_set["marketplace_commit"] == MARKETPLACE_SHA


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (
            {"oracle": ProbeObservation("oracle", "oracle", False, DIGEST_C)},
            "ORACLE_FAILED",
        ),
        (
            {"noop": ProbeObservation("noop", "noop", True, DIGEST_D)},
            "NOOP_PASSED",
        ),
        (
            {
                "mutations": (
                    ProbeObservation("skip-verifier", "mutation", True, DIGEST_E),
                )
            },
            "MUTATION_SURVIVED:skip-verifier",
        ),
        (
            {
                "work_order": SjiraWorkOrderRef(
                    identity="AFDE-CSKILL-26924-001",
                    repository="seanchatmangpt/autofde-lab",
                    base_sha=SUBJECT_SHA,
                    evidence_ceiling="REPO_LOCAL_COURT",
                    authority_ceiling="AUTHORIZED_DO",
                )
            },
            "AUTHORITY_CEILING_EXCEEDED",
        ),
        (
            {
                "marketplace": MarketplacePackRef(
                    repository="seanchatmangpt/ggen-marketplace",
                    commit_sha="2" * 40,
                    pack_name="collective-skill-court-pack",
                    pack_version="26.9.24",
                    pack_source_digest=DIGEST_B,
                )
            },
            "MARKETPLACE_COMMIT_MISMATCH",
        ),
    ],
)
def test_court_refuses_failed_discriminators_and_identity_drift(change, reason):
    compiler = CollectiveSkillCompiler()
    spec = replace(admitted_spec(), **change)
    receipt = compiler.admit(spec)

    assert receipt.admitted is False
    assert reason in receipt.reasons
    with pytest.raises(ValueError, match="refused court"):
        compiler.to_candidate(spec, receipt)
