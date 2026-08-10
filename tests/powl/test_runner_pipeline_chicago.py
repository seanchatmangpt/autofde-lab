# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style test for `autofde_lab.powl.runner`.

Real collaborators throughout, zero mocks:

- A real POWL2 Turtle document (`runner.build_pipeline_turtle`), parsed by
  the real `fabric.powl.parse_powl_turtle` and converted by the real
  `powl.turtle_bridge.powl_model_to_node` -- not a hand-built `PowlNode`
  standing in for what turtle_bridge would produce.
- A real `ChoiceGraph` (case-library hit/miss), built directly via
  `powl.algebra` -- turtle_bridge cannot represent it (see `runner.py`'s
  module docstring for the verified, named reason).
- Real Python callables bound as `action_bindings`, invoked by the real
  `ocel.powl_replay.replay_structural_fires` driver.
- A real, validated `OcelLog` (`OcelSessionRecorder.close()` runs the same
  structural validation any other session's log goes through).

No `unittest.mock` / `Mock` / `patch` / `monkeypatch` anywhere in this file.
"""

from __future__ import annotations

from autofde_lab.ocel.powl_replay import replay_structural_fires
from autofde_lab.powl.algebra import Atom, PartialOrder
from autofde_lab.powl.bounds import ExecutionBound
from autofde_lab.powl.executor import INITIAL_MARKING, enabled, fire
from autofde_lab.powl.runner import (
    ActuationBindingRefused,
    CASE_HIT_LABEL,
    CASE_RETRIEVE_LABEL,
    RECORD_LABEL,
    build_pipeline_powl_node,
    build_pipeline_turtle,
    classify_pipeline_stall,
    run_pipeline,
)
from autofde_lab.powl.turtle_bridge import powl_model_to_node
from autofde_lab.fabric.powl import parse_powl_turtle


def test_turtle_bridge_produces_real_linear_prefix_from_real_turtle():
    """turtle_bridge really parses a real Turtle document into real Atoms."""
    text = build_pipeline_turtle()
    assert "powl2:ActivityLeaf" in text  # a real Turtle document, not a stub

    model = parse_powl_turtle(text)
    node = powl_model_to_node(model)

    assert isinstance(node, PartialOrder)
    assert [a.label for a in node.children] == [
        "scan",
        "phi_encode",
        "dispatch_solve",
        "solve",
    ]


def test_pipeline_node_grafts_real_choicegraph_onto_turtle_sourced_atoms():
    """The case-library branch is a real ChoiceGraph, distinguished by its
    entry Atom's label (case_hit / case_miss), not by an edge label --
    ChoiceGraphEdge carries no label field."""
    node = build_pipeline_powl_node()
    assert isinstance(node, PartialOrder)
    labels = [getattr(c, "label", type(c).__name__) for c in node.children]
    assert labels == [
        "scan",
        "phi_encode",
        "dispatch_solve",
        "solve",
        "ChoiceGraph",
        RECORD_LABEL,
    ]
    choice = node.children[4]
    entry_labels = {c.label for c in choice.children if isinstance(c, Atom)}
    assert entry_labels == {CASE_RETRIEVE_LABEL, CASE_HIT_LABEL, "case_miss", "cbr_retain"}


def test_replay_structural_fires_invokes_real_action_bindings_one_event_per_fire():
    """Real bindings, invoked by the real `replay_structural_fires` driver;
    one real OCEL event per real structural fire."""
    node = build_pipeline_powl_node()

    invocations: list[tuple[str, dict]] = []

    def scan(attrs: dict) -> dict:
        invocations.append(("scan", attrs))
        return {"anomalies_found": 1}

    def cbr_retrieve(attrs: dict) -> None:
        invocations.append(("cbr_retrieve", attrs))
        return None  # no matching prior case -- a real "miss" outcome

    def case_hit(attrs: dict) -> str:
        invocations.append(("case_hit", attrs))
        return "reused_prior_mitigation"

    log = replay_structural_fires(
        node,
        session_id="test-runner-pipeline",
        action_bindings={
            "scan": scan,
            "cbr_retrieve": cbr_retrieve,
            "case_hit": case_hit,
        },
    )

    # 6 leaves total: scan, phi_encode, dispatch_solve, solve, then the
    # choice graph's real traversal (retrieve -> case_hit -> retain, per
    # replay_structural_fires's own lexicographically-smallest-path policy),
    # then the final record atom = 8 real structural fires.
    assert len(log.events) == 8
    assert [e.activity for e in log.events].count("powl_structural_fire") == 8

    # Exactly the 3 bound labels were really invoked, once each.
    assert [label for label, _ in invocations] == ["scan", "cbr_retrieve", "case_hit"]
    assert invocations[0][1]["label"] == "scan"
    assert invocations[2][1]["label"] == "case_hit"

    # Each bound invocation's real return value is recorded on its own event.
    scan_event = log.events[0]
    action_result_attrs = {a.key: a.value.value for a in scan_event.attributes}
    assert action_result_attrs["action_result"] == "{'anomalies_found': 1}"


def test_run_pipeline_surfaces_classify_stall_on_bound_exhaustion_no_hang():
    """`run_pipeline` surfaces `executor.classify_stall()`'s real verdict --
    a structural counter, never a wall-clock timeout -- when the executor's
    own bound stops the traversal short of `is_final`."""
    node = build_pipeline_powl_node()
    tiny_bound = ExecutionBound(max_activity_fires=2, max_node_visits=4096, max_marking_states=8192)

    log, result = run_pipeline(node, session_id="test-bound-exhausted", bound=tiny_bound)

    assert result.final is False
    assert result.stall == "BLOCKED:BOUND_EXHAUSTED"
    # Only 2 real fires were attempted before the structural bound stopped it.
    assert len(log.events) == 2


def test_run_pipeline_refuses_action_binding_for_non_pipeline_label():
    """`run_pipeline`'s docstring states the runner "stays structural-only"
    and never lets a cluster-mutating actuator fire as a side effect of Atom
    marking advancement. This test proves that decision is a real runtime
    guard, not merely prose: a caller trying to smuggle a mutating actuator
    in under a label this pipeline never has (i.e. not one of the known
    read-only/diagnostic Atom labels) is refused before any Atom fires --
    the real sentinel list below staying empty is direct evidence nothing
    was ever invoked, not an inference from "no exception propagated"."""
    node = build_pipeline_powl_node()

    invocations: list[str] = []

    def _would_mutate_cluster(atom_attrs: dict) -> None:  # pragma: no cover - must never run
        invocations.append(atom_attrs["label"])

    try:
        run_pipeline(
            node,
            session_id="test-refused-actuation-binding",
            action_bindings={"delete_pod": _would_mutate_cluster},
        )
        raised = False
    except ActuationBindingRefused:
        raised = True

    assert raised, "run_pipeline must refuse an action_bindings key outside the known pipeline labels"
    assert invocations == [], (
        f"the refused binding must never be invoked -- got invocations={invocations!r}"
    )


def test_classify_pipeline_stall_reports_final_on_completed_marking():
    """A completed marking classifies as final, not as any stall kind."""
    node = build_pipeline_powl_node()
    marking = INITIAL_MARKING
    while not (result := classify_pipeline_stall(node, marking)).final:
        live = enabled(node, marking)
        assert live, "structurally deadlocked before is_final -- test setup bug"
        marking = fire(node, marking, sorted(live)[0])
    assert result == classify_pipeline_stall(node, marking)
    assert result.final is True
    assert result.stall is None
