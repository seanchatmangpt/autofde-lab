"""Episode₂ replay-contract tests (HDDL sa2a-v26.9.17 domain §6-§7).

Covers the second crown:

    Episode₂: KNOWN -> Replay  under  frontier_clean(Episode₂) = true.

Proves BOTH directions of the route gate:

1. An episode structurally equivalent to the admitted Episode₁ experience
   routes to KNOWN and replays with ZERO frontier use (the counting allocator
   is invoked exactly once -- by Episode₁'s real discovery, never by Episode₂).
2. A non-equivalent episode is refused (EQUIVALENCE_FAILED, mismatched fields
   named) and NEVER reaches replay (no ReplayRoute exists; the counting
   ReplayEngine is never invoked).

Plus the structural enforcement the HDDL demands ("Equivalence cannot be
analogy"; "There is intentionally no explore-unknown subtask in the replay
method"):

- the equivalence proof is a typed field comparison over
  goal/subject/steps/bounds only -- a forged "equivalent" verdict cannot route
  a structurally different episode (the route re-proves from the records);
- the Episode₂ replay path cannot express frontier allocation: the module does
  not import the frontier allocator, and ``replay_known_transition``'s
  signature has no allocator/budget/explore parameter;
- a forged ReplayRoute lacking the KNOWN/frontier-clean/replay-contract facts
  is refused by the transition's own precondition teeth.

Style follows the existing counting-collaborator harness
(``tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py``):
real collaborators, real delegation, counters read as final integer state; no
``unittest.mock``.
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest

import autofde_lab.sa2a.brce.episode_replay as episode_replay_module
from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import ConsequenceBoundary, ExecutionEnvelope
from autofde_lab.sa2a.brce.episode_replay import (
    AdmittedMachineExperience,
    Episode1TransitionSteps,
    EpisodeReplayContractError,
    EpisodeRecord,
    EquivalenceReport,
    EquivalenceVerdict,
    ExperienceAdmissionRefusal,
    ReplayRoute,
    ReplayRouteRefusal,
    admit_machine_experience,
    prove_semantic_equivalence,
    replay_known_transition,
    route_known_replay,
)
from autofde_lab.sa2a.brce.receipts import ReceiptStore, TerminalReceiptState
from autofde_lab.sa2a.brce.replay import ReplayEngine, ReplayStanding, ReplayVerdict
from autofde_lab.sa2a.unknown.allocator import CMCACandidateAllocator, ExplorationBudget
from autofde_lab.sa2a.unknown.compilation import MachineExperienceCompiler
from autofde_lab.sa2a.unknown.resolution import (
    EpistemicState,
    UnknownQuery,
    UnknownResolutionPipeline,
)

GOAL = "urn:action:restart_pod"
SUBJECT = "urn:cap:cluster:pods"


class JournalActuator:
    """Real actuator with real, observable appended state (no call assertions)."""

    def __init__(self) -> None:
        self.applied: list[dict] = []

    def actuate(self, action_iri: str, target_resource: str, parameters: dict) -> dict:
        evidence = {"applied": True, "action": action_iri, "params": dict(parameters)}
        self.applied.append(evidence)
        return evidence

    def actuator_digest(self) -> str:
        return "actuator:journal:v1"


class JournalVerifier:
    """Real, independent postcondition verifier (distinct object from the actuator)."""

    def verify_postcondition(
        self, action_iri: str, target_resource: str, parameters: dict, evidence: dict | None
    ) -> bool:
        return evidence is not None and evidence.get("applied") is True

    def verifier_digest(self) -> str:
        return "verifier:journal:v1"


class CountingAllocator(CMCACandidateAllocator):
    """Real allocator subclass counting real allocate() invocations."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.allocate_call_count = 0

    def allocate(self, **kwargs):
        self.allocate_call_count += 1
        return super().allocate(**kwargs)


class CountingReplayEngine(ReplayEngine):
    """Real ReplayEngine subclass counting real verify_chain() invocations."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.verify_chain_call_count = 0

    def verify_chain(self, *args, **kwargs):
        self.verify_chain_call_count += 1
        return super().verify_chain(*args, **kwargs)


def _bounds() -> ExplorationBudget:
    return ExplorationBudget(max_compute_ticks=1000, max_tokens=10000, max_experiments=5)


def _episode_one_record(bounds: ExplorationBudget) -> EpisodeRecord:
    """Episode₁'s recorded transition: the HDDL §2 ordered subtasks as step keys."""
    return EpisodeRecord(
        episode_id="episode-1",
        goal=GOAL,
        subject=SUBJECT,
        steps=Episode1TransitionSteps,
        bounds=bounds,
    )


def _admitted_experience(bounds: ExplorationBudget) -> AdmittedMachineExperience:
    """Real Episode₁ experience: real compiler output admitted through the real court."""
    compiler = MachineExperienceCompiler()
    compilation = compiler.compile_candidate_experience(
        receipt_id="exp-comp-episode-1",
        resolved_items=[("ex:status 'CRASH_LOOP'", "restart_pod remedy", None)],
    )
    receipt = admit_machine_experience(compilation, _episode_one_record(bounds))
    assert isinstance(receipt, AdmittedMachineExperience)
    return receipt


def _episode_one_receipt_records() -> list[dict]:
    """One real executed DO from Episode₁, recorded through the real boundary.

    This is the causal chain Episode₂'s replay re-verifies offline (Replay != DO).
    """
    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-ep2-episode-1",
            subject_id="agent-alice",
            action_iri=GOAL,
            target_resource_iri=SUBJECT,
        )
    )
    store = ReceiptStore()
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=JournalActuator(),
        verifier=JournalVerifier(),
        receipt_store=store,
    )
    result = boundary.execute(
        ExecutionEnvelope(
            idempotency_token="idemp-episode-1",
            action_iri=GOAL,
            target_resource=SUBJECT,
            actor_id="agent-alice",
            grant_id="grant-ep2-episode-1",
            parameters={"pod_id": "payment-api-pod-42"},
        )
    )
    assert result.success is True
    assert result.state == TerminalReceiptState.EXECUTED
    return store.all_records()


# =============================================================================
# Direction 1: equivalent episode routes to KNOWN and replays, zero frontier.
# =============================================================================


def test_equivalent_episode_routes_and_replays_with_zero_frontier_use():
    """The reinforcement proof, measured end to end.

    Episode₁: real discovery through the real frontier (allocator count 1),
    real compilation, real admission court, real executed DO with receipts.
    Episode₂: identical transition (fresh episode id only) -> EQUIVALENT ->
    routed KNOWN -> replayed offline. The counting allocator's final count is
    still 1: Episode₂ consumed ZERO frontier.
    """
    bounds = _bounds()

    # --- Episode₁: the one lawful frontier purchase ------------------------
    allocator = CountingAllocator()
    pipeline = UnknownResolutionPipeline(allocator=allocator)
    plan, _ = pipeline.route_unknown_to_frontier(
        [UnknownQuery(query_id="q-crash-loop", predicate_or_topic="ex:status")], bounds
    )
    assert len(plan.allocations) == 1
    assert allocator.allocate_call_count == 1

    experience = _admitted_experience(bounds)
    records = _episode_one_receipt_records()

    # --- Episode₂: structurally identical transition, new identity ---------
    episode_two = dataclasses.replace(_episode_one_record(bounds), episode_id="episode-2")
    report = prove_semantic_equivalence(episode_two, experience.record)
    assert report.verdict is EquivalenceVerdict.EQUIVALENT
    assert report.mismatched_fields == ()
    # The proof is content-addressed and deterministic: re-proving yields the
    # same digest, so the receipt can be reconciled later.
    assert (
        report.proof_digest == prove_semantic_equivalence(episode_two, experience.record).proof_digest
    )

    route = route_known_replay(episode_two, experience, report, frontier_clean=True)
    assert isinstance(route, ReplayRoute)
    assert route.epistemic_standing is EpistemicState.KNOWN
    assert route.frontier_clean is True
    assert route.replay_contract is True

    engine = CountingReplayEngine()
    outcome = replay_known_transition(route, replay_engine=engine, receipt_records=records)

    assert outcome.replayed is True
    assert outcome.replay_verdict is ReplayVerdict.VALID
    assert outcome.replay_standing is ReplayStanding.ALIVE
    assert outcome.frontier_clean_retained is True
    assert outcome.errors == ()

    # Measured, not asserted: the replay consulted the real engine exactly once
    # and the real allocator ZERO additional times.
    assert engine.verify_chain_call_count == 1
    assert allocator.allocate_call_count == 1, (
        f"expected Episode₂ to consume zero frontier; allocator was invoked "
        f"{allocator.allocate_call_count} times total (Episode₁ accounts for 1)."
    )


# =============================================================================
# Direction 2: non-equivalent episode is refused, never reaches replay.
# =============================================================================


@pytest.mark.parametrize(
    "field, mutate",
    [
        ("goal", lambda r: dataclasses.replace(r, goal="urn:action:drain_node")),
        ("subject", lambda r: dataclasses.replace(r, subject="urn:cap:cluster:nodes")),
        ("steps", lambda r: dataclasses.replace(r, steps=r.steps[:-1])),
        ("steps", lambda r: dataclasses.replace(r, steps=tuple(reversed(r.steps)))),
        (
            "bounds",
            lambda r: dataclasses.replace(r, bounds=dataclasses.replace(r.bounds, max_tokens=1)),
        ),
    ],
    ids=["goal-differs", "subject-differs", "step-missing", "steps-reordered", "bounds-differ"],
)
def test_non_equivalent_episode_refused_and_never_reaches_replay(field, mutate):
    """Every structural mismatch yields EQUIVALENCE_FAILED and NO route.

    ``replay_known_transition`` accepts only a ``ReplayRoute``; the refusal
    carries no route-shaped value, so there is no path from refusal to replay.
    The counting engine's final count of 0 is the measured "never reached".
    """
    bounds = _bounds()
    experience = _admitted_experience(bounds)
    records = _episode_one_receipt_records()

    episode_two = mutate(dataclasses.replace(_episode_one_record(bounds), episode_id="episode-2"))
    report = prove_semantic_equivalence(episode_two, experience.record)

    assert report.verdict is EquivalenceVerdict.EQUIVALENCE_FAILED
    assert field in report.mismatched_fields

    refusal = route_known_replay(episode_two, experience, report, frontier_clean=True)

    assert isinstance(refusal, ReplayRouteRefusal)
    assert not isinstance(refusal, ReplayRoute)
    assert "REFUSED_EQUIVALENCE_FAILED" in refusal.reasons
    assert field in refusal.mismatched_fields
    # No route-shaped attribute exists on the refusal: nothing here can be fed
    # to replay_known_transition.
    assert not hasattr(refusal, "epistemic_standing")
    assert not hasattr(refusal, "frontier_clean")

    engine = CountingReplayEngine()
    assert engine.verify_chain_call_count == 0
    # The Episode₁ records sit untouched: nothing replayed, nothing mutated.
    assert len(records) > 0


# =============================================================================
# The hard negative condition: frontier_clean is load-bearing (§6).
# =============================================================================


def test_route_refuses_when_frontier_not_clean_even_if_equivalent():
    """route-known-replay's hard negative precondition: no frontier_clean, no route."""
    bounds = _bounds()
    experience = _admitted_experience(bounds)
    episode_two = dataclasses.replace(_episode_one_record(bounds), episode_id="episode-2")
    report = prove_semantic_equivalence(episode_two, experience.record)
    assert report.verdict is EquivalenceVerdict.EQUIVALENT

    refusal = route_known_replay(episode_two, experience, report, frontier_clean=False)

    assert isinstance(refusal, ReplayRouteRefusal)
    assert "REFUSED_FRONTIER_NOT_CLEAN" in refusal.reasons
    assert not hasattr(refusal, "epistemic_standing")


# =============================================================================
# Fail-closed against forged / stale / judgment-produced equivalence verdicts.
# =============================================================================


def test_stale_equivalence_proof_for_another_episode_cannot_route():
    """A valid proof binding episode-3 cannot be reused to route episode-2."""
    bounds = _bounds()
    experience = _admitted_experience(bounds)
    episode_two = dataclasses.replace(_episode_one_record(bounds), episode_id="episode-2")
    episode_three = dataclasses.replace(_episode_one_record(bounds), episode_id="episode-3")

    report = prove_semantic_equivalence(episode_three, experience.record)
    assert report.verdict is EquivalenceVerdict.EQUIVALENT

    refusal = route_known_replay(episode_two, experience, report, frontier_clean=True)
    assert isinstance(refusal, ReplayRouteRefusal)
    assert "REFUSED_EQUIVALENCE_PROOF_MISMATCH" in refusal.reasons


def test_forged_equivalent_verdict_cannot_route_structurally_different_episode():
    """The analogy channel is closed: even a fabricated EQUIVALENT report with
    correctly bound ids cannot route when the transitions actually differ --
    the route re-proves equivalence structurally from the records themselves."""
    bounds = _bounds()
    experience = _admitted_experience(bounds)
    different_episode = dataclasses.replace(
        _episode_one_record(bounds), episode_id="episode-2", goal="urn:action:drain_node"
    )

    forged = EquivalenceReport(
        new_episode_id="episode-2",
        old_episode_id="episode-1",
        verdict=EquivalenceVerdict.EQUIVALENT,
        compared_fields=("goal", "subject", "steps", "bounds"),
        mismatched_fields=(),
        proof_digest="fabricated",
    )

    refusal = route_known_replay(different_episode, experience, forged, frontier_clean=True)
    assert isinstance(refusal, ReplayRouteRefusal)
    assert "REFUSED_EQUIVALENCE_PROOF_INVALID" in refusal.reasons


# =============================================================================
# Admission court: an uncompiled experience cannot back a replay contract.
# =============================================================================


def test_experience_admission_refuses_empty_compilation():
    compiler = MachineExperienceCompiler()
    empty = compiler.compile_candidate_experience(receipt_id="exp-comp-empty", resolved_items=[])
    refusal = admit_machine_experience(empty, _episode_one_record(_bounds()))

    assert isinstance(refusal, ExperienceAdmissionRefusal)
    assert "REFUSED_EMPTY_EXPERIENCE" in refusal.reasons


def test_admitted_experience_declares_contract_facts_inline():
    """The (experience-admitted ∧ replay-contract) facts are inspectable
    declared literals on the object, never inferred from absence."""
    experience = _admitted_experience(_bounds())
    assert experience.admitted is True
    assert experience.replay_contract is True
    assert experience.rule_fingerprints  # real compiled provenance


# =============================================================================
# Structural frontier exclusion: the replay path cannot reach the allocator.
# =============================================================================


def test_episode2_module_never_imports_frontier_machinery():
    """Import-graph isolation: the Episode₂ module binds neither the frontier
    allocator nor the UNKNOWN pipeline -- there is no object it could call."""
    assert not hasattr(episode_replay_module, "CMCACandidateAllocator")
    assert not hasattr(episode_replay_module, "UnknownResolutionPipeline")
    assert not hasattr(episode_replay_module, "explore_unknown")


def test_replay_transition_signature_cannot_express_frontier_allocation():
    """The replay routine's parameters are exactly route/engine/records: no
    allocator, budget, or exploration channel exists to pass frontier through."""
    params = inspect.signature(replay_known_transition).parameters
    assert set(params) == {"route", "replay_engine", "receipt_records"}
    for name in params:
        assert "alloc" not in name
        assert "budget" not in name
        assert "explore" not in name
        assert "frontier" not in name


def test_forged_route_without_contract_facts_is_refused_by_transition():
    """Precondition teeth: a hand-built route lacking the KNOWN / frontier-clean
    / replay-contract facts cannot drive replay_known_transition."""
    forged = ReplayRoute(
        episode_id="episode-2",
        experience_id="exp-forged",
        epistemic_standing=EpistemicState.UNKNOWN,
        frontier_clean=False,
        replay_contract=False,
    )
    with pytest.raises(EpisodeReplayContractError):
        replay_known_transition(forged, replay_engine=ReplayEngine(), receipt_records=[])
