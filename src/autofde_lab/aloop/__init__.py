# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ALOOP: courts over autonomous *process* behaviour, recorded as OCEL 2.0.

Spec: ``docs/rfcs/RFC-ALOOP-v26.9.25.md`` (FINAL_SPEC candidate, NEXT_CALVER).

Only ALOOP-001 (basic closed loop) is implemented here; ALOOP-002..010 are
typed obligations in the RFC. The OCEL log is evidence, never proof: the
court derives a causal graph from qualified E2O relations and refuses or
downgrades whatever that graph does not support. Since court r9 an unsealed
log can at most be CONSISTENT_UNDER_ASSUMED_COMPLETENESS (exit 3); QUALIFIED
(exit 0) requires the sealed-recorder profile (``aloop.seal``) and complete
external witnesses.
"""

from autofde_lab.aloop.court import (
    CONSISTENT,
    EXIT_CONSISTENT_UNDER_ASSUMED_COMPLETENESS,
    EXIT_NOT_QUALIFIED,
    EXIT_QUALIFIED,
    EXIT_REFUSED,
    AloopRefusal,
    evaluate_document,
    evaluate_path,
    load_profile,
)

__all__ = [
    "CONSISTENT",
    "EXIT_CONSISTENT_UNDER_ASSUMED_COMPLETENESS",
    "EXIT_QUALIFIED",
    "EXIT_NOT_QUALIFIED",
    "EXIT_REFUSED",
    "AloopRefusal",
    "evaluate_document",
    "evaluate_path",
    "load_profile",
]
