"""Detector for Service selector mismatch faults.

Source mechanism (fault-injector evidence):
sregym/generators/fault/inject_virtual.py,
VirtualizationFaultInjector.inject_wrong_service_selector() (around line 807):

    current_selectors = service_config.get("spec", {}).get("selector", {})
    current_selectors["current_service_name"] = service
    service_config["spec"]["selector"] = current_selectors
    self.kubectl.patch_service(service, self.namespace, service_config)

This mutates a live Service's ``spec.selector`` by adding an extra key/value
pair that no Pod carries in its labels. kube-proxy/Endpoints reconciliation
then finds zero matching Pods, so the Service silently blackholes traffic
even though the Service object and the backing Deployment both look healthy.

No existing detector in this repo inspects Service selectors against backing
Deployment pod-template labels (confirmed via
``grep -l selector src/autofde_lab_planner/detectors/*.py`` -> only
object_reconstruction.py and scheduling_deadlock.py matched, neither of which
checks Service<->Deployment selector agreement).
"""

from __future__ import annotations

from typing import Any

from autofde_lab_planner.models import ServiceSelectorMismatchFault


def detect_service_selector_mismatches(
    services_json: dict[str, Any] | list[dict[str, Any]] | None = None,
    deployments_json: dict[str, Any] | list[dict[str, Any]] | None = None,
    namespace: str = "default",
) -> list[ServiceSelectorMismatchFault]:
    """Detects Services whose selector contains keys that do not match the
    labels of the Pod template of their corresponding Deployment.

    Correspondence between a Service and a Deployment is established by exact
    name equality (the SREGym benchmark app manifests consistently name the
    Service after the Deployment/microservice it fronts), which is the same
    correspondence the fault injector itself assumes when it is handed a
    single microservice name to target.
    """
    svc_items = _to_item_list(services_json)
    dep_items = _to_item_list(deployments_json)

    dep_labels_by_name: dict[str, dict[str, str]] = {}
    for dep in dep_items:
        dep_meta = dep.get("metadata") or {}
        dep_name = dep_meta.get("name", "")
        if not dep_name:
            continue
        pod_meta = ((dep.get("spec") or {}).get("template") or {}).get("metadata") or {}
        dep_labels_by_name[dep_name] = pod_meta.get("labels") or {}

    faults: list[ServiceSelectorMismatchFault] = []

    for svc in svc_items:
        svc_meta = svc.get("metadata") or {}
        svc_name = svc_meta.get("name", "")
        svc_ns = svc_meta.get("namespace") or namespace
        if not svc_name:
            continue

        selector = (svc.get("spec") or {}).get("selector") or {}
        if not selector:
            continue

        dep_name = svc_name
        pod_labels = dep_labels_by_name.get(dep_name)
        if pod_labels is None:
            # No corresponding Deployment observed; cannot establish ground
            # truth for this Service's selector, so this is not evidence of
            # a fault (absence of a match is not evidence of a mismatch).
            continue

        mismatched_keys = tuple(
            sorted(
                key
                for key, value in selector.items()
                if pod_labels.get(key) != value
            )
        )

        if mismatched_keys:
            faults.append(
                ServiceSelectorMismatchFault(
                    service_name=svc_name,
                    namespace=svc_ns,
                    deployment_name=dep_name,
                    mismatched_keys=mismatched_keys,
                    original_selector=dict(pod_labels),
                )
            )

    return faults


def _to_item_list(data: dict[str, Any] | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not data:
        return []
    if isinstance(data, dict):
        raw_items = data.get("items")
        if isinstance(raw_items, list):
            items = raw_items
        else:
            items = [data]
    elif isinstance(data, list):
        items = data
    else:
        return []
    return [i for i in items if isinstance(i, dict)]
