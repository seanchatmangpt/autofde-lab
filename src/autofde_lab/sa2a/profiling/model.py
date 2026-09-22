"""Deterministic semantic consequence profiling for Semantic A2A.

This module adopts the useful algebra from AgentPProf -- uniform operations,
query-time stack projection, and conserved additive measures -- while preserving
SA2A's stronger evidence and authority boundaries.

Unlike AgentPProf's recursive segmentation path, this layer does not infer task
identity from natural-language trajectories. A SemanticOperation must carry an
explicit 'semantic_path' supplied by admitted SA2A semantics (or by a caller
that accepts the lower evidence ceiling). Missing semantic identity or a
requested dimension/measure fails closed.

Profiles are observational evidence only. They do not admit, authorize,
actuate, mint BRCE receipts, or qualify MachineExperience.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping, Sequence

SEMANTIC_PATH_FIELD = "semantic_path"


class SemanticProfilingError(ValueError):
    """Base class for fail-closed semantic profiling errors."""


class MissingSemanticPath(SemanticProfilingError):
    """Raised when an operation has no explicit semantic responsibility path."""


class MissingProfileDimension(SemanticProfilingError):
    """Raised when a requested stack/filter dimension is absent."""


class MissingProfileMeasure(SemanticProfilingError):
    """Raised when a requested additive measure is absent."""


class InvalidAdditiveMeasure(SemanticProfilingError):
    """Raised when a measure cannot participate in additive profiling."""


def _as_decimal(value: int | float | Decimal, *, name: str) -> Decimal:
    if isinstance(value, bool):
        raise InvalidAdditiveMeasure(
            f"{name!r} cannot use a boolean as an additive measure"
        )
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidAdditiveMeasure(
            f"{name!r} is not a numeric additive measure: {value!r}"
        ) from exc
    if not result.is_finite() or result < 0:
        raise InvalidAdditiveMeasure(
            f"{name!r} must be finite and non-negative, got {value!r}"
        )
    return result


@dataclass(frozen=True, slots=True)
class SemanticOperation:
    """Observed operation with explicit semantic identity and additive measures."""

    operation_id: str
    activity: str
    timestamp_ns: int
    semantic_path: tuple[str, ...]
    dimensions: tuple[tuple[str, str], ...] = ()
    measures: tuple[tuple[str, Decimal], ...] = ()
    source: str = "unknown"

    @classmethod
    def create(
        cls,
        *,
        operation_id: str,
        activity: str,
        timestamp_ns: int,
        semantic_path: Sequence[str],
        dimensions: Mapping[str, str] | None = None,
        measures: Mapping[str, int | float | Decimal] | None = None,
        source: str = "unknown",
    ) -> "SemanticOperation":
        path = tuple(str(segment).strip() for segment in semantic_path)
        if not path or any(not segment for segment in path):
            raise MissingSemanticPath(
                f"operation {operation_id!r} requires a non-empty explicit semantic_path"
            )

        dims = tuple(
            sorted((str(key), str(value)) for key, value in (dimensions or {}).items())
        )
        normalized_measures = tuple(
            sorted(
                (str(key), _as_decimal(value, name=str(key)))
                for key, value in (measures or {}).items()
            )
        )
        return cls(
            operation_id=str(operation_id),
            activity=str(activity),
            timestamp_ns=int(timestamp_ns),
            semantic_path=path,
            dimensions=dims,
            measures=normalized_measures,
            source=str(source),
        )

    def dimension(self, name: str) -> str:
        if name == "activity":
            return self.activity
        if name == "source":
            return self.source
        if name == "operation_id":
            return self.operation_id
        for key, value in self.dimensions:
            if key == name:
                return value
        raise MissingProfileDimension(
            f"operation {self.operation_id!r} has no explicit dimension {name!r}"
        )

    def measure(self, name: str) -> Decimal:
        for key, value in self.measures:
            if key == name:
                return value
        raise MissingProfileMeasure(
            f"operation {self.operation_id!r} has no explicit additive measure {name!r}"
        )


@dataclass(frozen=True, slots=True)
class ProfileView:
    """Query-time filter, stack projection, and additive measure."""

    measure: str
    stack_fields: tuple[str, ...] = (SEMANTIC_PATH_FIELD,)
    required_dimensions: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.measure:
            raise ValueError("ProfileView.measure must be non-empty")
        if not self.stack_fields:
            raise ValueError("ProfileView.stack_fields must be non-empty")
        if len(set(self.stack_fields)) != len(self.stack_fields):
            raise ValueError("ProfileView.stack_fields must not contain duplicates")


@dataclass(frozen=True, slots=True)
class ProfileRow:
    """One folded stack and its conserved additive weight."""

    stack: tuple[str, ...]
    weight: Decimal


@dataclass(frozen=True, slots=True)
class SemanticProfile:
    """Folded observational profile that never grants actuation authority."""

    measure: str
    stack_fields: tuple[str, ...]
    rows: tuple[ProfileRow, ...]
    total_weight: Decimal
    selected_operations: int
    consequence_class: str = field(default="OBSERVATIONAL", init=False)
    authorizes_actuation: bool = field(default=False, init=False, repr=False)

    def weight_for(self, stack: Sequence[str]) -> Decimal:
        target = tuple(stack)
        for row in self.rows:
            if row.stack == target:
                return row.weight
        return Decimal(0)

    def to_collapsed_stacks(self) -> str:
        """Render deterministic flame-graph/stack-collapse text.

        This is intentionally not claimed to be a pprof protobuf.
        """
        return "\n".join(
            f"{';'.join(row.stack)} {format(row.weight, 'f')}" for row in self.rows
        )


def _selected(operation: SemanticOperation, view: ProfileView) -> bool:
    for name, expected in view.required_dimensions:
        if operation.dimension(name) != expected:
            return False
    return True


def _stack(
    operation: SemanticOperation,
    fields: Sequence[str],
) -> tuple[str, ...]:
    frames: list[str] = []
    for field_name in fields:
        if field_name == SEMANTIC_PATH_FIELD:
            frames.extend(operation.semantic_path)
        else:
            frames.append(operation.dimension(field_name))
    if not frames:
        raise MissingProfileDimension(
            f"operation {operation.operation_id!r} projected to an empty stack"
        )
    return tuple(frames)


def fold_operations(
    operations: Iterable[SemanticOperation],
    view: ProfileView,
) -> SemanticProfile:
    """Filter, project, and fold operations with exact decimal conservation."""
    aggregate: dict[tuple[str, ...], Decimal] = {}
    total = Decimal(0)
    selected = 0

    for operation in operations:
        if not _selected(operation, view):
            continue
        weight = operation.measure(view.measure)
        stack = _stack(operation, view.stack_fields)
        aggregate[stack] = aggregate.get(stack, Decimal(0)) + weight
        total += weight
        selected += 1

    rows = tuple(
        ProfileRow(stack=stack, weight=weight)
        for stack, weight in sorted(
            aggregate.items(),
            key=lambda item: (-item[1], item[0]),
        )
    )
    folded_total = sum((row.weight for row in rows), Decimal(0))
    if folded_total != total:
        raise AssertionError(
            "semantic profile conservation failure: "
            f"input={total} folded={folded_total}"
        )

    return SemanticProfile(
        measure=view.measure,
        stack_fields=view.stack_fields,
        rows=rows,
        total_weight=total,
        selected_operations=selected,
    )
