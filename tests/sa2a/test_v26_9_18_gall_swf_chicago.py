"""GALL Semantic Work Fabric frontier surfaces (v26.9.18 GALL SWF PRD §11.1, §15, §39, §43.3).

Chicago-style: real checkpoints, real selections, no mocks. Every claim tested here
is structural -- determinism, typed refusals, dict round-trips, and the authority
separation between planner output and any dispatch path.
"""

from __future__ import annotations

import dataclasses
import inspect
import json

import pytest

import autofde_lab.sa2a.gall_swf as gall_swf
from autofde_lab.sa2a.experience.types import ExperienceState, MachineExperience
from autofde_lab.sa2a.gall_swf import (
    REFUSED_DEPENDENCY,
    CandidatePlan,
    Checkpoint,
    FrontierSelection,
    GallStanding,
    MachineExperienceRecord,
    Recommendation,
    checkpoint_identity,
    project_to_hddl,
    recommend_frontier,
    select_frontier,
)

GALL_S_T1 = "https://semantic-a2a.dev/gall#S_t1"


def _checkpoint(
    repository: str,
    checkpoint_id: str,
    *,
    goal: str = "",
    dependencies: tuple[str, ...] = (),
    standing: GallStanding = GallStanding.UNKNOWN,
) -> Checkpoint:
    return Checkpoint(
        identity=checkpoint_identity(repository, checkpoint_id),
        repository=repository,
        base_sha="a1b2c3d4e5f6a7b8c9d0a1b2c3d4e5f6a7b8c9d0",
        goal=goal,
        dependencies=dependencies,
        standing=standing,
    )


def _dep_iri(repository: str, checkpoint_id: str) -> str:
    return checkpoint_identity(repository, checkpoint_id)


# ---------------------------------------------------------------------------
# Checkpoint identity + dict round-trip
# ---------------------------------------------------------------------------


def test_checkpoint_identity_follows_urn_grammar() -> None:
    assert checkpoint_identity("zoela_phx", "migrate-session-store") == (
        "urn:gall:checkpoint:zoela_phx:migrate-session-store"
    )


def test_checkpoint_identity_refuses_colon_components() -> None:
    with pytest.raises(ValueError, match="must not contain"):
        checkpoint_identity("bad:repo", "id")


def test_checkpoint_dict_round_trip() -> None:
    checkpoint = _checkpoint(
        "zoela_phx",
        "add-handwritten-ledger",
        goal="ledger shrinks monotonically",
        dependencies=(_dep_iri("zoela_phx", "raise-python-floor"),),
        standing=GallStanding.PARTIAL_ALIVE,
    )
    assert Checkpoint.from_dict(checkpoint.to_dict()) == checkpoint


def test_checkpoint_from_dict_fails_closed_on_unknown_standing() -> None:
    data = _checkpoint("zoela_phx", "id").to_dict()
    data["https://semantic-a2a.dev/gall#standing"] = "ALMOST_DONE"
    with pytest.raises(ValueError, match="not in the lawful vocabulary"):
        Checkpoint.from_dict(data)


def test_checkpoint_identity_must_agree_with_repository() -> None:
    with pytest.raises(ValueError, match="names repository"):
        Checkpoint(
            identity=checkpoint_identity("repo_a", "id"),
            repository="repo_b",
            base_sha="a" * 40,
        )


# ---------------------------------------------------------------------------
# PRD §11.1 frontier selection
# ---------------------------------------------------------------------------


def test_frontier_selects_unknown_checkpoint_with_alive_dependencies() -> None:
    done = _checkpoint("r", "done", standing=GallStanding.ALIVE)
    candidate = _checkpoint("r", "candidate", dependencies=(_dep_iri("r", "done"),))
    orphan = _checkpoint("r", "orphan")

    selection = select_frontier([done, candidate, orphan])

    assert isinstance(selection, FrontierSelection)
    assert selection.frontier == (
        _dep_iri("r", "candidate"),
        _dep_iri("r", "orphan"),
    )
    assert selection.alive == (_dep_iri("r", "done"),)
    assert selection.refusals == ()
    assert selection.excluded == ()


def test_frontier_reports_blocked_dependency_with_typed_refusal() -> None:
    broken = _checkpoint("r", "broken", standing=GallStanding.BUILD_BROKEN)
    blocked = _checkpoint("r", "blocked", dependencies=(_dep_iri("r", "broken"),))

    selection = select_frontier([blocked, broken])

    assert selection.frontier == ()
    assert len(selection.refusals) == 1
    refusal = selection.refusals[0]
    assert refusal.reason == REFUSED_DEPENDENCY
    assert refusal.checkpoint_iri == _dep_iri("r", "blocked")
    assert refusal.dependency_iri == _dep_iri("r", "broken")
    assert refusal.dependency_standing == GallStanding.BUILD_BROKEN


def test_frontier_dependency_absent_from_collection_is_fail_closed_unknown() -> None:
    # No dependency evidence observed => not ALIVE => blocked, never admitted.
    blocked = _checkpoint("r", "blocked", dependencies=(_dep_iri("elsewhere", "ghost"),))

    selection = select_frontier([blocked])

    assert selection.frontier == ()
    assert selection.refusals[0].dependency_standing == GallStanding.UNKNOWN
    assert selection.refusals[0].reason == REFUSED_DEPENDENCY


def test_frontier_excludes_already_alive_checkpoints() -> None:
    done = _checkpoint("r", "done", standing=GallStanding.ALIVE)

    selection = select_frontier([done])

    assert selection.frontier == ()
    assert selection.alive == (_dep_iri("r", "done"),)


def test_frontier_records_non_unknown_non_alive_exclusions() -> None:
    blocked = _checkpoint("r", "hard-blocked", standing=GallStanding.BLOCKED)

    selection = select_frontier([blocked])

    assert selection.frontier == ()
    assert selection.excluded == ((_dep_iri("r", "hard-blocked"), "BLOCKED"),)


def test_frontier_selection_is_deterministic_regardless_of_input_order() -> None:
    a = _checkpoint("r", "a", standing=GallStanding.ALIVE)
    b = _checkpoint("r", "b", dependencies=(_dep_iri("r", "a"),))
    c = _checkpoint("r", "c", standing=GallStanding.BLOCKED)

    forward = select_frontier([a, b, c])
    backward = select_frontier([c, b, a])

    assert dataclasses.astuple(forward) == dataclasses.astuple(backward)


def test_frontier_refuses_duplicate_identities() -> None:
    first = _checkpoint("r", "dup")
    second = _checkpoint("r", "dup")

    with pytest.raises(ValueError, match="duplicate checkpoint identity"):
        select_frontier([first, second])


# ---------------------------------------------------------------------------
# PRD §15/§43.3 HDDL projection
# ---------------------------------------------------------------------------


def _sample_frontier_checkpoints() -> list[Checkpoint]:
    base = _checkpoint("r", "base", goal="floor raised", standing=GallStanding.ALIVE)
    child = _checkpoint(
        "r",
        "child",
        goal="frontier represented",
        dependencies=(_dep_iri("r", "base"),),
    )
    other = _checkpoint("r", "other", goal="independent work")
    return [other, child, base]


def test_hddl_projection_shape_tasks_methods_objects() -> None:
    problem = project_to_hddl(_sample_frontier_checkpoints())

    assert problem["domain"] == "https://semantic-a2a.dev/gall#checkpoint-domain"
    assert problem["problem"] == "gall-checkpoint-frontier"
    assert problem["objects"] == [
        _dep_iri("r", "base"),
        _dep_iri("r", "child"),
        _dep_iri("r", "other"),
    ]
    # One task per checkpoint goal.
    assert [(task["name"], task["goal"]) for task in problem["tasks"]] == [
        (f"achieve-{_dep_iri('r', 'base')}", "floor raised"),
        (f"achieve-{_dep_iri('r', 'child')}", "frontier represented"),
        (f"achieve-{_dep_iri('r', 'other')}", "independent work"),
    ]
    # Decomposition: a checkpoint dependsOn its dependencies; leaves have no method.
    assert problem["methods"] == [
        {
            "name": f"decompose-{_dep_iri('r', 'child')}",
            "task": f"achieve-{_dep_iri('r', 'child')}",
            "ordered": True,
            "subtasks": [f"achieve-{_dep_iri('r', 'base')}"],
        }
    ]


def test_hddl_projection_is_deterministic() -> None:
    checkpoints = _sample_frontier_checkpoints()

    first = project_to_hddl(checkpoints)
    second = project_to_hddl(checkpoints)

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_hddl_projection_is_independent_of_input_order() -> None:
    forward = project_to_hddl(_sample_frontier_checkpoints())
    backward = project_to_hddl(list(reversed(_sample_frontier_checkpoints())))

    assert forward == backward


def test_hddl_projection_is_json_serializable() -> None:
    problem = project_to_hddl(_sample_frontier_checkpoints())

    encoded = json.dumps(problem)
    assert json.loads(encoded) == problem


# ---------------------------------------------------------------------------
# PRD §39 MachineExperience record
# ---------------------------------------------------------------------------


def _record(**overrides: object) -> MachineExperienceRecord:
    fields = {
        "s_t": "sha256:prior-semantic-state",
        "a_t": ("action.plan", "action.compile", "action.test"),
        "admission_t": ("action.plan", "action.test"),
        "execution_t": "sha256:construction-reference",
        "observation": "sha256:verifier-evidence",
        "s_t1": GallStanding.PARTIAL_ALIVE,
    }
    fields.update(overrides)
    return MachineExperienceRecord(**fields)  # type: ignore[arg-type]


def test_machine_experience_record_serialization_round_trip() -> None:
    record = _record()

    assert MachineExperienceRecord.from_dict(record.to_dict()) == record


def test_machine_experience_record_to_dict_is_json_serializable() -> None:
    encoded = json.dumps(_record().to_dict())

    assert "https://semantic-a2a.dev/gall#" in encoded


def test_machine_experience_record_admission_must_be_subset_of_available() -> None:
    with pytest.raises(ValueError, match="not in.*a_t"):
        _record(admission_t=("action.ghost",))


def test_machine_experience_record_standing_vocabulary_matches_checkpoints() -> None:
    for standing in GallStanding:
        record = _record(s_t1=standing)
        assert MachineExperienceRecord.from_dict(record.to_dict()).s_t1 == standing


def test_machine_experience_record_metadata_is_compatible_with_v26_9_17_schema() -> None:
    record = _record()

    metadata = record.to_metadata()

    # The v26.9.17 MachineExperience accepts the record as flat namespaced metadata
    # without disturbing its own lifecycle fields.
    experience = MachineExperience(
        experience_id="exp-1",
        semantic_class_id="class-1",
        source_episode_id="ep-1",
        source_candidate_digest="d1",
        source_admission_receipt="r1",
        discovery_identity="i1",
        discovery_resource_receipt="r2",
        solution_candidate_digest="d2",
        solution_admission_receipt="r3",
        compiled_artifact_ids=("a1",),
        equivalence_predicate_id="p1",
        state=ExperienceState.QUALIFIED,
        metadata=metadata,
    )
    assert experience.metadata[GALL_S_T1] == GallStanding.PARTIAL_ALIVE.value


# ---------------------------------------------------------------------------
# Authority separation (planner recommends; nothing here actuates)
# ---------------------------------------------------------------------------

_DISPATCH_VERBS = ("execute", "actuate", "dispatch", "perform", "apply", "run")


def test_recommendation_carries_no_dispatch_path() -> None:
    recommendation = recommend_frontier(_sample_frontier_checkpoints())

    assert isinstance(recommendation, Recommendation)
    assert isinstance(recommendation.plan, CandidatePlan)
    assert recommendation.advisory is True
    assert recommendation.plan.advisory is True
    for obj in (recommendation, recommendation.plan):
        for verb in _DISPATCH_VERBS:
            assert not hasattr(obj, verb)


def test_module_public_api_exposes_no_dispatch_entry_point() -> None:
    exported = set(gall_swf.__all__)
    for verb in _DISPATCH_VERBS:
        assert verb not in exported
        assert not any(verb in name.lower() for name in exported)
    for name, value in vars(gall_swf).items():
        if name.startswith("_"):
            continue
        assert name not in _DISPATCH_VERBS
        if inspect.isfunction(value):
            assert not any(
                verb in name.lower() for verb in _DISPATCH_VERBS
            ), f"public function {name} looks like a dispatch path"


def test_no_public_function_accepts_a_recommendation_parameter() -> None:
    for name in gall_swf.__all__:
        value = getattr(gall_swf, name)
        if not inspect.isfunction(value):
            continue
        signature = inspect.signature(value)
        for parameter in signature.parameters.values():
            annotation = parameter.annotation
            assert annotation is not Recommendation
            assert annotation is not CandidatePlan


def test_recommendation_refuses_truthiness_so_advisory_cannot_decide() -> None:
    recommendation = recommend_frontier(_sample_frontier_checkpoints())

    with pytest.raises(TypeError, match="advisory"):
        bool(recommendation)


def test_recommend_frontier_advises_exactly_the_admissible_frontier() -> None:
    done = _checkpoint("r", "done", standing=GallStanding.ALIVE)
    ready = _checkpoint("r", "ready", dependencies=(_dep_iri("r", "done"),))
    blocked = _checkpoint(
        "r",
        "blocked",
        dependencies=(_dep_iri("r", "ghost"),),
    )

    recommendation = recommend_frontier([blocked, ready, done])

    assert recommendation.plan.frontier == (_dep_iri("r", "ready"),)
