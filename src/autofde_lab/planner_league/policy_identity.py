"""Stable semantic identity for Planner League policies.

Policy identity includes every axis of PolicySpec, including constructor
parameters. It never depends on Python object addresses or repr() output that
can change between processes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from types import FunctionType
from typing import Any

from .core import PolicySpec


def _stable_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, tuple):
        return [_stable_value(item) for item in value]
    if isinstance(value, list):
        return [_stable_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _stable_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if is_dataclass(value):
        return {
            "dataclass": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": _stable_value(asdict(value)),
        }
    if isinstance(value, FunctionType) or callable(value):
        code = getattr(value, "__code__", None)
        if code is None:
            raise ValueError(
                "REFUSED:UNSTABLE_POLICY_PARAMETER_IDENTITY:"
                f"{type(value).__qualname__}"
            )
        closure = tuple(
            _stable_value(cell.cell_contents)
            for cell in (getattr(value, "__closure__", None) or ())
        )
        code_digest = hashlib.sha256(
            code.co_code + repr(code.co_consts).encode("utf-8")
        ).hexdigest()
        return {
            "callable": (
                f"{getattr(value, '__module__', '')}."
                f"{getattr(value, '__qualname__', '')}"
            ),
            "code_sha256": code_digest,
            "defaults": _stable_value(getattr(value, "__defaults__", None)),
            "closure": closure,
        }
    raise ValueError(
        "REFUSED:UNSTABLE_POLICY_PARAMETER_IDENTITY:"
        f"{type(value).__module__}.{type(value).__qualname__}"
    )


def policy_identity_payload(policy: PolicySpec) -> dict[str, Any]:
    return {
        "planner_id": policy.planner_id,
        "parameters": _stable_value(policy.parameters),
        "objective_id": policy.objective_id,
        "observation_projection_id": policy.observation_projection_id,
        "action_projection_id": policy.action_projection_id,
        "budget_id": policy.budget_id,
    }


def policy_identity(policy: PolicySpec) -> str:
    encoded = json.dumps(
        policy_identity_payload(policy),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def policy_ref(policy: PolicySpec) -> str:
    return f"urn:autofde:policy:{policy_identity(policy)}"
