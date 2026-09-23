# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Identity-mutation falsification tests for the Level 4 typed evidence chain.

Level 4 crown mission, item 2: for each identity edge that is genuinely
represented in the real evidence graph, swap one identity to a
wrong-but-plausible value and assert that the fresh standing/validation
constructor refuses -- never silently accepts a correct-order-wrong-identity
graph.

Scope, stated precisely rather than assumed:

The mission names eight candidate edges. Two disconnected real constructors
exist in this codebase, not one:

* ``crown_evidence.standing_from_episode`` -> ``Standing``
  (``Level4AliveEvidence`` / ``ConformantButGoalUnmetEvidence`` / ...).
  Its inputs are ``log``/``operations``/``receipts``/``replay``/
  ``postcondition_ref`` only. It never reads ``level4_ocel.py``'s
  object-object graph at all.
* ``level4_ocel.build_level4_ocel`` -> a real ``OcelLog`` with a real
  object-object edge table, validated by ``OcelLog.validate()`` (dangling
  references + Gianola-locality) -- this IS the real, load-bearing identity
  check available for the object-graph edges the mission names.

Of the mission's eight edges, exactly four are real, typed, non-inferred
object-object links in ``level4_ocel.py``'s graph today:

* ``Commitment -> Actuation``   (qualifier ``actuates_commitment``)
* ``Authority -> Actuation``    (qualifier ``authorized_by``)
* ``Actuation -> PostconditionObservation`` (qualifier ``observes_actuation``,
  built in the ``PostconditionObservation -> Actuation`` direction)
* ``Receipt -> parent Receipt`` (qualifier ``caused_by``)

This module writes one identity-mutation test per real edge above, against
``OcelLog.validate(strict_qualifiers=True)`` as the fresh constructor that
refuses. Every other mutation is a real, executed ``left/right``
`OcelLog.validate()` call over the real trial's real graph -- no mock, stub,
patch, or monkeypatch.

The remaining four named edges are NOT written as tests here, per the task's
own instruction to report rather than fabricate:

* ``PlanCandidate -> Commitment`` -- GAP. No object-object link exists
  between a ``PlanCandidate`` and ``POWLCommitment`` object anywhere in
  ``build_level4_ocel``. ``PlanCandidate`` only links to its
  ``PlannerAttempt`` (``proposed_by``); ``POWLCommitment`` only links to
  ``Task``/``DiscoveredDomain``. The committed candidate is never identified
  by object-object edge.
* ``PostconditionObservation -> IndependentVerifier`` -- GAP.
  ``IndependentVerifier`` is not a declared object type in
  ``LEVEL4_OBJECT_TYPES`` and no such object is ever constructed.
* ``Replay -> source Receipt`` -- GAP. The real ``Replay`` object links only
  to ``Task`` (qualifier ``replay_of_task``); it carries a ``head_digest``
  attribute but no object-object edge to the receipt(s) that digest was
  computed from.
* ``Goal -> PostconditionObservation`` -- GAP. ``Goal`` is not a declared
  object type anywhere. The independent goal-consequence check lives
  entirely in ``crown_evidence.py`` as a flat ``verify_goal_consequence``
  OCEL *event* (see that module's ``GOAL_CONSEQUENCE_EVENT_TYPE``), carrying
  only an ``episode`` relationship -- there is no ``PostconditionObservation``
  object, and no ``Task -> Goal`` object edge, in either graph.

A fifth, load-bearing finding beyond the four gaps above:
``crown_evidence.standing_from_episode`` reads the ``verify_goal_consequence``
event by *type* alone (``_goal_consequence_from_log``) and never
cross-checks its ``relationships[0].objectId`` against the real episode id
it was actually computed for. `test_goal_event_pointing_at_a_different_
episode_is_silently_accepted_by_standing_from_episode` below is a real,
executed demonstration of that gap (a real ``UNKNOWN``/refusal did NOT
happen) -- not a fabricated pass.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import replace

import pytest

from autofde_lab.hub.domain.gym_procedure.level4_crown import run_real_trial
from autofde_lab.hub.domain.gym_procedure.level4_ocel import (
    build_level4_ocel,
    link_commitment_ttl,
)
from autofde_lab.ocel.model import ObjectObjectLink
from autofde_lab.ocel.refusals import OcelError


@pytest.fixture(scope="module")
def executed_trial(tmp_path_factory) -> pathlib.Path:
    root = tmp_path_factory.mktemp("level4_identity_mutation")
    report = run_real_trial(
        69813132, "resource_flow", {"target": 3, "capacity": 4, "mine_rate": 1}, root
    )
    if report.outcome != "EXECUTED":
        pytest.skip(
            f"UNSUPPORTED: trial did not reach actuation (outcome={report.outcome})"
        )
    return pathlib.Path(report.evidence_dir)


@pytest.fixture(scope="module")
def linked_trial(executed_trial: pathlib.Path) -> pathlib.Path:
    built = build_level4_ocel(executed_trial)
    assert built.episode_id is not None and built.environment_id is not None
    link_commitment_ttl(
        executed_trial / "actuation" / "commitment.ttl",
        episode_id=built.episode_id,
        environment_id=built.environment_id,
    )
    return executed_trial


def _mutate_one_link(log, *, qualifier: str, new_target: str):
    """Return a copy of `log` with exactly one `qualifier`-typed
    object-object link's target swapped to `new_target`. Fails loudly if the
    qualifier is not present at all -- a mutation test with nothing to
    mutate would silently pass for the wrong reason."""
    links = list(log.object_object_links)
    for i, link in enumerate(links):
        if link.qualifier == qualifier:
            links[i] = ObjectObjectLink(link.source_id, new_target, link.qualifier)
            return replace(log, object_object_links=tuple(links))
    raise AssertionError(
        f"PREMISE_GONE: no real {qualifier!r} edge in this trial's graph"
    )


@pytest.mark.parametrize(
    "qualifier",
    ["actuates_commitment", "authorized_by", "observes_actuation", "caused_by"],
)
def test_wrong_but_plausible_identity_swap_is_refused(
    linked_trial, qualifier: str
) -> None:
    """Real edge, real mutation, real refusal.

    Each of these four qualifiers is a genuinely constructed, typed
    object-object identity in `build_level4_ocel`'s real graph (see module
    docstring for why the other four mission-named edges are excluded).
    Swapping the target to a same-scheme, plausible-looking but
    never-declared urn -- not a nonsense string -- and asserting the real
    `OcelLog.validate()` refuses via `OcelError`, exactly the machinery
    `test_a_dangling_reference_is_still_refused` already exercises for one
    case; this parametrizes it over every real edge named by the mission.
    """
    log = build_level4_ocel(linked_trial).log
    assert any(link.qualifier == qualifier for link in log.object_object_links), (
        f"PREMISE_GONE: {qualifier!r} absent from this trial's real graph"
    )

    plausible_but_wrong = f"urn:level4:{qualifier}:wrong-but-plausible-0000"
    mutated = _mutate_one_link(log, qualifier=qualifier, new_target=plausible_but_wrong)

    with pytest.raises(OcelError):
        mutated.validate(strict_qualifiers=True)


def test_goal_event_pointing_at_a_different_episode_is_silently_accepted_by_standing_from_episode(
    linked_trial,
) -> None:
    """Named gap, demonstrated with real objects -- not fabricated as a pass.

    `crown_evidence._goal_consequence_from_log` scans for a
    `verify_goal_consequence` event purely by event *type*; it never reads
    that event's own `relationships[0].objectId` and never compares it
    against the episode id `standing_from_episode`'s other arguments
    (`receipts`, `replay`) were actually computed for. A goal event that is
    real in shape but carries a wrong-but-plausible episode identity is
    therefore accepted exactly as if it belonged to this episode -- this
    test executes that real path and asserts the (undesirable, but real)
    current behavior, so the gap is evidenced rather than merely claimed.
    """
    import asyncio
    import copy
    import hashlib
    import uuid

    from gymact.gyms.switchboard import SwitchboardProvider
    from gymact.models import ActuationIntent
    from gymact.ocel import receipts_to_ocel
    from gymact.replay import ReplayExpectation, ReplayMode, replay_ledger
    from gymact.sqlite_ledger import SQLiteReceiptLedger

    from autofde_lab.hub.domain.gym_procedure.crown_evidence import (
        GOAL_CONSEQUENCE_EVENT_TYPE,
        Level4AliveEvidence,
        standing_from_episode,
    )
    from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent

    def _digest(obj: object) -> str:
        return hashlib.sha256(
            json.dumps(obj, sort_keys=True, default=str).encode()
        ).hexdigest()

    async def _run() -> dict:
        tmp = linked_trial / "actuation" / "identity_mutation_probe"
        tmp.mkdir(exist_ok=True)
        ledger = SQLiteReceiptLedger(str(tmp / "receipts.sqlite3"))
        auth = "urn:autofde-lab:test-identity-mutation"
        gym = GymAct(
            receipt_ledger=ledger, authority_resolver=AllowListAuthorityResolver({auth})
        )
        gym.register_provider(SwitchboardProvider())
        m = await gym.materialize(
            MaterializationIntent(provider="switchboard", config={})
        )
        episode_id = m.episode.episode_id
        cap = gym.capabilities(episode_id)[0]
        await gym.act(
            ActuationIntent(
                episode_id=episode_id, capability=cap.iri, authority_ref=auth
            )
        )
        await gym.teardown(episode_id)
        receipts = gym.episode_receipts(episode_id)
        log = receipts_to_ocel(receipts)
        replay = replay_ledger(
            ledger,
            mode=ReplayMode.EVIDENCE_REPLAY,
            expected=ReplayExpectation(subject_ref=m.episode.environment_id),
        )
        return {
            "episode_id": episode_id,
            "log": log,
            "operations": [r.operation for r in receipts],
            "receipts": receipts,
            "replay": replay,
        }

    real = asyncio.run(_run())

    wrong_episode_id = "urn:gymact:episode:wrong-but-plausible-not-this-episode"
    assert wrong_episode_id != real["episode_id"]

    mutated_log = copy.deepcopy(real["log"])
    mutated_log["events"].append(
        {
            "id": f"goal-verification:{uuid.uuid4().hex}",
            "type": GOAL_CONSEQUENCE_EVENT_TYPE,
            "time": "2026-08-08T00:00:00+00:00",
            "attributes": [
                {"name": "passed", "value": "True"},
                {"name": "verification_id", "value": uuid.uuid4().hex},
                {"name": "state_digest", "value": _digest({"solved": True})},
                {"name": "expected_digest", "value": _digest({"solved": True})},
                {"name": "observed_digest", "value": _digest({"solved": True})},
            ],
            # The identity mutation: this relationship names an episode that
            # is real-shaped but is NOT the episode `real["receipts"]`/
            # `real["replay"]` were actually computed for.
            "relationships": [{"objectId": wrong_episode_id, "qualifier": "episode"}],
        }
    )
    if not any(
        et["name"] == GOAL_CONSEQUENCE_EVENT_TYPE for et in mutated_log["eventTypes"]
    ):
        mutated_log["eventTypes"].append(
            {
                "name": GOAL_CONSEQUENCE_EVENT_TYPE,
                "attributes": [{"name": "passed", "type": "string"}],
            }
        )

    standing = standing_from_episode(
        mutated_log,
        real["operations"],
        real["receipts"],
        replay=real["replay"],
        postcondition_ref="urn:test:postcondition:identity-mutation-probe",
    )

    # This is the gap, executed and asserted on real returned state: a
    # wrong-episode-identity goal event is NOT refused. If this assertion
    # ever starts failing because `standing_from_episode` gained a real
    # cross-check, that is the gap being closed -- update this test to
    # assert the (now real) refusal instead of loosening it.
    assert isinstance(standing, Level4AliveEvidence), (
        "GAP_CLOSED_OR_TEST_STALE: standing_from_episode now refuses a "
        "wrong-episode-identity goal event; this test's premise (that it "
        "does not) needs updating to assert the new refusal, not to be "
        "deleted or loosened"
    )
