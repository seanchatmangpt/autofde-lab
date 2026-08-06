# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""First-class refusal vocabulary for the POWL 2.0 algebra.

Every rejection raised by :mod:`skdecide.powl` names a *specific* structural
law. A refusal is a verdict about shape, never a bare string and never a
generic ``InvalidInput``.

Provenance: the first eight members mirror the ``PowlRefusal`` enum in
``~/wasm4pm-compat/src/powl.rs:1116`` (dual MIT/Apache-2.0). Only the type
shape (variant names) is transcribed; no code is copied.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["PowlRefusal", "PowlError"]


class PowlRefusal(StrEnum):
    """Named structural laws a POWL 2.0 shape can violate."""

    # --- mirrored from ~/wasm4pm-compat/src/powl.rs:1116 ---
    CYCLIC_PARTIAL_ORDER = "CYCLIC_PARTIAL_ORDER"
    INVALID_CHOICE = "INVALID_CHOICE"
    INVALID_CHOICE_ARITY = "INVALID_CHOICE_ARITY"
    IRREDUCIBLE_PROJECTION = "IRREDUCIBLE_PROJECTION"
    LANGUAGE_MISMATCH = "LANGUAGE_MISMATCH"
    CHOICE_GRAPH_DISCONNECTED = "CHOICE_GRAPH_DISCONNECTED"

    # --- required by this package ---
    MULTI_BOUNDARY_CHOICE_GRAPH = "MULTI_BOUNDARY_CHOICE_GRAPH"
    DEPTH_EXCEEDED = "DEPTH_EXCEEDED"
    DANGLING_REFERENCE = "DANGLING_REFERENCE"
    NOT_TRANSITIVELY_REDUCED = "NOT_TRANSITIVELY_REDUCED"
    EDGE_TYPE_MISMATCH = "EDGE_TYPE_MISMATCH"
    INVALID_PARTIAL_ORDER_ARITY = "INVALID_PARTIAL_ORDER_ARITY"
    INVALID_FREQUENCY = "INVALID_FREQUENCY"
    PROHIBITED_NODE_KIND = "PROHIBITED_NODE_KIND"
    BOUND_EXHAUSTED = "BOUND_EXHAUSTED"


class PowlError(ValueError):
    """Raised for every POWL 2.0 structural rejection.

    Carries the named law (:attr:`refusal`) plus human-readable evidence
    (:attr:`detail`).
    """

    def __init__(self, refusal: PowlRefusal, detail: str = "") -> None:
        self.refusal: PowlRefusal = refusal
        self.detail: str = detail
        super().__init__(f"POWL refused: {refusal.value}" + (f" ({detail})" if detail else ""))
