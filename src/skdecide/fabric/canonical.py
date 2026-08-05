# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Canonical serialization and hashing for fabric identities and receipts."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any, Mapping

from skdecide.fabric.models import DecisionRefusal, RefusalCode

_ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]+")


def canonical_json(value: Any) -> str:
    """Serialize a value into stable, compact JSON."""
    return json.dumps(
        to_jsonable(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256(value: Any) -> str:
    """Hash the canonical JSON representation of a value."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def to_jsonable(value: Any) -> Any:
    """Convert common solver values into stable JSON-compatible data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return to_jsonable(value.value)
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if hasattr(value, "model_dump"):
        return to_jsonable(value.model_dump(mode="json", exclude_none=True))
    if isinstance(value, Mapping):
        return {
            str(key): to_jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        converted = [to_jsonable(item) for item in value]
        return sorted(converted, key=canonical_json)
    if hasattr(value, "_asdict"):
        return to_jsonable(value._asdict())
    if hasattr(value, "to_json"):
        rendered = value.to_json()
        try:
            return to_jsonable(json.loads(rendered))
        except (TypeError, json.JSONDecodeError):
            return str(rendered)
    if hasattr(value, "__dict__"):
        public = {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_") and not callable(item)
        }
        if public:
            return to_jsonable(public)
    rendered = _ADDRESS_RE.sub("<address>", str(value))
    if rendered:
        return rendered
    raise DecisionRefusal(
        RefusalCode.SERIALIZATION_FAILED,
        f"cannot serialize value of type {type(value).__name__}",
    )
