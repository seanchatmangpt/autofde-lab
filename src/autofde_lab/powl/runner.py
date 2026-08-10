# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Integration runner: pipeline steps wired as `action_bindings` on a real
:class:`~autofde_lab.powl.algebra.PowlNode` tree, built partly from a real
POWL2 Turtle document via :mod:`autofde_lab.powl.turtle_bridge`.

Pipeline steps modelled: scan, phi-encode (:mod:`autofde_lab.fabric.phi`),
dispatch (:func:`autofde_lab.utils.match_solvers`), solve, case-library
retrieve/retain (:mod:`autofde_lab.case_library`), a DSPy-fallback stub, and
OCEL record. Each becomes one :class:`~autofde_lab.powl.algebra.Atom` leaf;
a caller binds real callables to their labels and drives the tree through
:func:`autofde_lab.ocel.powl_replay.replay_structural_fires`.

Why the case-library branch is NOT built via turtle_bridge
------------------------------------------------------------
Verified this session, directly from source:
``autofde_lab.fabric.powl``'s Turtle vocabulary (what
``project_plan_to_powl``/``parse_powl_turtle`` actually accept) has no
``powl2:ChoiceGraph`` construct at all -- it models only a flat total order
of ``powl2:ActivityLeaf`` steps. ``turtle_bridge.powl_model_to_node`` and
``turtle_bridge.powl_node_to_model`` both refuse
(``BridgeError: UNSUPPORTED_NODE_SHAPE``) anything that is not a bare
:class:`~autofde_lab.powl.algebra.Atom` or a flat
:class:`~autofde_lab.powl.algebra.PartialOrder` of ``Atom`` children (see
that module's own docstring and refusal text).

So this module uses turtle_bridge for exactly what it can honestly do --
convert the *linear* prefix (scan, phi-encode, dispatch, solve) from a real
parsed Turtle document into real ``Atom`` leaves -- and builds the
case-library hit/miss branch as a real
:class:`~autofde_lab.powl.algebra.ChoiceGraph` directly via ``algebra.py``,
grafted into the same top-level :class:`PartialOrder` alongside the
turtle-sourced atoms. Both are real, executor-consumable ``PowlNode``
objects; only their construction path differs, named here rather than
silently faked.

``ChoiceGraphEdge`` carries no label field (confirmed in ``algebra.py`` this
session -- it is a frozen ``(src, dst)`` pair, nothing else). The hit/miss
branches are therefore distinguished by labelling each branch's *entry Atom*
(``"case_hit"`` / ``"case_miss"``) rather than by adding a label to the edge.

No silent hang
---------------
Termination of a (possibly cyclic) choice graph is structural, never a
wall-clock timeout -- see ``executor.py``'s module docstring and
``bounds.py``'s three counters (``max_activity_fires``, ``max_node_visits``,
``max_marking_states``). :func:`classify_pipeline_stall` surfaces
``executor.classify_stall()``'s result directly rather than adding a new
timeout layer of its own.

Decision: the runner stays structural-only; it does not gain a direct
actuation path
---------------------------------------------------------------------------
Now that ``action_bindings`` is merged (``ocel/powl_replay.py``), this
runner is free to bind real callables to Atom labels for every read-only or
diagnostic pipeline step -- scan, phi-encode, dispatch, solve, case-library
retrieve -- because none of those steps mutate a live cluster; they compute
or look up, and their own modules already own whatever standing they carry.
What this runner deliberately does NOT do is bind a cluster-mutating
remediation action directly to an Atom and let structural replay invoke it
as a side effect of marking advancement. Any real actuation step must be
reached through a separate, explicitly authorized call the runner's own
``action_bindings`` dict never performs itself -- e.g. a caller-held,
independently admitted actuator such as a gymact-mediated
``SregymEnvironment.actuate()``, invoked outside and after this runner's
structural replay, never from inside an Atom's binding. This matches
``CLAUDE.md``'s standing law verbatim: "It computes candidate plans. It does
not actuate." Collapsing that seam here -- letting a POWL Atom's action
payload double as a real actuator -- would hand structural marking
advancement (a property of the *plan*) the authority that belongs only to a
brokered, independently authorized actuation call (a property of the
*world*), the same class of defect ``.claude/rules/absence-is-not-evidence.md``
and ``.claude/rules/no-dual-bookkeeping.md`` name for admission and evidence:
a convenient coupling standing in for a lawful one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from autofde_lab.fabric.powl import parse_powl_turtle, project_plan_to_powl
from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.mcp_instrumentation import OcelSessionRecorder
from autofde_lab.ocel.powl_replay import ActionBinding
from autofde_lab.powl.algebra import (
    Atom,
    ChoiceGraph,
    ChoiceGraphEdge,
    NodeId,
    OrderEdge,
    PartialOrder,
    PowlNode,
)
from autofde_lab.powl.bounds import DEFAULT_BOUND, ExecutionBound
from autofde_lab.powl.executor import (
    INITIAL_MARKING,
    Marking,
    NodePath,
    classify_stall,
    enabled,
    fire,
    is_final,
    node_at,
)

__all__ = [
    "PIPELINE_LINEAR_STEPS",
    "CASE_RETRIEVE_LABEL",
    "CASE_HIT_LABEL",
    "CASE_MISS_LABEL",
    "CASE_RETAIN_LABEL",
    "RECORD_LABEL",
    "BridgeUnavailable",
    "build_pipeline_turtle",
    "build_pipeline_powl_node",
    "PipelineStallResult",
    "classify_pipeline_stall",
    "run_pipeline",
]

#: The turtle-bridge-eligible linear prefix: scan the cluster, phi-encode the
#: anomaly into a real domain object, dispatch via `match_solvers`, solve.
#: Each becomes one real `powl2:ActivityLeaf` in a real Turtle document.
PIPELINE_LINEAR_STEPS: tuple[str, ...] = (
    "(scan cluster)",
    "(phi_encode anomaly)",
    "(dispatch_solve problem)",
    "(solve problem)",
)

CASE_RETRIEVE_LABEL = "cbr_retrieve"
CASE_HIT_LABEL = "case_hit"
CASE_MISS_LABEL = "case_miss"
CASE_RETAIN_LABEL = "cbr_retain"
RECORD_LABEL = "ocel_record"


class BridgeUnavailable(ValueError):
    """Raised when turtle_bridge did not produce the shape this runner needs."""


def build_pipeline_turtle(base_iri: str = "urn:autofde-lab:powl-runner") -> str:
    """Real POWL2 Turtle text for the linear scan/phi/dispatch/solve prefix."""
    return project_plan_to_powl(list(PIPELINE_LINEAR_STEPS), base_iri=base_iri)


def build_pipeline_powl_node(turtle_text: str | None = None) -> PowlNode:
    """The full pipeline as one real, executor-consumable `PowlNode` tree.

    The linear prefix is parsed from a real POWL2 Turtle document via
    `turtle_bridge.powl_model_to_node`. The case-library hit/miss branch is a
    real `ChoiceGraph`, built directly via `algebra.py` -- see this module's
    docstring for why turtle_bridge cannot be used for that part.
    """
    from autofde_lab.powl.turtle_bridge import powl_model_to_node

    text = turtle_text if turtle_text is not None else build_pipeline_turtle()
    model = parse_powl_turtle(text)
    linear = powl_model_to_node(model)
    if not isinstance(linear, PartialOrder) or not all(
        isinstance(c, Atom) for c in linear.children
    ):
        raise BridgeUnavailable(
            f"expected a flat PartialOrder of Atom leaves from turtle_bridge, "
            f"got {type(linear).__name__}"
        )
    linear_atoms: tuple[Atom, ...] = linear.children  # type: ignore[assignment]
    n_linear = len(linear_atoms)

    # Real ChoiceGraph, built directly (turtle_bridge has no vocabulary for
    # it): retrieve(0) -> case_hit(1) | case_miss(2) -> retain(3). Branches
    # are distinguished by the entry Atom's label, never by an edge label.
    choice_children: tuple[PowlNode, ...] = (
        Atom(label=CASE_RETRIEVE_LABEL),
        Atom(label=CASE_HIT_LABEL),
        Atom(label=CASE_MISS_LABEL),
        Atom(label=CASE_RETAIN_LABEL),
    )
    choice_edges = frozenset(
        {
            ChoiceGraphEdge(NodeId(0), NodeId(1)),
            ChoiceGraphEdge(NodeId(0), NodeId(2)),
            ChoiceGraphEdge(NodeId(1), NodeId(3)),
            ChoiceGraphEdge(NodeId(2), NodeId(3)),
        }
    )
    choice_graph = ChoiceGraph(children=choice_children, edges=choice_edges, start=0, end=3)

    record_atom = Atom(label=RECORD_LABEL)

    top_children: tuple[PowlNode, ...] = linear_atoms + (choice_graph, record_atom)
    choice_index = n_linear
    record_index = n_linear + 1

    # Remap the turtle-sourced order relation (already 0..n_linear-1) as-is,
    # then chain: last linear step -> choice graph -> record atom.
    order_edges: set[OrderEdge] = {OrderEdge(edge.src, edge.dst) for edge in linear.order}
    order_edges.add(OrderEdge(NodeId(n_linear - 1), NodeId(choice_index)))
    order_edges.add(OrderEdge(NodeId(choice_index), NodeId(record_index)))

    return PartialOrder(children=top_children, order=frozenset(order_edges))


@dataclass(frozen=True, slots=True)
class PipelineStallResult:
    """What `classify_pipeline_stall` surfaces -- never a new timeout layer."""

    final: bool
    stall: str | None  # an `executor.DeadlockKind` value, or None if final/live


def classify_pipeline_stall(
    model: PowlNode,
    marking: Marking,
    bound: ExecutionBound = DEFAULT_BOUND,
) -> PipelineStallResult:
    """Surface `executor.classify_stall()` directly -- no wall-clock timeout.

    Per `executor.py`/`bounds.py`: termination is structural (three counters
    only), never a timeout. This function adds no bound of its own; it is a
    thin, honest pass-through so a caller of this runner gets the same
    `BLOCKED:BOUND_EXHAUSTED` / `BLOCKED:DEADLOCK` classification the
    executor already computes, rather than a silent hang.
    """
    if is_final(model, marking):
        return PipelineStallResult(final=True, stall=None)
    if marking.fires >= bound.max_activity_fires or not enabled(model, marking, bound):
        # Delegate the actual verdict to executor.classify_stall itself --
        # this module never re-derives BOUND_EXHAUSTED vs. DEADLOCK on its
        # own, only forwards the executor's real classification.
        return PipelineStallResult(final=False, stall=str(classify_stall(model, marking, bound)))
    return PipelineStallResult(final=False, stall=None)  # more work enabled, not stalled


def run_pipeline(
    model: PowlNode,
    *,
    session_id: str | None = None,
    action_bindings: dict[str, ActionBinding] | None = None,
    bound: ExecutionBound = DEFAULT_BOUND,
) -> tuple[OcelLog, PipelineStallResult]:
    """Drive `model` to completion or to a classified stall, recording one
    real `"powl_structural_fire"` OCEL event per fire -- the same event shape
    `ocel.powl_replay.replay_structural_fires` uses -- while retaining the
    `Marking` so a caller gets `classify_pipeline_stall`'s real verdict
    instead of a silently-incomplete log.

    This module keeps its own loop (rather than delegating entirely to
    `replay_structural_fires`, which does not return its final `Marking`)
    for exactly that reason: surfacing `classify_stall()` requires the
    marking `replay_structural_fires` does not expose.
    """
    session_id = session_id or "powl-runner-pipeline"
    recorder = OcelSessionRecorder(session_id, server_name="powl-runner")

    marking: Marking = INITIAL_MARKING
    step = 0
    while not is_final(model, marking):
        if marking.fires >= bound.max_activity_fires:
            # `fire()` itself raises BOUND_EXHAUSTED past this point; checked
            # here instead so a fire-budget stall stops the loop the same
            # honest, non-raising way a visit-cap or deadlock stall does --
            # `classify_pipeline_stall` below reports which one it was.
            break
        live = enabled(model, marking, bound)
        if not live:
            break
        chosen: NodePath = sorted(live)[0]
        node = node_at(model, chosen)
        label = node.label if isinstance(node, Atom) else f"path:{chosen}"

        marking = fire(model, marking, chosen, bound=bound)
        step += 1

        node_object_id = f"{session_id}-node-{'.'.join(map(str, chosen))}"
        outcome: dict[str, Any] = {"standing": "FIRED", "detail": label, "steps_taken": step}

        binding = action_bindings.get(label) if action_bindings else None
        if binding is not None and isinstance(node, Atom):
            atom_attrs = {"label": node.label, "action": node.action, "bindings": dict(node.bindings)}
            try:
                outcome["action_result"] = binding(atom_attrs)
            except Exception as exc:  # noqa: BLE001 -- recorded honestly, then re-raised
                recorder.record(
                    activity="powl_action_binding_error",
                    objects=[(node_object_id, "PowlNode")],
                    outcome={
                        "standing": "ERROR",
                        "detail": label,
                        "steps_taken": step,
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
                raise

        recorder.record(
            activity="powl_structural_fire",
            objects=[(node_object_id, "PowlNode")],
            outcome=outcome,
        )

    return recorder.close(), classify_pipeline_stall(model, marking, bound)
