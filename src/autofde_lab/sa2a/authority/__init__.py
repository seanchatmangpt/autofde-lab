"""Authority module for Semantic A2A (RFC-SA2A-001 v26.9.16).

Provides:
- AuthorityBroker (§28, §29)
- AuthorityDecision, AuthorityGrant, ConsequenceRequest
- ConfusedDeputyGuard (§54)
- ODRL mapping (§28)
"""

from autofde_lab.sa2a.authority.broker import (
    REFUSED_AGENT_IS_NOT_AUTHORITY,
    REFUSED_CAPABILITY_IS_NOT_AUTHORITY,
    REFUSED_CONSTRAINT_VIOLATION,
    REFUSED_EXPIRED_GRANT,
    REFUSED_NO_GRANT,
    REFUSED_PLAN_IS_NOT_AUTHORITY,
    REFUSED_PROHIBITED,
    REFUSED_PROOF_IS_NOT_AUTHORITY,
    REFUSED_UNFULFILLED_DUTY,
    AuthorityBroker,
    AuthorityDecision,
    AuthorityGrant,
    ConsequenceRequest,
)
from autofde_lab.sa2a.authority.confused_deputy import (
    REFUSED_CONFUSED_DEPUTY,
    REFUSED_UNAUTHORIZED_DELEGATION,
    ConfusedDeputyGuard,
    DelegationHop,
    DeputyGuardResult,
    InvocationContext,
)
from autofde_lab.sa2a.authority.odrl import (
    Asset,
    Constraint,
    Duty,
    OdrlAction,
    OdrlOperator,
    Party,
    Permission,
    Policy,
    Prohibition,
)

__all__ = [
    "AuthorityBroker",
    "AuthorityDecision",
    "AuthorityGrant",
    "ConsequenceRequest",
    "ConfusedDeputyGuard",
    "InvocationContext",
    "DelegationHop",
    "DeputyGuardResult",
    "Party",
    "Asset",
    "Constraint",
    "Duty",
    "Permission",
    "Prohibition",
    "Policy",
    "OdrlAction",
    "OdrlOperator",
    "REFUSED_AGENT_IS_NOT_AUTHORITY",
    "REFUSED_CAPABILITY_IS_NOT_AUTHORITY",
    "REFUSED_PLAN_IS_NOT_AUTHORITY",
    "REFUSED_PROOF_IS_NOT_AUTHORITY",
    "REFUSED_CONFUSED_DEPUTY",
    "REFUSED_UNAUTHORIZED_DELEGATION",
    "REFUSED_NO_GRANT",
    "REFUSED_PROHIBITED",
    "REFUSED_CONSTRAINT_VIOLATION",
    "REFUSED_UNFULFILLED_DUTY",
    "REFUSED_EXPIRED_GRANT",
]
