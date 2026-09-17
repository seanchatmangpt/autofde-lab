"""Episode₂ replay contract: prove-semantic-equivalence, route-known-replay, frontier_clean (HDDL sa2a-v26.9.17 §6-§7).

Implements the KNOWN -> Replay half of the self-reinforcing SA2A loop:

    Episode₁: UNKNOWN -> Experience -> KNOWN   (sa2a/unknown/, already admitted)
    Episode₂: KNOWN -> Replay                  (this module)

under the hard FOND invariant (§6):

    frontier_clean(Episode₂) = true  through completion.

There is intentionally NO ``explore-unknown`` subtask on the replay path. This
module makes that absence structural, not conventional:

1. ``prove_semantic_equivalence`` is a typed structural comparison over the
   machine experience record's goal / subject / steps / bounds fields. It reads
   nothing else -- there is no channel through which analogy or LLM judgment
   could enter ("Equivalence cannot be analogy", §6).
2. ``route_known_replay`` is the sole constructor of ``ReplayRoute`` and enforces
   the exact §6 route precondition:
       equivalent(e, episode-1) AND experience-admitted(x)
       AND replay-contract(x) AND frontier_clean(e).
   It fail-closed re-verifies the equivalence structurally from the records
   themselves, so a forged or stale "equivalent" verdict cannot route.
3. ``replay_known_transition`` accepts NO allocator, budget, or frontier
   parameter -- its signature cannot express frontier allocation -- and this
   module never imports ``CMCACandidateAllocator`` or
   ``UnknownResolutionPipeline`` (import-graph isolation, asserted by test).
   The replay of the known transition is the offline deterministic
   re-verification of the recorded receipt chain (Replay != DO, §32) via
   ``ReplayEngine.verify_chain``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from autofde_lab.sa2a.brce.replay import ReplayEngine, ReplayStanding, ReplayVerdict
from autofde_lab.sa2a.unknown.allocator import ExplorationBudget
from autofde_lab.sa2a.unknown.compilation import ExperienceCompilationReceipt
from autofde_lab.sa2a.unknown.resolution import EpistemicState


class EpisodeReplayContractError(RuntimeError):
    """Raised when replay_known_transition is invoked on a route violating the Episode₂ contract."""


# The typed structural transition recorded for an episode. The step keys are the
# HDDL ordered-subtask names of the episode method (§2 for Episode₁), so the
# record is grounded in the domain rather than in free prose.
Episode1TransitionSteps = (
    "reconstruct_world",
    "classify_problem",
    "solve_classified_problem",
    "construct_plan",
    "bound_allocation",
    "manufacture",
    "admit_authority",
    "dispatch_command",
    "execute_command",
    "close_receipt",
    "independent_verify",
    "observe_process",
    "record_feedback",
    "create_machine_experience",
    "admit_machine_experience",
    "issue_affidavit",
)


@dataclass(frozen=True, slots=True)
class EpisodeRecord:
    """Typed structural characterization of one episode's transition (§6).

    Only these four fields (goal / subject / steps / bounds) are ever compared
    by ``prove_semantic_equivalence``. ``episode_id`` is identity, not
    structure: two episodes with identical transitions are structurally
    equivalent regardless of their ids.
    """

    episode_id: str
    goal: str  # goal / action IRI the episode pursues
    subject: str  # subject / target capability the episode acts on
    steps: tuple[str, ...]  # ordered structural transition steps (HDDL subtask keys)
    bounds: ExplorationBudget  # typed allocation bounds under which the transition ran

    @property
    def transition_signature(self) -> str:
        """Content-addressed structural identity of the transition (ignores episode_id)."""
        payload = {
            "goal": self.goal,
            "subject": self.subject,
            "steps": list(self.steps),
            "bounds": {
                "max_compute_ticks": self.bounds.max_compute_ticks,
                "max_tokens": self.bounds.max_tokens,
                "max_experiments": self.bounds.max_experiments,
                "concurrency_lanes": self.bounds.concurrency_lanes,
            },
        }
        dumped = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


class EquivalenceVerdict(str, Enum):
    """HDDL §6 prove-semantic-equivalence oneof outcome."""

    EQUIVALENT = "EQUIVALENT"
    EQUIVALENCE_FAILED = "EQUIVALENCE_FAILED"


_COMPARED_FIELDS = ("goal", "subject", "steps", "bounds")


@dataclass(frozen=True, slots=True)
class EquivalenceReport:
    """Receipt of one structural equivalence proof (§6 k2)."""

    new_episode_id: str
    old_episode_id: str
    verdict: EquivalenceVerdict
    compared_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    proof_digest: str


def prove_semantic_equivalence(
    new: EpisodeRecord, old: EpisodeRecord
) -> EquivalenceReport:
    """Prove (or fail to prove) structural equivalence of two episode transitions (§6).

    Pure typed field comparison over goal / subject / steps / bounds:

    - ``goal`` and ``subject`` compare by exact value;
    - ``steps`` compares as an ORDERED sequence (permutation is a mismatch);
    - ``bounds`` compares by the typed ``ExplorationBudget`` field-wise equality.

    No other input is read: there is no analogue of "the episodes feel alike".
    The check may not be refused, bypassed, or augmented by judgment.
    """
    mismatched: list[str] = []
    if new.goal != old.goal:
        mismatched.append("goal")
    if new.subject != old.subject:
        mismatched.append("subject")
    if new.steps != old.steps:
        mismatched.append("steps")
    if new.bounds != old.bounds:
        mismatched.append("bounds")

    verdict = (
        EquivalenceVerdict.EQUIVALENT if not mismatched else EquivalenceVerdict.EQUIVALENCE_FAILED
    )
    proof_payload = {
        "new": new.transition_signature,
        "old": old.transition_signature,
        "verdict": verdict.value,
    }
    dumped = json.dumps(proof_payload, sort_keys=True, separators=(",", ":"))
    return EquivalenceReport(
        new_episode_id=new.episode_id,
        old_episode_id=old.episode_id,
        verdict=verdict,
        compared_fields=_COMPARED_FIELDS,
        mismatched_fields=tuple(mismatched),
        proof_digest=hashlib.sha256(dumped.encode("utf-8")).hexdigest(),
    )


@dataclass(frozen=True, slots=True)
class AdmittedMachineExperience:
    """The HDDL §5 admission outcome as inspectable typed facts (§6 method precondition).

    ``admitted`` and ``replay_contract`` are declared invariant literals in the
    same spirit as ``CandidateResolution.authority: Literal["none"]``: the facts
    are always present and always inspectable, never inferred from absence. The
    only lawful constructor is :func:`admit_machine_experience` -- the admission
    court; a bare construction is not an admission and carries no court receipt.
    """

    experience_id: str
    record: EpisodeRecord  # the Episode₁ transition this experience records
    rule_fingerprints: tuple[str, ...]  # provenance: compiled rules behind the experience
    admitted: Literal[True]
    replay_contract: Literal[True]


@dataclass(frozen=True, slots=True)
class ExperienceAdmissionRefusal:
    """Typed refusal of machine-experience admission (§5: candidate-refused candidate-experience)."""

    reasons: tuple[str, ...]


def admit_machine_experience(
    compilation: ExperienceCompilationReceipt, record: EpisodeRecord
) -> AdmittedMachineExperience | ExperienceAdmissionRefusal:
    """Admission court for machine experience (§5 admit-machine-experience).

    Requires a real compilation receipt (at least one compiled deterministic
    rule -- an experience with no compiled content cannot back a replay) and a
    well-formed episode record. Refusal is typed; it never raises.
    """
    reasons: list[str] = []
    if compilation.compiled_rule_count == 0 or not compilation.rule_fingerprints:
        reasons.append("REFUSED_EMPTY_EXPERIENCE")
    if not record.goal.strip():
        reasons.append("REFUSED_NO_GOAL")
    if not record.subject.strip():
        reasons.append("REFUSED_NO_SUBJECT")
    if not record.steps:
        reasons.append("REFUSED_NO_TRANSITION_STEPS")
    if reasons:
        return ExperienceAdmissionRefusal(reasons=tuple(reasons))

    digest_payload = json.dumps(
        {
            "compilation_digest": compilation.digest,
            "transition_signature": record.transition_signature,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    experience_id = f"exp-{hashlib.sha256(digest_payload.encode('utf-8')).hexdigest()[:12]}"
    return AdmittedMachineExperience(
        experience_id=experience_id,
        record=record,
        rule_fingerprints=compilation.rule_fingerprints,
        admitted=True,
        replay_contract=True,
    )


@dataclass(frozen=True, slots=True)
class ReplayRoute:
    """The §6 route-known-replay effect: the episode is KNOWN, frontier-clean.

    Constructible ONLY through :func:`route_known_replay` after the full
    precondition holds. Carries the frontier_clean and replay-contract facts the
    replay transition will re-assert.
    """

    episode_id: str
    experience_id: str
    epistemic_standing: EpistemicState  # always KNOWN on a lawful route
    frontier_clean: Literal[True]
    replay_contract: Literal[True]


@dataclass(frozen=True, slots=True)
class ReplayRouteRefusal:
    """Typed refusal of the replay route.

    Deliberately carries NO route-shaped attribute: there is no value here that
    :func:`replay_known_transition` will accept, so a refusal cannot be walked
    into a replay by shape.
    """

    episode_id: str
    experience_id: str
    reasons: tuple[str, ...]
    mismatched_fields: tuple[str, ...] = ()


def route_known_replay(
    new: EpisodeRecord,
    experience: AdmittedMachineExperience,
    equivalence: EquivalenceReport,
    *,
    frontier_clean: bool,
) -> ReplayRoute | ReplayRouteRefusal:
    """Gate the KNOWN route (§6 route-known-replay).

    Enforces the exact HDDL precondition as an all-or-nothing court (all
    failures reported, none silent):

    1. ``equivalence.verdict`` is EQUIVALENT;
    2. the proof binds THESE objects (new_episode_id / old_episode_id match);
    3. the structural truth is re-verified from the records themselves, so a
       forged, stale, or judgment-produced "equivalent" verdict cannot route
       when the transitions actually differ;
    4. the experience is admitted and carries a replay contract;
    5. ``frontier_clean`` holds for the new episode.

    On success the effect is ``(known ?e)``: a :class:`ReplayRoute` standing at
    ``EpistemicState.KNOWN`` with frontier-clean retained.
    """
    reasons: list[str] = []
    mismatched_fields: tuple[str, ...] = ()

    if equivalence.verdict is not EquivalenceVerdict.EQUIVALENT:
        reasons.append("REFUSED_EQUIVALENCE_FAILED")
        mismatched_fields = equivalence.mismatched_fields
    if (
        equivalence.new_episode_id != new.episode_id
        or equivalence.old_episode_id != experience.record.episode_id
    ):
        reasons.append("REFUSED_EQUIVALENCE_PROOF_MISMATCH")
    # Fail-closed structural re-verification: the route re-proves equivalence
    # itself; the caller's report is never trusted over the records.
    if new.transition_signature != experience.record.transition_signature:
        reasons.append("REFUSED_EQUIVALENCE_PROOF_INVALID")
    if experience.admitted is not True:
        reasons.append("REFUSED_EXPERIENCE_NOT_ADMITTED")
    if experience.replay_contract is not True:
        reasons.append("REFUSED_NO_REPLAY_CONTRACT")
    if not frontier_clean:
        reasons.append("REFUSED_FRONTIER_NOT_CLEAN")

    if reasons:
        return ReplayRouteRefusal(
            episode_id=new.episode_id,
            experience_id=experience.experience_id,
            reasons=tuple(reasons),
            mismatched_fields=mismatched_fields,
        )

    return ReplayRoute(
        episode_id=new.episode_id,
        experience_id=experience.experience_id,
        epistemic_standing=EpistemicState.KNOWN,
        frontier_clean=True,
        replay_contract=True,
    )


@dataclass(frozen=True, slots=True)
class ReplayOutcome:
    """Result of replaying the known transition (§6 replay-known-transition)."""

    episode_id: str
    experience_id: str
    replayed: bool
    replay_verdict: ReplayVerdict
    replay_standing: ReplayStanding
    frontier_clean_retained: bool
    errors: tuple[str, ...] = ()


def replay_known_transition(
    route: ReplayRoute,
    *,
    replay_engine: ReplayEngine,
    receipt_records: Sequence[Mapping[str, Any]],
) -> ReplayOutcome:
    """Replay the known transition WITHOUT frontier or re-execution (§6 k4).

    Preconditions re-asserted fail-closed from the route itself:
    ``(known ?e)`` ∧ ``frontier-clean ?e`` ∧ ``replay-contract ?x``.

    Structural frontier exclusion: this signature accepts no allocator, budget,
    or exploration parameter, and this module does not import the frontier
    machinery. The replay is the offline deterministic re-verification of the
    recorded receipt chain (Replay != DO, §32).
    """
    if route.epistemic_standing is not EpistemicState.KNOWN:
        raise EpisodeReplayContractError(
            f"Episode '{route.episode_id}' is not KNOWN; replay-known-transition precondition violated."
        )
    if route.frontier_clean is not True:
        raise EpisodeReplayContractError(
            f"Episode '{route.episode_id}' is not frontier_clean; replay-known-transition precondition violated."
        )
    if route.replay_contract is not True:
        raise EpisodeReplayContractError(
            f"Experience '{route.experience_id}' carries no replay contract; "
            "replay-known-transition precondition violated."
        )

    report = replay_engine.verify_chain(receipt_records)
    return ReplayOutcome(
        episode_id=route.episode_id,
        experience_id=route.experience_id,
        replayed=report.verdict is ReplayVerdict.VALID,
        replay_verdict=report.verdict,
        replay_standing=report.standing,
        frontier_clean_retained=route.frontier_clean,
        errors=tuple(report.errors),
    )
