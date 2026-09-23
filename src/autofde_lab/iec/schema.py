"""Value-independent structural shape inference.

Shapes are deterministic summaries of JSON-like structures. They intentionally
erase concrete values while preserving container topology and primitive types,
which makes them useful for discovering repeated contracts across repositories.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .model import digest


@dataclass(frozen=True, slots=True)
class Shape:
    kind: str
    fields: tuple[tuple[str, "Shape"], ...] = ()
    items: tuple["Shape", ...] = ()

    @property
    def shape_id(self) -> str:
        return digest(self)


def infer_shape(value: Any) -> Shape:
    if value is None:
        return Shape("null")
    if isinstance(value, bool):
        return Shape("boolean")
    if isinstance(value, int) and not isinstance(value, bool):
        return Shape("integer")
    if isinstance(value, float):
        return Shape("number")
    if isinstance(value, str):
        return Shape("string")
    if isinstance(value, dict):
        return Shape(
            "object",
            fields=tuple(
                (str(key), infer_shape(item))
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            ),
        )
    if isinstance(value, (list, tuple)):
        unique: dict[str, Shape] = {}
        for item in value:
            shape = infer_shape(item)
            unique[shape.shape_id] = shape
        return Shape(
            "array",
            items=tuple(unique[key] for key in sorted(unique)),
        )
    return Shape(type(value).__name__)


@dataclass(frozen=True, slots=True)
class ShapeCorrespondence:
    left_id: str
    right_id: str
    shape_id: str
    standing: str = "CANDIDATE"
    required_verifier: str = "iec.translation-validation"

    @property
    def candidate_id(self) -> str:
        return digest(self)


def same_shape_candidates(
    values: tuple[tuple[str, Any], ...],
) -> tuple[ShapeCorrespondence, ...]:
    buckets: dict[str, list[str]] = {}
    for identity, value in values:
        buckets.setdefault(infer_shape(value).shape_id, []).append(identity)

    candidates: list[ShapeCorrespondence] = []
    for shape_id, identities in sorted(buckets.items()):
        ordered = sorted(set(identities))
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                candidates.append(
                    ShapeCorrespondence(
                        left_id=left,
                        right_id=right,
                        shape_id=shape_id,
                    )
                )
    return tuple(candidates)
