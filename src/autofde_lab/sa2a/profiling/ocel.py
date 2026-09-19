"""OCEL 2.0 ingress for Semantic A2A semantic consequence profiling.

The repository already owns deterministic OCEL models and validation. This
adapter reuses them rather than introducing a second trace schema. It does not
guess semantic responsibility: every event must be explicitly linked to a
semantic path by 'semantic_paths'.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import OcelAttributeValue, OcelEvent, OcelValueKind
from autofde_lab.sa2a.profiling.model import (
    InvalidAdditiveMeasure,
    MissingProfileDimension,
    MissingProfileMeasure,
    MissingSemanticPath,
    SemanticOperation,
)


def _event_attributes(event: OcelEvent) -> dict[str, OcelAttributeValue]:
    return {attribute.key: attribute.value for attribute in event.attributes}


def _dimension_value(
    value: OcelAttributeValue,
    *,
    key: str,
    event_id: str,
) -> str:
    if value.kind in {OcelValueKind.LIST, OcelValueKind.MAP, OcelValueKind.NULL}:
        raise MissingProfileDimension(
            f"event {event_id!r} attribute {key!r} is not a scalar profile dimension"
        )
    return str(value.value)


def _measure_value(
    value: OcelAttributeValue,
    *,
    key: str,
    event_id: str,
) -> Decimal:
    if value.kind not in {OcelValueKind.INTEGER, OcelValueKind.FLOAT}:
        raise InvalidAdditiveMeasure(
            f"event {event_id!r} attribute {key!r} is not numeric"
        )
    if isinstance(value.value, bool):
        raise InvalidAdditiveMeasure(
            f"event {event_id!r} attribute {key!r} cannot be boolean"
        )
    return Decimal(str(value.value))


def operations_from_ocel(
    log: OcelLog,
    *,
    semantic_paths: Mapping[str, Sequence[str]],
    dimension_fields: Mapping[str, str] | None = None,
    measure_fields: Mapping[str, str] | None = None,
    source: str = "ocel",
) -> tuple[SemanticOperation, ...]:
    """Project a validated OCEL log into explicit semantic operations.

    'dimension_fields' maps profile dimension to OCEL event attribute.
    'measure_fields' maps additive measure to OCEL event attribute.
    'operation_count=1' is manufactured from the observed event itself; every
    other measure must be explicitly present.

    AgentSight/eBPF data can enter through this boundary after normalization to
    the repository's OCEL representation. No AgentSight-specific schema or
    privileged runtime dependency is introduced here.
    """
    log.validate()
    dimension_fields = dimension_fields or {}
    measure_fields = measure_fields or {}

    operations: list[SemanticOperation] = []
    for event in log.events:
        path = semantic_paths.get(event.id)
        if path is None:
            raise MissingSemanticPath(
                f"OCEL event {event.id!r} has no explicit SA2A semantic path"
            )

        attributes = _event_attributes(event)
        dimensions: dict[str, str] = {}
        for dimension_name, attribute_key in dimension_fields.items():
            value = attributes.get(attribute_key)
            if value is None:
                raise MissingProfileDimension(
                    f"event {event.id!r} is missing dimension "
                    f"attribute {attribute_key!r}"
                )
            dimensions[dimension_name] = _dimension_value(
                value,
                key=attribute_key,
                event_id=event.id,
            )

        measures: dict[str, int | Decimal] = {"operation_count": 1}
        for measure_name, attribute_key in measure_fields.items():
            value = attributes.get(attribute_key)
            if value is None:
                raise MissingProfileMeasure(
                    f"event {event.id!r} is missing measure "
                    f"attribute {attribute_key!r}"
                )
            measures[measure_name] = _measure_value(
                value,
                key=attribute_key,
                event_id=event.id,
            )

        operations.append(
            SemanticOperation.create(
                operation_id=event.id,
                activity=event.activity,
                timestamp_ns=event.timestamp_ns,
                semantic_path=path,
                dimensions=dimensions,
                measures=measures,
                source=source,
            )
        )

    return tuple(operations)
