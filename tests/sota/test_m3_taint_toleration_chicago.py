"""Chicago-style zero-mock unit tests for the taint/toleration scheduling fault mechanism.

Source mechanism: sregym/generators/fault/inject_virtual.py
VirtualizationFaultInjector.inject_toleration_without_matching_taint() -- taints
a node (default sre-fault=blocked:NoSchedule) and deletes the target
workload's Pods, so replacement Pods land Pending with a FailedScheduling
event carrying the scheduler's "had untolerated taint {key: value}" message.

Strict zero-mock policy: NO unittest.mock, NO Mock, NO MagicMock, NO patch,
NO monkeypatch. All tests exercise pure functions with real Python data
structures shaped like real `kubectl get ... -o json` output.
"""

from __future__ import annotations

from autofde_lab_planner.detectors.taint_toleration import detect_taint_toleration_faults
from autofde_lab_planner.engine import CompositePlannerEngine
from autofde_lab_planner.models import TaintTolerationFault
from autofde_lab_planner.remediators.taint_toleration import decide_taint_toleration_remediation_commands


def _deployment(name: str, namespace: str, replicas: int = 2, ready: int = 0) -> dict:
    return {
        "metadata": {"name": name, "namespace": namespace},
        "spec": {"replicas": replicas, "template": {"metadata": {"labels": {"app": name}}}},
        "status": {"readyReplicas": ready},
    }


def _pending_pod(name: str, namespace: str, app: str) -> dict:
    return {
        "metadata": {"name": name, "namespace": namespace, "labels": {"app": app}},
        "status": {"phase": "Pending"},
    }


def _failed_scheduling_event(pod_name: str, namespace: str, taint_key: str, taint_value: str) -> dict:
    return {
        "reason": "FailedScheduling",
        "message": (
            f"0/3 nodes are available: 1 node(s) had untolerated taint {{{taint_key}: {taint_value}}}, "
            "2 node(s) didn't match Pod's node affinity/selector."
        ),
        "involvedObject": {"kind": "Pod", "name": pod_name, "namespace": namespace},
    }


def _node(name: str, taint_key: str, taint_value: str, effect: str = "NoSchedule") -> dict:
    return {
        "metadata": {"name": name},
        "spec": {"taints": [{"key": taint_key, "value": taint_value, "effect": effect}]},
    }


def test_detects_untolerated_taint_blocking_pending_deployment():
    deployments = {"items": [_deployment("cart", "boutique", replicas=2, ready=0)]}
    pods = {"items": [_pending_pod("cart-7f8-abcde", "boutique", "cart")]}
    events = {"items": [_failed_scheduling_event("cart-7f8-abcde", "boutique", "sre-fault", "blocked")]}
    nodes = {"items": [_node("node1", "sre-fault", "blocked", "NoSchedule")]}

    faults = detect_taint_toleration_faults(
        deployments_json=deployments,
        pods_json=pods,
        events_json=events,
        nodes_json=nodes,
        namespace="boutique",
    )

    assert len(faults) == 1
    f = faults[0]
    assert isinstance(f, TaintTolerationFault)
    assert f.deployment_name == "cart"
    assert f.node_name == "node1"
    assert f.taint_key == "sre-fault"
    assert f.taint_value == "blocked"
    assert f.taint_effect == "NoSchedule"
    assert f.unready_replicas >= 1
    assert f.desired_replicas == 2


def test_no_fault_without_failed_scheduling_evidence():
    """A Pending pod alone (e.g. still being scheduled normally) is not
    evidence of an untolerated taint -- absence of the specific scheduler
    signal must not be coerced into this fault."""
    deployments = {"items": [_deployment("cart", "boutique", replicas=2, ready=0)]}
    pods = {"items": [_pending_pod("cart-7f8-abcde", "boutique", "cart")]}

    faults = detect_taint_toleration_faults(
        deployments_json=deployments,
        pods_json=pods,
        events_json={"items": []},
        namespace="boutique",
    )

    assert faults == []


def test_no_fault_when_deployment_is_fully_ready_despite_stale_event():
    deployments = {"items": [_deployment("cart", "boutique", replicas=2, ready=2)]}
    events = {"items": [_failed_scheduling_event("cart-7f8-abcde", "boutique", "sre-fault", "blocked")]}

    faults = detect_taint_toleration_faults(
        deployments_json=deployments,
        pods_json={"items": []},
        events_json=events,
        namespace="boutique",
    )

    assert faults == []


def test_node_name_left_empty_when_no_node_evidence_supplied():
    """Without live Node data the exact node cannot be established; the
    detector must not fabricate a node identity from the event alone."""
    deployments = {"items": [_deployment("cart", "boutique", replicas=1, ready=0)]}
    pods = {"items": [_pending_pod("cart-7f8-abcde", "boutique", "cart")]}
    events = {"items": [_failed_scheduling_event("cart-7f8-abcde", "boutique", "sre-fault", "blocked")]}

    faults = detect_taint_toleration_faults(
        deployments_json=deployments,
        pods_json=pods,
        events_json=events,
        namespace="boutique",
    )

    assert len(faults) == 1
    assert faults[0].node_name == ""
    assert faults[0].taint_effect == "NoSchedule"


def test_remediation_emits_toleration_patch_and_rollout_restart():
    fault = TaintTolerationFault(
        deployment_name="cart",
        namespace="boutique",
        node_name="node1",
        taint_key="sre-fault",
        taint_value="blocked",
        taint_effect="NoSchedule",
        unready_replicas=2,
        desired_replicas=2,
    )

    commands, deployments = decide_taint_toleration_remediation_commands(faults=[fault], namespace="boutique")

    assert len(commands) == 2
    assert commands[0] == (
        "kubectl patch deployment cart -n boutique --type=json "
        '-p=\'[{"op": "add", "path": "/spec/template/spec/tolerations", '
        '"value": [{"key": "sre-fault", "operator": "Equal", "value": "blocked", "effect": "NoSchedule"}]}]\''
    )
    assert commands[1] == "kubectl rollout restart deployment/cart -n boutique"
    assert deployments == ["cart"]


def test_engine_wires_taint_toleration_detection_and_remediation():
    engine = CompositePlannerEngine(namespace="boutique")

    deployments = {"items": [_deployment("cart", "boutique", replicas=1, ready=0)]}
    pods = {"items": [_pending_pod("cart-7f8-abcde", "boutique", "cart")]}
    events = {"items": [_failed_scheduling_event("cart-7f8-abcde", "boutique", "sre-fault", "blocked")]}
    nodes = {"items": [_node("node1", "sre-fault", "blocked", "NoSchedule")]}

    diagnosis = engine.run_diagnosis(
        deployments_json=deployments,
        pods_json=pods,
        events_json=events,
        nodes_json=nodes,
    )

    assert len(diagnosis.taint_toleration_faults) == 1
    assert "sre-fault" in diagnosis.diagnosis_text

    mitigation = engine.run_mitigation(diagnosis)
    assert any("tolerations" in c for c in mitigation.commands)
    assert any("rollout restart deployment/cart" in c for c in mitigation.commands)
