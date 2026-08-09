"""Composite multi-detector planning engine for Category-B fault mechanisms."""

from __future__ import annotations

from typing import Any

from autofde_lab_planner.detectors.flagd_drift import detect_flagd_config_drift
from autofde_lab_planner.detectors.object_reconstruction import detect_missing_objects
from autofde_lab_planner.detectors.otel_trace import detect_otel_trace_anomalies
from autofde_lab_planner.detectors.probe_heuristics import detect_probe_faults
from autofde_lab_planner.models import CategoryBDiagnosis, CategoryBMitigation
from autofde_lab_planner.remediators.flagd_drift import decide_flagd_remediation_commands
from autofde_lab_planner.remediators.object_reconstruction import decide_object_reconstruction_commands
from autofde_lab_planner.remediators.otel_trace import decide_otel_remediation_commands
from autofde_lab_planner.remediators.probe_heuristics import decide_probe_remediation_commands


class CompositePlannerEngine:
    """Orchestrates detection and remediation generation for Category-B fault mechanisms."""

    def __init__(self, namespace: str = "default", app_name: str = ""):
        self.namespace = namespace
        self.app_name = app_name

    def run_diagnosis(
        self,
        deployments_json: dict[str, Any] | list[dict[str, Any]],
        services_json: dict[str, Any] | list[dict[str, Any]] | None = None,
        configmaps_json: dict[str, Any] | list[dict[str, Any]] | None = None,
        secrets_json: dict[str, Any] | list[dict[str, Any]] | None = None,
        pods_json: dict[str, Any] | list[dict[str, Any]] | None = None,
        events_json: dict[str, Any] | list[dict[str, Any]] | None = None,
        flagd_configmap_json: str | dict[str, Any] | None = None,
        raw_traces_by_service: dict[str, Any] | None = None,
    ) -> CategoryBDiagnosis:
        """Executes all Category-B detectors (B13, B4, B9, B6) and generates diagnosis report."""
        # 1. B13: Missing/Corrupted K8s Objects
        missing_objects = detect_missing_objects(
            deployments_json=deployments_json,
            live_services_json=services_json,
            live_configmaps_json=configmaps_json,
            live_secrets_json=secrets_json,
            pods_json=pods_json,
            namespace=self.namespace,
        )

        # 2. B4: Probe Heuristics (Readiness/Liveness)
        probe_faults = detect_probe_faults(
            deployments_json=deployments_json,
            pods_json=pods_json,
            events_json=events_json,
        )

        # 3. B9: flagd Config Drift
        flagd_drift = None
        if flagd_configmap_json:
            flagd_drift = detect_flagd_config_drift(
                configmap_json_input=flagd_configmap_json,
                namespace=self.namespace,
            )

        # 4. B6: OTel Trace Diffing
        trace_anomalies = None
        if raw_traces_by_service:
            trace_anomalies = detect_otel_trace_anomalies(raw_traces_by_service)

        # Build natural-language diagnosis text
        text_parts: list[str] = []

        if missing_objects:
            objs_str = ", ".join(f"{mo.kind}/{mo.object_name} ({mo.reason})" for mo in missing_objects)
            text_parts.append(f"Detected missing or corrupted Kubernetes objects in namespace {self.namespace}: {objs_str}.")

        if probe_faults:
            pf_str = ", ".join(f"{pf.deployment_name}:{pf.probe_type} ({pf.fault_kind})" for pf in probe_faults)
            text_parts.append(f"Detected probe misconfigurations in namespace {self.namespace}: {pf_str}.")

        if flagd_drift and flagd_drift.has_drift:
            flags_str = ", ".join(f"{df.flag_name}='{df.current_variant}'" for df in flagd_drift.drifted_flags)
            text_parts.append(f"Detected flagd feature flag config drift in namespace {self.namespace}: {flags_str}.")

        if trace_anomalies and trace_anomalies.has_anomaly:
            text_parts.append(f"Detected OTel trace RPC anomalies: {trace_anomalies.reasoning}")

        if not text_parts:
            diagnosis_text = f"No Category-B fault mechanism anomalies detected in namespace {self.namespace}."
        else:
            diagnosis_text = " ".join(text_parts)

        return CategoryBDiagnosis(
            probe_faults=tuple(probe_faults),
            trace_anomalies=trace_anomalies,
            flagd_drift=flagd_drift,
            missing_objects=tuple(missing_objects),
            diagnosis_text=diagnosis_text,
        )

    def run_mitigation(self, diagnosis: CategoryBDiagnosis) -> CategoryBMitigation:
        """Generates all remediation commands across B13, B4, B9, B6 mechanisms."""
        commands: list[str] = []
        rollout_wait: list[str] = []

        # 1. B13 Remediations
        if diagnosis.missing_objects:
            b13_cmds, b13_deps = decide_object_reconstruction_commands(
                list(diagnosis.missing_objects), self.namespace
            )
            commands.extend(b13_cmds)
            rollout_wait.extend(b13_deps)

        # 2. B4 Remediations
        if diagnosis.probe_faults:
            b4_cmds, b4_deps = decide_probe_remediation_commands(
                list(diagnosis.probe_faults), self.namespace
            )
            commands.extend(b4_cmds)
            rollout_wait.extend(b4_deps)

        # 3. B9 Remediations
        if diagnosis.flagd_drift and diagnosis.flagd_drift.has_drift:
            b9_cmds, b9_deps = decide_flagd_remediation_commands(diagnosis.flagd_drift)
            commands.extend(b9_cmds)
            rollout_wait.extend(b9_deps)

        # 4. B6 Remediations
        if diagnosis.trace_anomalies and diagnosis.trace_anomalies.has_anomaly:
            b6_cmds, b6_deps = decide_otel_remediation_commands(
                diagnosis.trace_anomalies, self.namespace
            )
            commands.extend(b6_cmds)
            rollout_wait.extend(b6_deps)

        # Deduplicate wait deployments
        unique_wait = tuple(dict.fromkeys(rollout_wait))
        mitigation_text = (
            f"Generated {len(commands)} remediation actions targeting deployments: {', '.join(unique_wait)}."
            if commands
            else "No remediation actions required."
        )

        return CategoryBMitigation(
            commands=tuple(commands),
            rollout_wait_deployments=unique_wait,
            mitigation_text=mitigation_text,
        )
