# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Counterfactual Process Validation with PM4Py over AutoFDE OCEL 2.0 and traces.

Provides mathematically rigorous, token-replay and alignment-backed
conformance checking to evaluate:
1. Lawful execution traces against inductive Petri net models.
2. Counterfactual deviations, mutations, and policy violations
   (early actuation, unadmitted step injection, skipped teardown,
   and out-of-order object lifecycles).

Adheres to AGENTS.md:
- ALIVE: Observed token replay / alignment execution with real Petri nets.
- UNSUPPORTED: Gracefully indicated when PM4Py is not installed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.object_centric_conformance import project_object_trace

__all__ = [
    "PM4PY_AVAILABLE",
    "AlignmentStep",
    "CounterfactualValidationResult",
    "LawfulProcessModel",
    "discover_lawful_model",
    "evaluate_counterfactual_trace",
    "ocel_to_pm4py_log",
    "traces_to_pm4py_log",
]

try:
    import pm4py
    from pm4py.objects.log.obj import Event, EventLog, Trace
    from pm4py.objects.petri_net.obj import Marking, PetriNet

    PM4PY_AVAILABLE = True
except ImportError:  # pragma: no cover
    pm4py = None
    EventLog = None
    Trace = None
    Event = None
    PetriNet = None
    Marking = None
    PM4PY_AVAILABLE = False


@dataclass(frozen=True)
class AlignmentStep:
    """A single transition step in an optimal alignment."""

    log_move: str | None
    model_move: str | None
    is_sync: bool

    @property
    def is_deviation(self) -> bool:
        """True if the step represents an unaligned move (log-only or model-only)."""
        return not self.is_sync


@dataclass(frozen=True)
class LawfulProcessModel:
    """A discovered Petri net model representing admitted lawful behavior."""

    net: Any  # pm4py.objects.petri_net.obj.PetriNet
    initial_marking: Any  # pm4py.objects.petri_net.obj.Marking
    final_marking: Any  # pm4py.objects.petri_net.obj.Marking
    discovered_activities: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CounterfactualValidationResult:
    """Result of evaluating a candidate or counterfactual trace against a lawful model."""

    is_conforming: bool
    trace_fitness: float
    alignment_cost: int
    missing_tokens: int
    remaining_tokens: int
    produced_tokens: int
    consumed_tokens: int
    alignment_steps: tuple[AlignmentStep, ...] = field(default_factory=tuple)
    deviations: tuple[AlignmentStep, ...] = field(default_factory=tuple)
    evidence_status: str = "ALIVE"

    @property
    def has_deviations(self) -> bool:
        return len(self.deviations) > 0 or self.trace_fitness < 1.0


def _require_pm4py() -> None:
    if not PM4PY_AVAILABLE:
        raise RuntimeError(
            "pm4py is not installed or available in the current environment. "
            "Install with `pip install pm4py` or install the `pm4py` extra."
        )


def traces_to_pm4py_log(
    traces: Sequence[Sequence[str]],
    case_prefix: str = "case_",
    start_timestamp_ns: int = 1_000_000_000,
    step_ns: int = 1_000_000_000,
) -> Any:
    """Convert a sequence of activity-name traces into a PM4Py EventLog."""
    _require_pm4py()
    log = EventLog()
    for case_idx, trace_acts in enumerate(traces):
        pm_trace = Trace(attributes={"concept:name": f"{case_prefix}{case_idx}"})
        curr_ns = start_timestamp_ns
        for act in trace_acts:
            dt = datetime.fromtimestamp(curr_ns / 1e9, tz=timezone.utc)
            event = Event(
                {
                    "concept:name": str(act),
                    "time:timestamp": dt,
                }
            )
            pm_trace.append(event)
            curr_ns += step_ns
        log.append(pm_trace)
    return log


def ocel_to_pm4py_log(
    ocel_log: OcelLog,
    object_focus: str | None = None,
    group_by_object: bool = True,
) -> Any:
    """Convert an AutoFDE OcelLog to a PM4Py EventLog.

    If group_by_object is True, each object in the log forms a case (trace)
    containing the sequence of events linked to that object.
    If object_focus is specified, only that specific object's trace is exported.
    """
    _require_pm4py()
    log = EventLog()

    if group_by_object:
        obj_map = {obj.id: obj for obj in ocel_log.objects}
        target_objects = (
            [object_focus] if object_focus is not None else list(obj_map.keys())
        )
        for obj_id in target_objects:
            if obj_id not in obj_map:
                continue
            project_object_trace(ocel_log, obj_id)
            pm_trace = Trace(
                attributes={
                    "concept:name": obj_id,
                    "ocel:type": obj_map[obj_id].object_type,
                }
            )
            # Find matching events to preserve real timestamps
            event_map = {e.id: e for e in ocel_log.events}
            linked_event_ids = [
                link.event_id
                for link in ocel_log.event_object_links
                if link.object_id == obj_id
            ]
            linked_events = sorted(
                [event_map[eid] for eid in linked_event_ids if eid in event_map],
                key=lambda e: (e.timestamp_ns, e.id),
            )

            for evt in linked_events:
                dt = datetime.fromtimestamp(evt.timestamp_ns / 1e9, tz=timezone.utc)
                event = Event(
                    {
                        "concept:name": evt.activity,
                        "time:timestamp": dt,
                        "ocel:event_id": evt.id,
                    }
                )
                pm_trace.append(event)
            log.append(pm_trace)
    else:
        # Single global chronological case
        pm_trace = Trace(attributes={"concept:name": "global_trace"})
        for evt in sorted(ocel_log.events, key=lambda e: (e.timestamp_ns, e.id)):
            dt = datetime.fromtimestamp(evt.timestamp_ns / 1e9, tz=timezone.utc)
            event = Event(
                {
                    "concept:name": evt.activity,
                    "time:timestamp": dt,
                    "ocel:event_id": evt.id,
                }
            )
            pm_trace.append(event)
        log.append(pm_trace)

    return log


def discover_lawful_model(
    lawful_traces: Sequence[Sequence[str]] | Any,
) -> LawfulProcessModel:
    """Discover a lawful Petri net from training/reference traces using PM4Py inductive miner."""
    _require_pm4py()
    if not isinstance(lawful_traces, EventLog):
        event_log = traces_to_pm4py_log(lawful_traces)
    else:
        event_log = lawful_traces

    net, initial_marking, final_marking = pm4py.discover_petri_net_inductive(event_log)
    activities = tuple(
        sorted({t.label for t in net.transitions if t.label is not None})
    )
    return LawfulProcessModel(
        net=net,
        initial_marking=initial_marking,
        final_marking=final_marking,
        discovered_activities=activities,
    )


def evaluate_counterfactual_trace(
    model: LawfulProcessModel,
    candidate_trace: Sequence[str] | Any,
) -> CounterfactualValidationResult:
    """Evaluate a candidate (or counterfactual mutant) trace against a lawful process model.

    Computes:
    - Token replay fitness and token counts (missing, remaining, produced, consumed)
    - Optimal alignments (identifying log-only moves and model-only moves)
    """
    _require_pm4py()
    if not isinstance(candidate_trace, EventLog):
        eval_log = traces_to_pm4py_log([candidate_trace])
    else:
        eval_log = candidate_trace

    # 1. Token-based replay
    replay_results = pm4py.fitness_token_based_replay(
        eval_log,
        model.net,
        model.initial_marking,
        model.final_marking,
    )

    fitness = float(replay_results.get("log_fitness", 0.0))
    missing = int(replay_results.get("missing_tokens", 0))
    remaining = int(replay_results.get("remaining_tokens", 0))
    produced = int(replay_results.get("produced_tokens", 0))
    consumed = int(replay_results.get("consumed_tokens", 0))

    # 2. Optimal Alignments
    alignments = pm4py.conformance_diagnostics_alignments(
        eval_log,
        model.net,
        model.initial_marking,
        model.final_marking,
    )

    alignment_steps: list[AlignmentStep] = []
    deviations: list[AlignmentStep] = []
    total_cost = 0

    if alignments:
        diag = alignments[0]
        total_cost = int(diag.get("cost", 0))
        raw_alignment = diag.get("alignment", [])
        for log_move, model_move in raw_alignment:
            # In PM4Py, '>>' denotes a skipped move
            is_sync = (log_move == model_move) and (log_move not in (">>", None))
            step = AlignmentStep(
                log_move=None if log_move == ">>" else log_move,
                model_move=None if model_move == ">>" else model_move,
                is_sync=is_sync,
            )
            alignment_steps.append(step)
            if not is_sync:
                deviations.append(step)

    is_conforming = (fitness >= 1.0) and (total_cost == 0) and (len(deviations) == 0)

    return CounterfactualValidationResult(
        is_conforming=is_conforming,
        trace_fitness=fitness,
        alignment_cost=total_cost,
        missing_tokens=missing,
        remaining_tokens=remaining,
        produced_tokens=produced,
        consumed_tokens=consumed,
        alignment_steps=tuple(alignment_steps),
        deviations=tuple(deviations),
        evidence_status="ALIVE",
    )
