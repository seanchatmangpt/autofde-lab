"""Map a raw Anomaly to a real SREGym fault-injector method name, or UNCLASSIFIED.

The label set is not invented -- every value below is a real method name
grepped from
`vendor/gyms/sregym/sregym/generators/fault/inject_virtual.py`
(`grep -n "def inject_" ...`), the same ground-truth source the abandoned
14-function enumeration (src/autofde_lab_planner/{models,engine}.py,
commit 72c8dfa) was built against. Anomalies that don't match a known
signature return "UNCLASSIFIED" honestly rather than guessing, per
`.claude/rules/absence-is-not-evidence.md`.
"""

from __future__ import annotations

from autofde_lab_planner.scanner.models import Anomaly

UNCLASSIFIED = "UNCLASSIFIED"

# Real inject_* method names from vendor/gyms/sregym/sregym/generators/fault/inject_virtual.py
INJECT_SCALE_PODS_TO_ZERO = "inject_scale_pods_to_zero"
INJECT_PVC_CLAIM_MISMATCH = "inject_pvc_claim_mismatch"
INJECT_MISSING_CONFIGMAP = "inject_missing_configmap"
INJECT_CONFIGMAP_DRIFT = "inject_configmap_drift"
INJECT_WRONG_SERVICE_SELECTOR = "inject_wrong_service_selector"
INJECT_RBAC_MISCONFIGURATION = "inject_rbac_misconfiguration"
INJECT_MISCONFIG_K8S = "inject_misconfig_k8s"
INJECT_RESOURCE_REQUEST = "inject_resource_request"


def classify(anomaly: Anomaly) -> str:
    """Best-effort, evidence-bounded classification. Never guesses."""
    kind = anomaly.kind
    field = anomaly.field
    rel = anomaly.relation_class

    if kind == "Deployment" and field == "readyReplicas" and rel == "declared_vs_observed":
        return INJECT_SCALE_PODS_TO_ZERO
    if kind == "Deployment" and field == "image" and rel == "declared_vs_observed":
        return INJECT_MISCONFIG_K8S
    if kind == "PersistentVolumeClaim" and rel == "dangling_reference":
        return INJECT_PVC_CLAIM_MISMATCH
    if kind == "ConfigMap" and rel == "dangling_reference" and field == "data":
        return INJECT_MISSING_CONFIGMAP
    if kind == "ConfigMap" and rel == "declared_vs_observed":
        return INJECT_CONFIGMAP_DRIFT
    if kind == "ConfigMap" and rel == "dangling_reference":
        return INJECT_MISSING_CONFIGMAP
    if kind == "Service" and rel == "dangling_reference" and field == "spec.selector":
        return INJECT_WRONG_SERVICE_SELECTOR
    if kind == "ServiceAccount" and rel == "insufficient_capability":
        return INJECT_RBAC_MISCONFIGURATION
    if kind == "ResourceQuota" and rel == "aggregate_threshold":
        return INJECT_RESOURCE_REQUEST

    return UNCLASSIFIED
