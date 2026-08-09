"""Category-B13 Detector: Missing/Corrupted Object Reconstruction."""

from __future__ import annotations

from typing import Any
from autofde_lab_planner.models import MissingObjectFault


def detect_missing_objects(
    deployments_json: dict[str, Any] | list[dict[str, Any]],
    live_services_json: dict[str, Any] | list[dict[str, Any]] | None = None,
    live_configmaps_json: dict[str, Any] | list[dict[str, Any]] | None = None,
    live_secrets_json: dict[str, Any] | list[dict[str, Any]] | None = None,
    pods_json: dict[str, Any] | list[dict[str, Any]] | None = None,
    namespace: str = "default",
) -> list[MissingObjectFault]:
    """Scans Kubernetes state for missing or corrupted core objects (Service, ConfigMap, Secret)."""
    dep_items = _to_item_list(deployments_json)
    svc_items = _to_item_list(live_services_json)
    cm_items = _to_item_list(live_configmaps_json)
    secret_items = _to_item_list(live_secrets_json)
    pod_items = _to_item_list(pods_json)

    live_svc_names: dict[str, dict[str, Any]] = {
        s.get("metadata", {}).get("name"): s for s in svc_items if s.get("metadata", {}).get("name")
    }
    live_cm_names: set[str] = {
        c.get("metadata", {}).get("name") for c in cm_items if c.get("metadata", {}).get("name")
    }
    live_secret_names: set[str] = {
        sec.get("metadata", {}).get("name") for sec in secret_items if sec.get("metadata", {}).get("name")
    }

    faults: list[MissingObjectFault] = []
    seen_fault_keys: set[str] = set()

    for dep in dep_items:
        dep_meta = dep.get("metadata", {})
        dep_name = dep_meta.get("name", "")
        dep_ns = dep_meta.get("namespace") or namespace
        if not dep_name:
            continue

        # Rule 1: Check for corresponding Service
        if dep_name not in live_svc_names:
            fault_key = f"Service:{dep_name}"
            if fault_key not in seen_fault_keys:
                seen_fault_keys.add(fault_key)
                faults.append(
                    MissingObjectFault(
                        kind="Service",
                        object_name=dep_name,
                        namespace=dep_ns,
                        associated_deployment=dep_name,
                        reason="missing_service_for_deployment",
                    )
                )
        else:
            svc_item = live_svc_names[dep_name]
            selector = svc_item.get("spec", {}).get("selector", {})
            if not selector or selector.get("app") != dep_name:
                fault_key = f"Service:{dep_name}:selector"
                if fault_key not in seen_fault_keys:
                    seen_fault_keys.add(fault_key)
                    faults.append(
                        MissingObjectFault(
                            kind="Service",
                            object_name=dep_name,
                            namespace=dep_ns,
                            associated_deployment=dep_name,
                            reason="corrupted_service_selector",
                        )
                    )

        # Rule 2 & 3: Check referenced ConfigMaps and Secrets in Pod spec template
        containers = dep.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        volumes = dep.get("spec", {}).get("template", {}).get("spec", {}).get("volumes", [])

        for v in volumes:
            cm_ref = v.get("configMap", {}).get("name")
            if cm_ref and cm_ref not in live_cm_names:
                fault_key = f"ConfigMap:{cm_ref}"
                if fault_key not in seen_fault_keys:
                    seen_fault_keys.add(fault_key)
                    faults.append(
                        MissingObjectFault(
                            kind="ConfigMap",
                            object_name=cm_ref,
                            namespace=dep_ns,
                            associated_deployment=dep_name,
                            reason="missing_referenced_configmap",
                        )
                    )
            sec_ref = v.get("secret", {}).get("secretName")
            if sec_ref and sec_ref not in live_secret_names:
                fault_key = f"Secret:{sec_ref}"
                if fault_key not in seen_fault_keys:
                    seen_fault_keys.add(fault_key)
                    faults.append(
                        MissingObjectFault(
                            kind="Secret",
                            object_name=sec_ref,
                            namespace=dep_ns,
                            associated_deployment=dep_name,
                            reason="missing_referenced_secret",
                        )
                    )

        for c in containers:
            env = c.get("env", [])
            for e in env:
                val_from = e.get("valueFrom", {})
                cm_key_ref = val_from.get("configMapKeyRef", {}).get("name")
                if cm_key_ref and cm_key_ref not in live_cm_names:
                    fault_key = f"ConfigMap:{cm_key_ref}"
                    if fault_key not in seen_fault_keys:
                        seen_fault_keys.add(fault_key)
                        faults.append(
                            MissingObjectFault(
                                kind="ConfigMap",
                                object_name=cm_key_ref,
                                namespace=dep_ns,
                                associated_deployment=dep_name,
                                reason="missing_referenced_configmap",
                            )
                        )
                sec_key_ref = val_from.get("secretKeyRef", {}).get("name")
                if sec_key_ref and sec_key_ref not in live_secret_names:
                    fault_key = f"Secret:{sec_key_ref}"
                    if fault_key not in seen_fault_keys:
                        seen_fault_keys.add(fault_key)
                        faults.append(
                            MissingObjectFault(
                                kind="Secret",
                                object_name=sec_key_ref,
                                namespace=dep_ns,
                                associated_deployment=dep_name,
                                reason="missing_referenced_secret",
                            )
                        )

    # Rule 4: Check Pod container statuses for CreateContainerConfigError
    for pod in pod_items:
        pod_meta = pod.get("metadata", {})
        pod_ns = pod_meta.get("namespace") or namespace
        c_statuses = pod.get("status", {}).get("containerStatuses", [])
        for cs in c_statuses:
            waiting = cs.get("state", {}).get("waiting", {})
            reason = waiting.get("reason", "")
            msg = waiting.get("message", "")
            if reason == "CreateContainerConfigError":
                # Try to extract object name from message
                # e.g. configmap "media-mongodb" not found or secret "foo" not found
                if 'configmap "' in msg.lower():
                    cm_name = msg.split('configmap "')[1].split('"')[0]
                    fault_key = f"ConfigMap:{cm_name}"
                    if fault_key not in seen_fault_keys:
                        seen_fault_keys.add(fault_key)
                        faults.append(
                            MissingObjectFault(
                                kind="ConfigMap",
                                object_name=cm_name,
                                namespace=pod_ns,
                                reason="missing_referenced_configmap",
                            )
                        )
                elif 'secret "' in msg.lower():
                    sec_name = msg.split('secret "')[1].split('"')[0]
                    fault_key = f"Secret:{sec_name}"
                    if fault_key not in seen_fault_keys:
                        seen_fault_keys.add(fault_key)
                        faults.append(
                            MissingObjectFault(
                                kind="Secret",
                                object_name=sec_name,
                                namespace=pod_ns,
                                reason="missing_referenced_secret",
                            )
                        )

    return faults


def _to_item_list(data: dict[str, Any] | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not data:
        return []
    if isinstance(data, dict):
        return data.get("items", [data])
    if isinstance(data, list):
        return data
    return []
