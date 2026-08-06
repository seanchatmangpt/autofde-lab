# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Persistent agent runtime over POWL 2.0 candidate plans.

Computes candidate plans across epochs and records a two-phase occurrence
ledger. It never actuates, admits, brokers, or issues an authoritative receipt.
"""

from __future__ import annotations

from skdecide.agent.bridge import (
    IntentRegisteringPolicies,
    SessionRolloutCallback,
    action_labels,
    resolve_enabled_node,
)
from skdecide.agent.epoch import DecisionEpoch, atom_labels
from skdecide.agent.ledger import (
    IntentToken,
    LedgerPhase,
    LedgerRecord,
    OccurrenceLedger,
)
from skdecide.agent.models import AgentOutcome, EpochReceipt, EpochStanding
from skdecide.agent.refusals import (
    BLOCKED_ACTION_NODE_UNRESOLVED,
    BLOCKED_LEDGER_UNRESUMABLE,
    CLAIM_CEILING,
    AgentRefusal,
    AgentRefusalCode,
)
from skdecide.agent.session import AgentSession

__all__ = [
    "AgentOutcome",
    "AgentRefusal",
    "AgentRefusalCode",
    "AgentSession",
    "BLOCKED_ACTION_NODE_UNRESOLVED",
    "BLOCKED_LEDGER_UNRESUMABLE",
    "CLAIM_CEILING",
    "DecisionEpoch",
    "EpochReceipt",
    "EpochStanding",
    "IntentRegisteringPolicies",
    "IntentToken",
    "LedgerPhase",
    "LedgerRecord",
    "OccurrenceLedger",
    "SessionRolloutCallback",
    "action_labels",
    "atom_labels",
    "resolve_enabled_node",
]
