"""autofde_lab.sa2a.case_studies.manufacturing -- sa2a-mfg-01 case study package.

MFG-01A (baseline admitted into repo), per MIGRATION_PLAN.md. This package is
the migrated, import-fixed sa2a-mfg-01 scratch prototype: a real, seeded,
multi-agent (ResourceAgent x4, AuthorityAgent, Actuator, VerifierAgent)
manufacturing control loop over a fixed M1-M4 plant, emitting real OCEL 2.0
evidence via `ocel_adapter`. This case study has no PRD/ARD entry; its
governing spec is this package's own `CONTRACT.md` (once migrated) plus
`MIGRATION_PLAN.md`.

Standing (per `.claude/rules/standing-law.md`): `technicalStanding` is
PARTIAL_ALIVE for this fixed-plant baseline -- real observed execution, real
OCEL output, byte-for-byte replay determinism, and three invariants
independently re-derived from durable OCEL JSON. It is not `ALIVE` for any
claim beyond this fixed four-machine plant: no generative world model
`G(seed, theta) -> W` (planned MFG-01B), no generated HDDL/POWL/FOND
projection (planned MFG-01C), and no frontier falsifier (planned MFG-01D)
exist in this package. `organizationalStanding` and `enterpriseStanding` are
UNKNOWN -- not computed by anything in this repo.
"""

from __future__ import annotations

from autofde_lab.sa2a.case_studies.manufacturing.actuator import Actuator
from autofde_lab.sa2a.case_studies.manufacturing.authority_agent import AuthorityAgent
from autofde_lab.sa2a.case_studies.manufacturing.ocel_adapter import LogRef, new_log_ref
from autofde_lab.sa2a.case_studies.manufacturing.resource_agent import ResourceAgent
from autofde_lab.sa2a.case_studies.manufacturing.runtime import run
from autofde_lab.sa2a.case_studies.manufacturing.verifier import VerifierAgent

__all__ = [
    "Actuator",
    "AuthorityAgent",
    "LogRef",
    "ResourceAgent",
    "VerifierAgent",
    "new_log_ref",
    "run",
]
