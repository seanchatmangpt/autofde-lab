"""BRCE (Bounded Runtime Consequence Engine) package for Semantic A2A (RFC-SA2A-001 v26.9.16)."""

from autofde_lab.sa2a.brce.boundary import (
    BoundaryExecutionResult,
    ColludingRolesError,
    ConsequenceActuator,
    ConsequenceBoundary,
    ConsequenceBoundaryError,
    ConsequenceVerifier,
    ExecutionEnvelope,
    ReplayProtectionViolationError,
    UnreceiptedActuationAttemptError,
)
from autofde_lab.sa2a.brce.receipts import (
    FinalReceipt,
    PreparedReceipt,
    ReceiptStore,
    TerminalReceiptState,
    compute_receipt_digest,
)
from autofde_lab.sa2a.brce.replay import (
    ReplayEngine,
    ReplayReport,
    ReplayStanding,
    ReplayVerdict,
)

__all__ = [
    "BoundaryExecutionResult",
    "ColludingRolesError",
    "ConsequenceActuator",
    "ConsequenceBoundary",
    "ConsequenceBoundaryError",
    "ConsequenceVerifier",
    "ExecutionEnvelope",
    "FinalReceipt",
    "PreparedReceipt",
    "ReceiptStore",
    "ReplayEngine",
    "ReplayProtectionViolationError",
    "ReplayReport",
    "ReplayStanding",
    "ReplayVerdict",
    "TerminalReceiptState",
    "UnreceiptedActuationAttemptError",
    "compute_receipt_digest",
]
