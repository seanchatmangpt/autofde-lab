# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Structural POWL replay, projected into a real OCEL 2.0 trace.

Drives a :class:`~autofde_lab.powl.algebra.PowlNode` tree through
:mod:`autofde_lab.powl.executor`'s **existing** ``enabled()``/``fire()``
functions -- this module reimplements no traversal logic of its own -- and
records each real structural fire as a real OCEL event via
:func:`autofde_lab.ocel.mcp_session.append_tool_call_event`.

Boundary this module must never cross
--------------------------------------
``powl/executor.py`` is a *reference traversal*: it fires nothing in the
world, and an :class:`~autofde_lab.powl.algebra.Atom`'s ``action`` payload is
"never invoked, never brokered, never admitted" (its own module docstring,
quoted exactly). This module inherits that guarantee by construction --
it calls only ``enabled()``/``fire()`` -- and additionally never imports,
directly or transitively:

- ``autofde_lab.ofmf`` (any submodule, including ``ofmf_keystone``)
- ``SpiffExecutor`` / ``SpiffWorkflowAdapter``
- the ``SpiffWorkflow`` package itself

``tests/ocel/test_powl_replay_boundary.py`` checks this mechanically, via a
``sys.modules`` inspection after import -- not as a documentation promise.

Representation choice
----------------------
This module drives ``powl/algebra.py``'s :class:`PowlNode` tree directly
(the shape ``powl/executor.py`` already consumes), not ``fabric/powl.py``'s
Turtle-projector :class:`PowlModel`. As of this session's own finding there
is no converter between the two POWL representations, and writing one is
real, unscoped semantic work (resolving ``PowlModel``'s node-id graph back
into ``algebra.py``'s index-addressed children/edges arena convention).
Building this replay directly against a hand-constructed (or
``project_plan_to_powl``-inspired) ``PowlNode`` tree is the narrower, honest
scope for this item -- a caller that already has a parsed ``PowlModel`` can
still reach this module by building the equivalent ``PowlNode`` tree, which
is what :func:`plan_lines_to_powl_node` below does for the common case (a
flat, real plan action sequence).
"""

from __future__ import annotations

import uuid
from typing import Sequence

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.mcp_instrumentation import OcelSessionRecorder
from autofde_lab.powl.algebra import Atom, PartialOrder, PowlNode
from autofde_lab.powl.executor import (
    INITIAL_MARKING,
    Marking,
    NodePath,
    enabled,
    fire,
    is_final,
)

__all__ = ["plan_lines_to_powl_node", "replay_structural_fires"]


def plan_lines_to_powl_node(plan_lines: Sequence[str]) -> PowlNode:
    """A real, totally-ordered :class:`PowlNode` tree for a real flat plan.

    ``plan_lines`` is e.g. the output of ``fabric/powl.py``'s
    ``decision_result_to_plan_lines`` (VAL-style action strings such as
    ``"(unstack a b)"``), or any other real, ordered sequence of step labels.
    Each line becomes one :class:`Atom` leaf; a :class:`PartialOrder` with a
    full chain of :class:`~autofde_lab.powl.algebra.OrderEdge`\\ s enforces
    strict sequencing, matching the flat plan's own total order.

    Requires at least two lines: :class:`PartialOrder` itself requires
    ``n >= 2`` children (its own construction-time invariant), so a
    single-step plan cannot be represented without a composite wrapper this
    function declines to invent silently.
    """
    if len(plan_lines) < 2:
        raise ValueError(
            f"plan_lines_to_powl_node requires >= 2 steps, got {len(plan_lines)}"
        )
    from autofde_lab.powl.algebra import OrderEdge

    children = tuple(Atom(label=line) for line in plan_lines)
    order = frozenset(
        OrderEdge(i, i + 1) for i in range(len(children) - 1)  # type: ignore[arg-type]
    )
    return PartialOrder(children=children, order=order)


def replay_structural_fires(
    model: PowlNode,
    *,
    session_id: str | None = None,
) -> OcelLog:
    """Replay ``model`` to completion via ``powl/executor.py``'s
    ``enabled()``/``fire()`` only, recording one real ``"powl_structural_fire"``
    OCEL event per structural fire.

    At each step this function picks the lexicographically-smallest enabled
    path -- a caller-side policy choice made *here*, in the replay driver,
    never inside the executor itself (``enabled()``'s own law: it returns a
    set, never an ordered choice). Returns the validated
    :class:`~autofde_lab.ocel.log.OcelLog`.
    """
    session_id = session_id or f"powl-replay-{uuid.uuid4().hex[:8]}"
    recorder = OcelSessionRecorder(session_id, server_name="powl-structural-replay")

    marking: Marking = INITIAL_MARKING
    step = 0
    while not is_final(model, marking):
        live = enabled(model, marking)
        if not live:
            # Structurally stalled with nothing enabled and not final --
            # nothing left this replay can lawfully do; stop rather than loop.
            break
        chosen: NodePath = sorted(live)[0]
        node = _node_at(model, chosen)
        label = node.label if isinstance(node, Atom) else f"path:{chosen}"

        marking = fire(model, marking, chosen)
        step += 1

        recorder.record(
            activity="powl_structural_fire",
            objects=[(f"{session_id}-node-{'.'.join(map(str, chosen))}", "PowlNode")],
            outcome={
                "standing": "FIRED",
                "detail": label,
                "steps_taken": step,
            },
        )

    return recorder.close()


def _node_at(model: PowlNode, path: NodePath) -> PowlNode:
    from autofde_lab.powl.executor import node_at

    return node_at(model, path)
