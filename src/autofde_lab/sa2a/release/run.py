"""ReleaseRun: the v26.9.17 crown orchestrator (PRD §12; ARD §50).

"Crown command semantics... SHALL NOT contain independent duplicated semantic
logic" (ARD §50): every stage below is a call into an already-real, already-tested
component (`SubjectResolver`, `Episode1Runner`, `Episode2Runner`, the real
`ReplayEngine`, the real subprocess `fresh_consumer` verifier) -- this module only
sequences them and enforces the typed `ReleaseState` transition law
(`state_machine.py`), it computes no admission/authority/consequence verdict itself.

Each stage transition is enforced through `validate_release_transition()` for real
(not merely narrated): an attempt to skip a required predecessor raises, the same
discipline `state_machine.py`'s own docstring describes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from autofde_lab.sa2a.brce.replay import ReplayEngine, ReplayReport, ReplayStanding
from autofde_lab.sa2a.composition.exact_subject import ExactSubject
from autofde_lab.sa2a.composition.resolver import SubjectResolutionError, SubjectResolver
from autofde_lab.sa2a.episode.episode1 import Episode1Result, Episode1Runner
from autofde_lab.sa2a.episode.episode2 import Episode2Result, Episode2Runner
from autofde_lab.sa2a.experience.compiler import ArtifactRegistry
from autofde_lab.sa2a.experience.known_route import KnownRouteRegistry
from autofde_lab.sa2a.release.state_machine import ReleaseState, validate_release_transition
from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownQuery


@dataclass(frozen=True, slots=True)
class ReleaseRunResult:
    state: ReleaseState
    exact_subject: Optional[ExactSubject]
    episode1: Optional[Episode1Result]
    episode2: Optional[Episode2Result]
    replay_report: Optional[ReplayReport]
    fresh_consumer_standing: Optional[dict]
    reason: str = ""

    def to_receipt(self) -> dict[str, Any]:
        """PRD §63-shaped machine-readable final result."""
        ep1 = self.episode1
        ep2 = self.episode2
        return {
            "release": self.exact_subject.release_id if self.exact_subject else "",
            "composition_digest": self.exact_subject.composition_digest if self.exact_subject else "",
            "profile": self.exact_subject.semantic_profile if self.exact_subject else "",
            "episode_1": ep1.episode.to_dict() if ep1 else None,
            "machine_experience": (
                {
                    "experience_id": ep1.machine_experience.experience_id,
                    "state": ep1.machine_experience.state.value,
                    "known_route_id": ep1.machine_experience.known_route_id,
                }
                if ep1
                else None
            ),
            "episode_2": ep2.episode.to_dict() if ep2 else None,
            "replay": (
                {"verdict": self.replay_report.verdict.value, "standing": self.replay_report.standing.value}
                if self.replay_report
                else None
            ),
            "fresh_consumer": (
                {"verdict": self.fresh_consumer_standing.get("verdict")} if self.fresh_consumer_standing else None
            ),
            "standing": self.state.value,
            "reason": self.reason,
        }


class ReleaseRun:
    """Orchestrates one v26.9.17 crown run (PRD §12, ARD §50)."""

    def __init__(self, *, work_dir: Path) -> None:
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.state = ReleaseState.CREATED
        self.history: list[ReleaseState] = [self.state]

    def _goto(self, target: ReleaseState) -> None:
        validate_release_transition(self.state, target)
        self.state = target
        self.history.append(target)

    def run(
        self,
        *,
        candidate_manifest: Mapping[str, Any],
        semantic_class_id: str,
        episode1_query: UnknownQuery,
        episode1_discover: Callable[[UnknownQuery], CandidateResolution],
        equivalence_predicate: Callable[[Any], bool],
        equivalence_predicate_id: str,
        probe_input: str,
        action_iri: str,
        episode1_target_resource: str,
        episode2_fresh_candidate: CandidateResolution,
        episode2_target_resource: str,
    ) -> ReleaseRunResult:
        state_dir = self.work_dir / "state"
        journal_path = self.work_dir / "journal.json"
        receipt_store_dir = self.work_dir / "receipts"

        # --- SUBJECT_FENCED
        try:
            exact_subject = SubjectResolver().resolve(candidate_manifest)
        except SubjectResolutionError as exc:
            self._goto(ReleaseState.REFUSED)
            return ReleaseRunResult(self.state, None, None, None, None, None, reason=str(exc))
        self._goto(ReleaseState.SUBJECT_FENCED)

        # --- PREFLIGHTED: fail closed on any repository pinned "dirty:" (ARD §61 --
        # a dirty worktree SHALL prevent final release standing).
        dirty = [r.name for r in exact_subject.repositories if r.exact_sha.startswith("dirty:")]
        if dirty:
            self._goto(ReleaseState.BLOCKED)
            return ReleaseRunResult(
                self.state, exact_subject, None, None, None, None,
                reason=f"BLOCKED:DIRTY_WORKTREE:{','.join(dirty)}",
            )
        self._goto(ReleaseState.PREFLIGHTED)

        # --- EPISODE_1_RUNNING / EPISODE_1_VERIFIED
        self._goto(ReleaseState.EPISODE_1_RUNNING)
        routes = KnownRouteRegistry()
        artifacts = ArtifactRegistry()
        runner1 = Episode1Runner(
            state_dir=state_dir, journal_path=journal_path, receipt_store_dir=receipt_store_dir,
            known_route_registry=routes, artifact_registry=artifacts,
        )
        ep1 = runner1.run(
            semantic_class_id=semantic_class_id, query=episode1_query, discover=episode1_discover,
            equivalence_predicate=equivalence_predicate, equivalence_predicate_id=equivalence_predicate_id,
            probe_input=probe_input, action_iri=action_iri, target_resource=episode1_target_resource,
            exact_subject_digest=exact_subject.composition_digest,
        )
        if ep1.episode.classification != "KNOWN" or ep1.episode.standing != "EXECUTED":
            self._goto(ReleaseState.NONCONFORMANT)
            return ReleaseRunResult(
                self.state, exact_subject, ep1, None, None, None,
                reason=f"episode 1 did not reach KNOWN/EXECUTED (classification={ep1.episode.classification!r}, standing={ep1.episode.standing!r})",
            )
        self._goto(ReleaseState.EPISODE_1_VERIFIED)

        # --- EXPERIENCE_ADMITTED
        if ep1.machine_experience.state.value != "ACTIVE":
            self._goto(ReleaseState.NONCONFORMANT)
            return ReleaseRunResult(
                self.state, exact_subject, ep1, None, None, None,
                reason=f"MachineExperience did not reach ACTIVE (state={ep1.machine_experience.state.value!r})",
            )
        self._goto(ReleaseState.EXPERIENCE_ADMITTED)

        # --- EPISODE_2_RUNNING / EPISODE_2_VERIFIED
        self._goto(ReleaseState.EPISODE_2_RUNNING)
        experience_store = {ep1.machine_experience.experience_id: ep1.machine_experience}
        runner2 = Episode2Runner(
            state_dir=state_dir, journal_path=journal_path, receipt_store_dir=receipt_store_dir,
            known_route_registry=routes, artifact_registry=artifacts, experience_store=experience_store,
        )
        ep2 = runner2.run(
            semantic_class_id=semantic_class_id, fresh_candidate=episode2_fresh_candidate,
            probe_input=probe_input, action_iri=action_iri, target_resource=episode2_target_resource,
        )
        if ep2.episode.classification != "KNOWN" or not ep2.episode.frontier_clean:
            self._goto(ReleaseState.NONCONFORMANT)
            return ReleaseRunResult(
                self.state, exact_subject, ep1, ep2, None, None,
                reason=f"episode 2 did not reach KNOWN+frontier_clean (classification={ep2.episode.classification!r}, frontier_clean={ep2.episode.frontier_clean})",
            )
        self._goto(ReleaseState.EPISODE_2_VERIFIED)

        # --- CHICAGO_RUNNING: replay (real ReplayEngine, zero actuation) + fresh
        # consumer (real, separate subprocess). Scoped honestly: this covers replay
        # + fresh-consumer only, not the full 12-gate Chicago court (see
        # docs/jira/v26.9.17/ for what remains unconsolidated).
        self._goto(ReleaseState.CHICAGO_RUNNING)
        receipt_records = self._load_receipt_records(receipt_store_dir)
        replay_report = ReplayEngine().verify_chain(receipt_records)
        if replay_report.standing != ReplayStanding.ALIVE:
            self._goto(ReleaseState.NONCONFORMANT)
            return ReleaseRunResult(
                self.state, exact_subject, ep1, ep2, replay_report, None,
                reason=f"replay standing {replay_report.standing.value} (verdict {replay_report.verdict.value})",
            )

        fresh_consumer_standing = self._run_fresh_consumer(state_dir, ep1.episode.episode_id, ep2.episode.episode_id)
        if fresh_consumer_standing.get("verdict") != "CONFORMANT_EVIDENCE_RECONSTRUCTED":
            self._goto(ReleaseState.NONCONFORMANT)
            return ReleaseRunResult(
                self.state, exact_subject, ep1, ep2, replay_report, fresh_consumer_standing,
                reason=f"fresh-consumer verdict {fresh_consumer_standing.get('verdict')!r}",
            )
        self._goto(ReleaseState.EVIDENCE_VALIDATED)

        # --- CROWNED
        self._goto(ReleaseState.CROWNED)
        return ReleaseRunResult(self.state, exact_subject, ep1, ep2, replay_report, fresh_consumer_standing, reason="CROWNED")

    @staticmethod
    def _load_receipt_records(receipt_store_dir: Path) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        if not receipt_store_dir.is_dir():
            return records
        for path in sorted(receipt_store_dir.glob("prep_*.json")) + sorted(receipt_store_dir.glob("final_*.json")):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return records

    @staticmethod
    def _run_fresh_consumer(state_dir: Path, episode1_id: str, episode2_id: str) -> dict[str, Any]:
        """Invokes the fresh-consumer verifier as a REAL, SEPARATE process (ARD §45) --
        never imported and called in-process, so producer in-memory state cannot leak."""
        result = subprocess.run(
            [sys.executable, "-m", "autofde_lab.sa2a.release.fresh_consumer", str(state_dir), episode1_id, episode2_id],
            capture_output=True, text=True,
        )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"verdict": f"UNKNOWN:SUBPROCESS_OUTPUT_UNPARSEABLE:{result.stderr[:200]}"}
