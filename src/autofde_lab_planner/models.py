"""Domain models and data structures for Category-B fault mechanisms."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# -----------------------------------------------------------------------------
# B4: Probe Fault Models
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class ProbeFault:
    deployment_name: str
    container_name: str
    probe_type: Literal["readinessProbe", "livenessProbe"]
    fault_kind: Literal["invalid_endpoint", "aggressive_timing"]
    observed_path: str | None = None
    observed_port: int | str | None = None
    initial_delay: int | None = None
    period_seconds: int | None = None
    failure_threshold: int | None = None
    ready_replicas: int = 0
    desired_replicas: int = 1
    restart_count: int = 0
    event_messages: tuple[str, ...] = ()


# -----------------------------------------------------------------------------
# B6: OTel Trace Diffing Models
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class ParsedSpan:
    span_id: str
    trace_id: str
    operation_name: str
    service_name: str
    duration_ms: float
    has_error: bool
    status_code: str | None = None
    parent_span_id: str | None = None
    tags: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TraceTree:
    trace_id: str
    spans_by_id: dict[str, ParsedSpan]
    children_by_parent: dict[str, list[str]]
    root_span_ids: list[str]


@dataclass(frozen=True)
class ServiceMetrics:
    service_name: str
    total_spans: int
    error_spans: int
    error_rate: float
    avg_duration_ms: float
    max_duration_ms: float
    downstream_call_count: int


@dataclass(frozen=True)
class TraceAnomalyResult:
    has_anomaly: bool
    root_cause_service: str | None = None
    affected_services: tuple[str, ...] = ()
    anomalous_traces_count: int = 0
    metrics_by_service: dict[str, ServiceMetrics] = field(default_factory=dict)
    reasoning: str = ""


# -----------------------------------------------------------------------------
# B9: flagd Config Drift Models
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class FlagDriftItem:
    flag_name: str
    current_variant: str
    canonical_variant: str = "off"
    target_deployments: tuple[str, ...] = ()


@dataclass(frozen=True)
class FlagdDriftResult:
    has_drift: bool
    configmap_name: str = "flagd-config"
    namespace: str = "astronomy-shop"
    drifted_flags: tuple[FlagDriftItem, ...] = ()
    repaired_flagd_json: str | None = None


# -----------------------------------------------------------------------------
# B13: Object Reconstruction Models
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class MissingObjectFault:
    kind: Literal["Service", "ConfigMap", "Secret", "PVC"]
    object_name: str
    namespace: str
    associated_deployment: str | None = None
    reason: Literal[
        "missing_service_for_deployment",
        "missing_referenced_configmap",
        "missing_referenced_secret",
        "corrupted_service_selector",
        "corrupted_configmap_keys",
    ] = "missing_service_for_deployment"
    missing_keys: tuple[str, ...] = ()


# -----------------------------------------------------------------------------
# Aggregate Engine Diagnosis & Mitigation Models
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class CategoryBDiagnosis:
    probe_faults: tuple[ProbeFault, ...] = ()
    trace_anomalies: TraceAnomalyResult | None = None
    flagd_drift: FlagdDriftResult | None = None
    missing_objects: tuple[MissingObjectFault, ...] = ()
    diagnosis_text: str = ""


@dataclass(frozen=True)
class CategoryBMitigation:
    commands: tuple[str, ...] = ()
    rollout_wait_deployments: tuple[str, ...] = ()
    mitigation_text: str = ""
