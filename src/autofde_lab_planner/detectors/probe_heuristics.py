"""Category-B4 Detector: Probe Heuristics & Liveness/Readiness Faults."""

from __future__ import annotations

from typing import Any
from autofde_lab_planner.models import ProbeFault


def parse_container_probes(deployment_item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extracts container probes and ports from a Deployment dict."""
    containers_info: dict[str, dict[str, Any]] = {}
    spec = deployment_item.get("spec", {})
    template_spec = spec.get("template", {}).get("spec", {})
    containers = template_spec.get("containers", [])

    for c in containers:
        c_name = c.get("name", "")
        ports = [p.get("containerPort") for p in c.get("ports", []) if "containerPort" in p]
        containers_info[c_name] = {
            "livenessProbe": c.get("livenessProbe"),
            "readinessProbe": c.get("readinessProbe"),
            "ports": ports,
        }
    return containers_info


def detect_probe_faults(
    deployments_json: dict[str, Any] | list[dict[str, Any]],
    pods_json: dict[str, Any] | list[dict[str, Any]] | None = None,
    events_json: dict[str, Any] | list[dict[str, Any]] | None = None,
) -> list[ProbeFault]:
    """Detects readiness or liveness probe misconfigurations and aggressive timing faults.

    Operates over raw K8s API JSON structures (Deployments, Pods, Events).
    """
    items: list[dict[str, Any]] = []
    if isinstance(deployments_json, dict):
        items = deployments_json.get("items", [deployments_json])
    elif isinstance(deployments_json, list):
        items = deployments_json

    pod_items: list[dict[str, Any]] = []
    if isinstance(pods_json, dict):
        pod_items = pods_json.get("items", [pods_json])
    elif isinstance(pods_json, list):
        pod_items = pods_json or []

    # Map deployment_name -> pod statuses (ready count, max restarts)
    pod_metrics: dict[str, dict[str, Any]] = {}
    for p in pod_items:
        labels = p.get("metadata", {}).get("labels", {})
        app_name = labels.get("app") or p.get("metadata", {}).get("name", "").split("-")[0]
        status = p.get("status", {})
        c_statuses = status.get("containerStatuses", [])
        restarts = sum(cs.get("restartCount", 0) for cs in c_statuses)
        ready = all(cs.get("ready", False) for cs in c_statuses) if c_statuses else False
        if app_name not in pod_metrics:
            pod_metrics[app_name] = {"restarts": 0, "unready_count": 0}
        pod_metrics[app_name]["restarts"] += restarts
        if not ready:
            pod_metrics[app_name]["unready_count"] += 1

    faults: list[ProbeFault] = []

    for dep in items:
        metadata = dep.get("metadata", {})
        dep_name = metadata.get("name", "")
        if not dep_name:
            continue

        spec = dep.get("spec", {})
        desired_replicas = spec.get("replicas", 1)
        status = dep.get("status", {})
        ready_replicas = status.get("readyReplicas", 0)

        c_probes = parse_container_probes(dep)

        for c_name, p_info in c_probes.items():
            ports = p_info.get("ports", [])
            for probe_type in ("readinessProbe", "livenessProbe"):
                probe = p_info.get(probe_type)
                if not probe:
                    continue

                http_get = probe.get("httpGet")
                tcp_socket = probe.get("tcpSocket")
                initial_delay = probe.get("initialDelaySeconds")
                period_seconds = probe.get("periodSeconds")
                failure_threshold = probe.get("failureThreshold")

                # Check 1: Aggressive Timing
                # (initialDelaySeconds <= 2 or 0, periodSeconds <= 2, failureThreshold <= 1)
                is_aggressive = (
                    initial_delay is not None
                    and initial_delay <= 2
                    and period_seconds is not None
                    and period_seconds <= 2
                    and failure_threshold is not None
                    and failure_threshold <= 1
                )

                # Check 2: Invalid Endpoint / Port divergence
                is_invalid_endpoint = False
                observed_path = None
                observed_port = None

                if http_get:
                    observed_path = http_get.get("path")
                    observed_port = http_get.get("port")
                elif tcp_socket:
                    observed_port = tcp_socket.get("port")

                # Flag endpoint mismatch if probe path is /healthz and port is 8080,
                # or if specified probe port does not match container exposed ports
                if observed_path == "/healthz" and observed_port == 8080 and 8080 not in ports:
                    is_invalid_endpoint = True
                elif observed_port is not None and isinstance(observed_port, int) and ports and observed_port not in ports:
                    is_invalid_endpoint = True

                # Determine if pod metrics indicate fault (unready replicas or restarts)
                app_pm = pod_metrics.get(dep_name, {})
                has_health_issue = (
                    ready_replicas < desired_replicas
                    or app_pm.get("unready_count", 0) > 0
                    or app_pm.get("restarts", 0) > 0
                )

                if is_invalid_endpoint:
                    faults.append(
                        ProbeFault(
                            deployment_name=dep_name,
                            container_name=c_name,
                            probe_type=probe_type,
                            fault_kind="invalid_endpoint",
                            observed_path=observed_path,
                            observed_port=observed_port,
                            initial_delay=initial_delay,
                            period_seconds=period_seconds,
                            failure_threshold=failure_threshold,
                            ready_replicas=ready_replicas,
                            desired_replicas=desired_replicas,
                            restart_count=app_pm.get("restarts", 0),
                        )
                    )
                elif is_aggressive and (has_health_issue or initial_delay == 0):
                    faults.append(
                        ProbeFault(
                            deployment_name=dep_name,
                            container_name=c_name,
                            probe_type=probe_type,
                            fault_kind="aggressive_timing",
                            observed_path=observed_path,
                            observed_port=observed_port,
                            initial_delay=initial_delay,
                            period_seconds=period_seconds,
                            failure_threshold=failure_threshold,
                            ready_replicas=ready_replicas,
                            desired_replicas=desired_replicas,
                            restart_count=app_pm.get("restarts", 0),
                        )
                    )

    return faults
