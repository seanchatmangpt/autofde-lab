"""ODRL (Open Digital Rights Language) 2.2 mapping and types for Semantic A2A (§28).

Supports Permission, Prohibition, Duty, Party, Asset, and Action IRIs, along
with Policy models used by the Authority Broker to evaluate whether actions
are authorized under formal policy specifications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Sequence

# Standard ODRL 2.2 Namespace IRIs
ODRL_NS = "http://www.w3.org/ns/odrl/2/"


class OdrlAction(str, Enum):
    """Common ODRL and Semantic A2A Action IRIs."""

    USE = "http://www.w3.org/ns/odrl/2/use"
    EXECUTE = "http://www.w3.org/ns/odrl/2/execute"
    TRANSFER = "http://www.w3.org/ns/odrl/2/transfer"
    READ = "http://www.w3.org/ns/odrl/2/read"
    MODIFY = "http://www.w3.org/ns/odrl/2/modify"
    DELETE = "http://www.w3.org/ns/odrl/2/delete"
    ANALYZE = "http://www.w3.org/ns/odrl/2/analyze"
    COMPENSATE = "http://www.w3.org/ns/odrl/2/compensate"
    NOTIFY = "http://www.w3.org/ns/odrl/2/notify"


class OdrlOperator(str, Enum):
    """ODRL Constraint Operators."""

    EQ = "http://www.w3.org/ns/odrl/2/eq"
    NEQ = "http://www.w3.org/ns/odrl/2/neq"
    LT = "http://www.w3.org/ns/odrl/2/lt"
    LTEQ = "http://www.w3.org/ns/odrl/2/lteq"
    GT = "http://www.w3.org/ns/odrl/2/gt"
    GTEQ = "http://www.w3.org/ns/odrl/2/gteq"
    IS_A = "http://www.w3.org/ns/odrl/2/isA"
    IS_PART_OF = "http://www.w3.org/ns/odrl/2/isPartOf"


@dataclass(frozen=True)
class Party:
    """ODRL Party representing an assigner or assignee."""

    uid: str
    role: str = "http://www.w3.org/ns/odrl/2/assignee"  # assignee or assigner
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Asset:
    """ODRL Asset representing the target resource of a policy."""

    uid: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Constraint:
    """ODRL Constraint restricting a rule."""

    left_operand: str
    operator: OdrlOperator | str
    right_operand: Any

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate constraint against runtime context."""
        left_val = context.get(self.left_operand)
        if left_val is None:
            # Check for stripped key if full IRI was used
            short_key = self.left_operand.split("#")[-1].split("/")[-1]
            left_val = context.get(short_key)

        if left_val is None:
            return False

        op = (
            self.operator.value
            if isinstance(self.operator, OdrlOperator)
            else self.operator
        )

        if op in (OdrlOperator.EQ, OdrlOperator.EQ.value, "eq", "=="):
            return left_val == self.right_operand
        elif op in (OdrlOperator.NEQ, OdrlOperator.NEQ.value, "neq", "!="):
            return left_val != self.right_operand
        elif op in (OdrlOperator.LT, OdrlOperator.LT.value, "lt", "<"):
            return left_val < self.right_operand
        elif op in (OdrlOperator.LTEQ, OdrlOperator.LTEQ.value, "lteq", "<="):
            return left_val <= self.right_operand
        elif op in (OdrlOperator.GT, OdrlOperator.GT.value, "gt", ">"):
            return left_val > self.right_operand
        elif op in (OdrlOperator.GTEQ, OdrlOperator.GTEQ.value, "gteq", ">="):
            return left_val >= self.right_operand
        elif op in (OdrlOperator.IS_A, OdrlOperator.IS_A.value, "isA"):
            return left_val == self.right_operand
        elif op in (OdrlOperator.IS_PART_OF, OdrlOperator.IS_PART_OF.value, "isPartOf"):
            return left_val in self.right_operand
        return False


@dataclass(frozen=True)
class Duty:
    """ODRL Duty representing an obligation that must be fulfilled."""

    uid: str
    action: OdrlAction | str
    target: Optional[Asset | str] = None
    assignee: Optional[Party | str] = None
    assigner: Optional[Party | str] = None
    constraints: Sequence[Constraint] = field(default_factory=tuple)


@dataclass(frozen=True)
class Permission:
    """ODRL Permission representing an action an assignee is permitted to perform on an asset."""

    uid: str
    action: OdrlAction | str
    target: Asset | str
    assignee: Party | str
    assigner: Optional[Party | str] = None
    constraints: Sequence[Constraint] = field(default_factory=tuple)
    duties: Sequence[Duty] = field(default_factory=tuple)


@dataclass(frozen=True)
class Prohibition:
    """ODRL Prohibition representing an action an assignee is prohibited from performing."""

    uid: str
    action: OdrlAction | str
    target: Asset | str
    assignee: Party | str
    assigner: Optional[Party | str] = None
    constraints: Sequence[Constraint] = field(default_factory=tuple)


@dataclass(frozen=True)
class Policy:
    """ODRL Policy container holding Permissions, Prohibitions, and Duties."""

    uid: str
    profile: str = "http://www.w3.org/ns/odrl/2/core"
    permissions: Sequence[Permission] = field(default_factory=tuple)
    prohibitions: Sequence[Prohibition] = field(default_factory=tuple)
    duties: Sequence[Duty] = field(default_factory=tuple)
