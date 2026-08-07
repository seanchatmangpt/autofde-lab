# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Boundary-defense and functional tests for ``ocel/powl_replay.py``.

Test (a) below is the load-bearing one: a real ``sys.modules`` check after
import, proving ``autofde_lab.ocel.powl_replay`` never transitively imports
``SpiffWorkflow`` or ``autofde_lab.ofmf`` -- the exact boundary this repo's
"projection is not execution" doctrine draws.
"""

from __future__ import annotations

import sys

FORBIDDEN_MODULE_KEYS = (
    "SpiffWorkflow",
    "autofde_lab.ofmf",
    "autofde_lab.ofmf.ofmf_keystone",
)


def test_powl_replay_never_imports_spiffworkflow_or_ofmf() -> None:
    """Mechanical boundary check: a real sys.modules inspection after import.

    Not a documentation promise -- if any transitive import chain inside
    ``ocel/powl_replay.py`` ever reaches ``SpiffWorkflow`` or
    ``autofde_lab.ofmf``, this test fails.
    """
    import autofde_lab.ocel.powl_replay  # noqa: F401

    present = [key for key in FORBIDDEN_MODULE_KEYS if key in sys.modules]
    assert present == [], (
        f"ocel.powl_replay transitively imported forbidden module(s): {present} "
        f"-- this crosses the projection/actuation boundary"
    )
    # Also guard against any *submodule* of the forbidden packages sneaking in
    # under a different key (e.g. "autofde_lab.ofmf.something_else").
    leaked = [
        k
        for k in sys.modules
        if k.startswith("autofde_lab.ofmf") or k.startswith("SpiffWorkflow")
    ]
    assert leaked == [], f"ocel.powl_replay leaked forbidden submodule(s): {leaked}"


def test_replay_structural_fires_produces_ordered_ocel_trace() -> None:
    """A real small POWL plan, replayed through the existing executor only,
    produces a real validated OCEL log with one event per structural fire,
    in the correct (fired) order."""
    from autofde_lab.ocel.powl_replay import (
        plan_lines_to_powl_node,
        replay_structural_fires,
    )

    # A real, small blocks-world-style flat plan (VAL-format action strings,
    # matching decision_result_to_plan_lines's own output shape).
    plan_lines = [
        "(unstack a b)",
        "(put-down a)",
        "(pick-up b)",
        "(stack b a)",
    ]
    model = plan_lines_to_powl_node(plan_lines)

    log = replay_structural_fires(model, session_id="test-session-powl-replay")

    # The log validates cleanly (OCPQ Definition 2 structural laws).
    validated = log.validate()

    fire_events = [
        e for e in validated.events if e.activity == "powl_structural_fire"
    ]
    assert len(fire_events) == len(plan_lines), (
        f"expected {len(plan_lines)} structural fires, got {len(fire_events)}"
    )

    # Recover recorded order via timestamp_ns (mcp_session assigns increasing
    # real timestamps at record time) and via the steps_taken attribute,
    # which is assigned monotonically in fire order.
    ordered = sorted(fire_events, key=lambda e: e.timestamp_ns)

    def _attr(event, key):
        for a in event.attributes:
            if a.key == key:
                return a.value.value
        return None

    steps_taken = [int(_attr(e, "steps_taken")) for e in ordered]
    assert steps_taken == list(range(1, len(plan_lines) + 1)), steps_taken

    # Each event's recorded "detail" attribute is one of the real plan lines,
    # and the sequence of details matches the plan's own total order (a
    # PartialOrder with a full precedence chain forces this).
    details = [_attr(e, "detail") for e in ordered]
    assert details == plan_lines
