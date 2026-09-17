# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""HDDL Task Network to POWL and Multi-Library OCEL Conformance Bridge.

Connects:
- HDDL Hierarchical Decomposition (from ash_pplan)
- POWL Choice Graphs and Partial Orders (from ash_r2rml / powl_v2.ttl)
- Multi-library OCEL Conformance (pm4py, OCPA, Polars)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from autofde_lab.ocel.pm4py_counterfactual import (
    CounterfactualValidationResult,
    LawfulProcessModel,
    discover_lawful_model,
    evaluate_counterfactual_trace,
)

__all__ = [
    "HddlMethodDecomposition",
    "HddlPowlBridgeResult",
    "HddlTask",
    "project_hddl_to_powl_traces",
    "validate_ocel_against_hddl_powl",
]


@dataclass(frozen=True)
class HddlTask:
    """A task in an HDDL task network."""

    name: str
    is_primitive: bool
    parameters: tuple[str, ...] = ()


@dataclass(frozen=True)
class HddlMethodDecomposition:
    """An HDDL method that decomposes a compound task into subtasks."""

    method_name: str
    task_name: str
    subtasks: tuple[str, ...]  # ordered subtask names


@dataclass(frozen=True)
class HddlPowlBridgeResult:
    """Result of mapping HDDL to POWL and verifying OCEL conformance."""

    lawful_model: LawfulProcessModel
    conformance: CounterfactualValidationResult
    decomposed_subtasks: tuple[str, ...]
    is_valid_powl_trace: bool


def project_hddl_to_powl_traces(
    root_task: str,
    methods: Sequence[HddlMethodDecomposition],
) -> list[list[str]]:
    """Recursively expand an HDDL compound task through methods into primitive activity sequences.

    This maps HDDL's hierarchical decomposition into POWL choice graph branches
    and sequential partial orders.
    """
    method_map: dict[str, list[HddlMethodDecomposition]] = {}
    for m in methods:
        method_map.setdefault(m.task_name, []).append(m)

    def expand(task: str) -> list[list[str]]:
        if task not in method_map:
            # Primitive action in POWL
            return [[task]]

        expanded_branches: list[list[str]] = []
        for method in method_map[task]:
            # Method defines an ordered subtask sequence
            subtask_expansions: list[list[list[str]]] = [
                expand(st) for st in method.subtasks
            ]

            # Cartesian product of sequences for the subtasks
            current_combos: list[list[str]] = [[]]
            for st_variants in subtask_expansions:
                next_combos = []
                for prefix in current_combos:
                    for variant in st_variants:
                        next_combos.append(prefix + variant)
                current_combos = next_combos

            expanded_branches.extend(current_combos)

        return expanded_branches

    return expand(root_task)


def validate_ocel_against_hddl_powl(
    root_task: str,
    methods: Sequence[HddlMethodDecomposition],
    candidate_trace: Sequence[str],
) -> HddlPowlBridgeResult:
    """Synthesize a POWL model from HDDL methods and validate candidate/counterfactual traces."""
    lawful_traces = project_hddl_to_powl_traces(root_task, methods)
    lawful_model = discover_lawful_model(lawful_traces)

    conformance = evaluate_counterfactual_trace(lawful_model, candidate_trace)

    all_primitive_steps: set[str] = set()
    for t in lawful_traces:
        all_primitive_steps.update(t)

    return HddlPowlBridgeResult(
        lawful_model=lawful_model,
        conformance=conformance,
        decomposed_subtasks=tuple(sorted(all_primitive_steps)),
        is_valid_powl_trace=conformance.is_conforming,
    )
