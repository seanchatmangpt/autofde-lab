"""GALL-008 semantic telemetry correlation and additive attribution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()


_SECRET_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "bearer",
    "password",
    "secret",
}


@dataclass(frozen=True, slots=True)
class SemanticCorrelation:
    semantic_subject: str
    capability_id: str
    command_id: str
    receipt_id: str
    runtime_subject: str
    role_id: str | None = None

    def validate(self) -> None:
        required = (
            self.semantic_subject,
            self.capability_id,
            self.command_id,
            self.receipt_id,
            self.runtime_subject,
        )
        if any(not value for value in required):
            raise ValueError("semantic telemetry correlation identity is incomplete")

    @property
    def digest(self) -> str:
        self.validate()
        return _digest(asdict(self))


@dataclass(frozen=True, slots=True)
class Measurement:
    dimension: str
    unit: str
    value: float
    source: str
    correlation: SemanticCorrelation
    uncertainty: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        self.correlation.validate()
        if not self.dimension or not self.unit or not self.source:
            raise ValueError("measurement dimension/unit/source are required")
        if self.uncertainty < 0:
            raise ValueError("measurement uncertainty cannot be negative")
        keys = {str(key).lower() for key in self.metadata}
        if keys & _SECRET_KEYS:
            raise ValueError("authority secret/credential keys are forbidden in telemetry")


@dataclass(frozen=True, slots=True)
class SemanticTelemetryArtifact:
    measurements: tuple[Measurement, ...]
    source_versions: Mapping[str, str]

    @classmethod
    def admit(
        cls,
        measurements: Iterable[Measurement],
        *,
        source_versions: Mapping[str, str],
    ) -> "SemanticTelemetryArtifact":
        admitted = tuple(measurements)
        if not admitted:
            raise ValueError("semantic telemetry requires at least one observation")
        for measurement in admitted:
            measurement.validate()
        correlations = {measurement.correlation.digest for measurement in admitted}
        if len(correlations) != 1:
            raise ValueError("telemetry layers do not bind the same semantic consequence")
        if not source_versions:
            raise ValueError("telemetry source/tool versions are required")
        return cls(admitted, dict(source_versions))

    @property
    def semantic_subject(self) -> str:
        return self.measurements[0].correlation.semantic_subject

    @property
    def digest(self) -> str:
        return _digest(
            {
                "measurements": [
                    {
                        **asdict(item),
                        "correlation": asdict(item.correlation),
                        "metadata": dict(item.metadata),
                    }
                    for item in self.measurements
                ],
                "source_versions": dict(self.source_versions),
            }
        )

    def evidence_receipt(self, *, producer_sha: str) -> dict[str, Any]:
        """Emit a powerless GALL-008 receipt consumable by GALL-009 admission."""
        if len(producer_sha) != 40 or any(
            ch not in "0123456789abcdef" for ch in producer_sha
        ):
            raise ValueError("producer_sha must be an exact lowercase 40-hex commit SHA")

        payload: dict[str, Any] = {
            "schema": "autofde.gall.semantic-telemetry-receipt/1",
            "checkpoint": "GALL-008",
            "producer_sha": producer_sha,
            "semantic_subject": self.semantic_subject,
            "correlation_digest": self.measurements[0].correlation.digest,
            "artifact_digest": self.digest,
            "source_versions": dict(self.source_versions),
            "standing": "OBSERVED",
            "authority": "NONE",
            "evidence_ceiling": (
                "observational evidence only; GALL-009 admission and DO remain separate"
            ),
        }
        return {**payload, "receipt_digest": _digest(payload)}

    def conservation(
        self,
        *,
        dimension: str,
        unit: str,
        expected_total: float,
        tolerance: float = 1e-9,
    ) -> dict[str, float]:
        selected = [
            item.value
            for item in self.measurements
            if item.dimension == dimension and item.unit == unit
        ]
        if not selected:
            raise ValueError(f"no additive measurements for {dimension}/{unit}")
        observed = sum(selected)
        residual = expected_total - observed
        if abs(residual) > tolerance and expected_total == 0:
            raise ValueError("non-zero attribution against zero expected total")
        return {
            "expected_total": expected_total,
            "attributed": observed,
            "residual": residual,
            "within_tolerance": float(abs(residual) <= tolerance),
        }
