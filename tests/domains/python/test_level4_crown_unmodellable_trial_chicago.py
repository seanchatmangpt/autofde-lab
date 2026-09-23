# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""A trial that cannot be modelled must be SCORED as failed, never raised.

Chicago-style throughout: a real `RealBlindEnvironment` against the real
gymact provider over a real subprocess bridge, a real `run_real_trial`, real
files on disk, and assertions on the real returned `TrialReport` state. No
test doubles.

NOTE (2026-09-01, G04 backlog item 6): the module docstring above used to
claim the refusal exercised here (`requires_authority=True` making every DO
binding refuse with `LIVE_AUTHORITY_REQUIRED`) was one the real provider
genuinely issued. That was true only pre-2026-08-08. Commit `5060ee61`
(`fix(crown): exercise the authority gate -- LIVE_AUTHORITY_REQUIRED starved
counter discovery`) intentionally changed `level4_gymact_bridge.py`'s
`_BRIDGE_SCRIPT` so the bridge always constructs
`GymAct(authority_resolver=AllowListAuthorityResolver({_AUTHORITY_REF}))` and
passes that same admitted `_AUTHORITY_REF` on every `ActuationIntent` --
deliberately, so the bridge EXERCISES the SELECT/CONSTRUCT-only boundary
(a real resolver, a real admitted ref) instead of leaving every actuation
refused by a bare fail-closed `GymAct()`. `cube_counter`'s own
`requires_authority` config flag is stored on the environment
(`CubeCounterEnvironment.requires_authority`) but was never wired to gate
`actuate()` -- it never has been -- so post-fix there is no longer any
config-level way to make the bridge's `increment` binding refuse with
`LIVE_AUTHORITY_REQUIRED`; the bridge's own admitted ref always satisfies the
resolver. See `test_provider_really_refuses_when_authority_is_required`
below for the retirement of the one test that pinned the pre-fix premise
directly. `test_unmodellable_trial_is_scored_not_raised` immediately below it
also assumes the same stale refusal and is left failing here as a separate,
not-yet-triaged finding -- out of scope for backlog item 6, which named only
the authority-refusal test.

The defect pinned: when probing never observes any action succeed,
`induce_discovered_domain` marks every action unknown, `project_to_recipe`
drops them all, and `Recipe.__post_init__` refuses the empty procedure by
raising. That refusal is correct, but letting it escape `run_real_trial`
removed the trial from the crown scoreboard entirely instead of scoring it
False -- 4 of 10 frozen seeds terminated this way and had to be classified
by hand, outside the conjunction. Absent evidence is not a passed factor,
and it is not an absent factor either: it is a failed one with a name.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autofde_lab.hub.domain.gym_procedure.crown_evidence import UnknownEvidence
from autofde_lab.hub.domain.gym_procedure.level4_crown import run_real_trial
from autofde_lab.hub.domain.gym_procedure.level4_crown_runner import _row_is_alive
from autofde_lab.hub.domain.gym_procedure.level4_gymact_bridge import (
    GYMACT_VENV_PYTHON,
    RealBlindEnvironment,
)

pytestmark = pytest.mark.skipif(
    not Path(GYMACT_VENV_PYTHON).exists(),
    reason=f"real gymact interpreter absent at {GYMACT_VENV_PYTHON}",
)


@pytest.mark.skip(
    reason=(
        "RETIRED 2026-09-01 (G04 backlog item 6): pinned pre-2026-08-08-fix "
        "behavior the current, intentionally-fixed bridge design can no "
        "longer produce. Before commit 5060ee61, a bare `GymAct()` (no "
        "authority_resolver) meant the fail-closed DenyAuthorityResolver "
        "refused every cube_counter actuation with LIVE_AUTHORITY_REQUIRED "
        "regardless of the `requires_authority` config value -- so this "
        "test's premise ('requires_authority=True refuses') happened to "
        "hold, but for the wrong reason (every actuation was refused, not "
        "just authority-required ones). The fix deliberately replaced that "
        "with `GymAct(authority_resolver=AllowListAuthorityResolver({"
        "_AUTHORITY_REF}))` plus a real admitted `authority_ref` on every "
        "ActuationIntent/MaterializationIntent, so the SELECT/CONSTRUCT-only "
        "bridge now always presents admitted authority. cube_counter's own "
        "`requires_authority` flag was never wired into `actuate()`'s "
        "refusal path (grep `src/gymact/gyms/cube_counter.py`: the flag is "
        "stored on `CubeCounterEnvironment.__init__` and read nowhere else), "
        "so there is no remaining config-level way to reproduce a "
        "LIVE_AUTHORITY_REQUIRED refusal from this provider through this "
        "bridge. Verified failing against current HEAD: "
        '`record["applicable"]` is True (increment succeeds, '
        "counter 0 -> 1), not False. Retired rather than reworded because "
        "the current design has no analogous authority-refusal case to "
        "assert instead for this provider/binding pair -- an authority "
        "refusal now depends on the ref itself being unadmitted, not on a "
        "provider's own config flag, so a faithful replacement test belongs "
        "against the AllowListAuthorityResolver directly, not this "
        "provider-level environment."
    )
)
def test_provider_really_refuses_when_authority_is_required(tmp_path: Path) -> None:
    """RETIRED -- see skip reason above. Kept in place (not deleted) so its
    name and history remain discoverable via git blame / grep rather than
    silently vanishing from the suite."""
    env = RealBlindEnvironment(
        "cube_counter", {"target": 3, "requires_authority": True}, tmp_path / "probe"
    )
    record = env.try_action("increment", commit=False)

    assert record["applicable"] is False
    assert record["standing"] == "REFUSED"
    assert record["reason"] == "LIVE_AUTHORITY_REQUIRED"
    # The real world did not move.
    assert record["observed_post"]["counter"] == 0


def test_unmodellable_trial_is_scored_not_raised(tmp_path: Path) -> None:
    report = run_real_trial(
        seed=424242,
        provider_key="cube_counter",
        config={"target": 3, "requires_authority": True},
        evidence_root=tmp_path / "ev",
        probe_budget=6,
    )

    assert report.outcome == "NO_APPLICABLE_ACTION_DISCOVERED"
    # The trial never reached actuation, so `standing` is a named
    # `UnknownEvidence` -- never a silently-defaulted `AliveEvidence`, and
    # never a boolean ground-truth field left to disagree with it.
    assert isinstance(report.standing, UnknownEvidence)
    assert report.standing.missing == "NO_APPLICABLE_ACTION_DISCOVERED"
    assert report.standing.episode_digest is None
    assert report.is_alive() is False
    assert report.verdict() == "UNKNOWN"
    assert report.replay_error == "NO_APPLICABLE_ACTION_DISCOVERED"
    assert "NO_APPLICABLE_ACTION_DISCOVERED" in report.replay_mismatches
    # The real provider's own refusal reason survives into the report.
    assert "LIVE_AUTHORITY_REQUIRED" in report.goal_predicate_description
    # Probing really happened against the real bridge.
    assert report.n_probes > 0
    assert Path(report.evidence_dir).is_dir()


def test_unmodellable_trial_scores_false_in_the_crown_conjunction(
    tmp_path: Path,
) -> None:
    report = run_real_trial(
        seed=424243,
        provider_key="cube_counter",
        config={"target": 3, "requires_authority": True},
        evidence_root=tmp_path / "ev",
        probe_budget=6,
    )
    # `crown_factor.conjunction_from_row` is now explicitly a legacy-row
    # compatibility shim, not the live construction path (see
    # `crown_evidence.py`'s module docstring) -- go through
    # `TrialReport.to_row()`, the real serialization this refactor
    # introduced, rather than reconstructing a legacy row shape from
    # `report.__dict__` by hand.
    row = report.to_row()

    assert _row_is_alive(row) is False


def test_authority_granted_path_still_reaches_a_real_model(tmp_path: Path) -> None:
    """The guard must not swallow trials that CAN be modelled: the same
    provider with authority granted still discovers a real applicable
    action, so the new early return is narrow rather than a blanket bail."""
    env = RealBlindEnvironment(
        "cube_counter", {"target": 3, "requires_authority": False}, tmp_path / "probe"
    )
    record = env.try_action("increment", commit=False)

    assert record["applicable"] is True
    assert record["standing"] == "ALIVE"
    assert record["observed_post"]["counter"] == 1
