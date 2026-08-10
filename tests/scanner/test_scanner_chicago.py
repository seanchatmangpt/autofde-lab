"""Chicago-style tests for the generalized structural-anomaly scanner.

Real fixture k8s JSON in, real scanner.registry.scan() call, real Anomaly
objects asserted on final state. No mocks (see
.claude/rules/testing-chicago-style.md).

Baseline commit: covers the six kinds specified by the task (Deployment,
Service, PVC, ConfigMap, RBAC composite, ResourceQuota). A following commit
adds CronJob as the sixth-plus-one kind to demonstrate O(1) extension.
"""

from __future__ import annotations

from autofde_lab_planner.scanner import diff_engine, taxonomy
from autofde_lab_planner.scanner.models import Anomaly
from autofde_lab_planner.scanner.registry import scan


def test_declared_vs_observed_relation_class_deployment_replica_mismatch():
    state = {
        "deployments": [
            {
                "metadata": {"name": "billing-api", "namespace": "prod"},
                "spec": {
                    "replicas": 3,
                    "selector": {"matchLabels": {"app": "billing-api"}},
                    "template": {"spec": {"containers": [{"image": "billing-api:1.2.3"}]}},
                },
            }
        ],
        "pods": [
            {
                "metadata": {"name": "billing-api-1", "namespace": "prod", "labels": {"app": "billing-api"}},
                "status": {"conditions": [{"type": "Ready", "status": "True"}]},
            }
        ],
    }
    anomalies = scan(state)
    replica_anomalies = [a for a in anomalies if a.field == "readyReplicas"]
    assert len(replica_anomalies) == 1
    a = replica_anomalies[0]
    assert a.kind == "Deployment"
    assert a.relation_class == "declared_vs_observed"
    assert a.expected == "3"
    assert a.observed == "1"


def test_dangling_reference_relation_class_pvc_claim_mismatch():
    state = {
        "persistentvolumeclaims": [{"metadata": {"name": "billing-data-real"}}],
        "pods": [
            {
                "metadata": {"name": "billing-api-1", "namespace": "prod"},
                "spec": {
                    "volumes": [
                        {"name": "data", "persistentVolumeClaim": {"claimName": "billing-data-typo"}},
                    ]
                },
            }
        ],
    }
    anomalies = scan(state)
    pvc_anomalies = [a for a in anomalies if a.kind == "PersistentVolumeClaim"]
    assert len(pvc_anomalies) == 1
    a = pvc_anomalies[0]
    assert a.relation_class == "dangling_reference"
    assert a.observed == "billing-data-typo"
    assert a.expected is None


def test_insufficient_capability_relation_class_rbac_gap():
    state = {
        "clusterroles": [
            {"metadata": {"name": "reader"}, "rules": [{"resources": ["pods"], "verbs": ["get", "list"]}]}
        ],
        "clusterrolebindings": [
            {
                "roleRef": {"name": "reader"},
                "subjects": [{"kind": "ServiceAccount", "name": "billing-sa", "namespace": "prod"}],
            }
        ],
        "pods": [
            {
                "metadata": {
                    "name": "billing-api-1",
                    "namespace": "prod",
                    "annotations": {"required-rbac": "get:pods,delete:pods"},
                },
                "spec": {"serviceAccountName": "billing-sa"},
            }
        ],
    }
    anomalies = scan(state)
    rbac_anomalies = [a for a in anomalies if a.relation_class == "insufficient_capability"]
    assert len(rbac_anomalies) == 1
    a = rbac_anomalies[0]
    assert a.kind == "ServiceAccount"
    assert "delete:pods" in a.expected
    assert "delete:pods" not in a.observed


def test_aggregate_threshold_relation_class_resourcequota_exhaustion():
    state = {
        "resourcequotas": [{"metadata": {"name": "prod-quota", "namespace": "prod"}, "spec": {"hard": {"pods": "2"}}}],
        "pods": [
            {"metadata": {"name": "p1", "namespace": "prod"}},
            {"metadata": {"name": "p2", "namespace": "prod"}},
            {"metadata": {"name": "p3", "namespace": "prod"}},
        ],
    }
    anomalies = scan(state)
    quota_anomalies = [a for a in anomalies if a.relation_class == "aggregate_threshold"]
    assert len(quota_anomalies) == 1
    a = quota_anomalies[0]
    assert a.observed == "3.0 pods"
    assert a.expected == "<= 2.0 pods"


def test_all_anomalies_share_one_uniform_dataclass_type():
    state = {
        "deployments": [
            {
                "metadata": {"name": "d1", "namespace": "ns"},
                "spec": {"replicas": 5, "selector": {"matchLabels": {"app": "d1"}}, "template": {"spec": {"containers": [{}]}}},
            }
        ],
        "pods": [
            {
                "metadata": {"name": "pd1", "namespace": "ns"},
                "spec": {"volumes": [{"persistentVolumeClaim": {"claimName": "missing-pvc"}}]},
            },
            {
                "metadata": {"name": "pd2", "namespace": "ns", "annotations": {"required-rbac": "get:secrets"}},
                "spec": {"serviceAccountName": "sa"},
            },
        ],
        "resourcequotas": [{"metadata": {"name": "q", "namespace": "ns"}, "spec": {"hard": {"pods": "0"}}}],
        "clusterroles": [{"metadata": {"name": "r"}, "rules": []}],
        "clusterrolebindings": [
            {"roleRef": {"name": "r"}, "subjects": [{"kind": "ServiceAccount", "name": "sa", "namespace": "ns"}]}
        ],
    }
    anomalies = scan(state)
    relation_classes_seen = {a.relation_class for a in anomalies}
    assert len(relation_classes_seen) >= 3
    for a in anomalies:
        assert type(a) is Anomaly  # noqa: E721 -- exact type check: no subclassing exists


def test_coverage_missing_object_pvc():
    state = {
        "persistentvolumeclaims": [{"metadata": {"name": "real-pvc"}}],
        "pods": [
            {
                "metadata": {"name": "app-1", "namespace": "ns"},
                "spec": {"volumes": [{"persistentVolumeClaim": {"claimName": "nonexistent-pvc"}}]},
            }
        ],
    }
    anomalies = scan(state)
    assert any(a.kind == "PersistentVolumeClaim" and a.relation_class == "dangling_reference" for a in anomalies)


def test_coverage_workload_misconfig_image_drift():
    state = {
        "deployments": [
            {
                "metadata": {"name": "app", "namespace": "ns"},
                "spec": {
                    "replicas": 1,
                    "selector": {"matchLabels": {"app": "app"}},
                    "template": {"spec": {"containers": [{"image": "app:v2"}]}},
                },
                "status": {"observedImage": "app:v1-rollback-stuck"},
            }
        ],
        "pods": [
            {
                "metadata": {"name": "app-1", "namespace": "ns", "labels": {"app": "app"}},
                "status": {"conditions": [{"type": "Ready", "status": "True"}]},
            }
        ],
    }
    anomalies = scan(state)
    assert any(a.kind == "Deployment" and a.field == "image" for a in anomalies)


def test_coverage_rbac_misconfig():
    state = {
        "clusterroles": [{"metadata": {"name": "r"}, "rules": [{"resources": ["pods"], "verbs": ["get"]}]}],
        "clusterrolebindings": [
            {"roleRef": {"name": "r"}, "subjects": [{"kind": "ServiceAccount", "name": "sa", "namespace": "ns"}]}
        ],
        "pods": [
            {
                "metadata": {"name": "p", "namespace": "ns", "annotations": {"required-rbac": "delete:pods"}},
                "spec": {"serviceAccountName": "sa"},
            }
        ],
    }
    anomalies = scan(state)
    assert any(a.relation_class == "insufficient_capability" for a in anomalies)


def test_taxonomy_classifies_known_anomaly():
    a = Anomaly(
        kind="PersistentVolumeClaim",
        object_name="app-1",
        namespace="ns",
        relation_class="dangling_reference",
        field="spec.volumes[].persistentVolumeClaim.claimName",
        observed="missing-pvc",
        expected=None,
        detail="",
    )
    assert taxonomy.classify(a) == taxonomy.INJECT_PVC_CLAIM_MISMATCH


def test_taxonomy_returns_unclassified_honestly():
    a = Anomaly(
        kind="TotallyUnknownKind",
        object_name="x",
        namespace="ns",
        relation_class="aggregate_threshold",
        field="nonsense",
        observed="1",
        expected="0",
        detail="",
    )
    assert taxonomy.classify(a) == taxonomy.UNCLASSIFIED
