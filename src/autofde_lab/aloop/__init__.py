# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ALOOP: courts over autonomous *process* behaviour, recorded as OCEL 2.0.

Spec: ``docs/rfcs/RFC-ALOOP-v26.9.25.md`` (FINAL_SPEC candidate, NEXT_CALVER).

ALOOP-001 supplies the causal closed-loop court and ALOOP-004 supplies the
provider-extinction/fresh-job recovery court. The remaining ALOOP obligations
stay typed in the RFC until executable courts exist. The OCEL log is evidence, never proof: the
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

from autofde_lab.aloop.provider_extinction import (
    ArtifactHandoff,
    ExecutionSemantics,
    FailureInjection,
    ProviderExtinctionResult,
    RecoveryQualification,
    compare_provider_substitution,
    qualify_fresh_job_recovery,
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
    "ArtifactHandoff",
    "ExecutionSemantics",
    "FailureInjection",
    "ProviderExtinctionResult",
    "RecoveryQualification",
    "compare_provider_substitution",
    "qualify_fresh_job_recovery",
]
