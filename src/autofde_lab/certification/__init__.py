# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Receipted cloud-certification ladder — `docs/jira/v26.8.12/cloud-cert-wbpr-prd.md` FR2.

`stride_sampler` generalizes the `docs/STATUS.md` Pass-20 discipline (sort a
registry's IDs, take a fixed stride, compute once) into reusable code — that
discipline previously existed only as a one-off manual slice, per the PRD's
Correction 6.

`ladder` defines the three certification tiers and their admission rules,
per FR2. Scenario-variant registries themselves (the actual per-domain
content a Professional-tier sample draws from) are explicitly out of scope
here — per the PRD's own Rollout recommendation, that is deferred to a
follow-up PRD once this module's shape is proven against a real registry.
"""

from __future__ import annotations

from .ladder import CertificationTier, TierResult, evaluate_associate, evaluate_professional
from .stride_sampler import ScenarioRegistry, StrideSample, stride_sample

__all__ = [
    "CertificationTier",
    "TierResult",
    "evaluate_associate",
    "evaluate_professional",
    "ScenarioRegistry",
    "StrideSample",
    "stride_sample",
]
