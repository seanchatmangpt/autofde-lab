"""Chicago-style zero-mock unit tests for the Service selector mismatch fault mechanism.

Source mechanism: sregym/generators/fault/inject_virtual.py
VirtualizationFaultInjector.inject_wrong_service_selector() -- adds an extra
selector key ("current_service_name": <service>) to a live Service that no
Pod's labels carry, so the Service's Endpoints go to zero addresses.

Strict zero-mock policy: NO unittest.mock, NO Mock, NO MagicMock, NO patch,
NO monkeypatch. All tests exercise pure functions with real Python data
structures shaped like real `kubectl get ... -o json` output.
"""

from __future__ import annotations

from autofde_lab_planner.detectors.service_selector_mismatch import detect_service_selector_mismatches
from autofde_lab_planner.engine import CompositePlannerEngine
from autofde_lab_planner.models import ServiceSelectorMismatchFault
from autofde_lab_planner.remediators.service_selector_mismatch import decide_service_selector_remediation_commands


def _deployment(name: str, namespace: str, labels: dict[str, str]) -> dict:
    return {
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "replicas": 2,
            "template": {"metadata": {"labels": labels}},
        },
        "status": {"readyReplicas": 2},
    }


def test_detects_extra_selector_key_not_present_in_pod_labels():
    services = {
        "items": [
            {
                "metadata": {"name": "geo", "namespace": "hotel-reservation"},
                "spec": {
                    "selector": {"app": "geo", "current_service_name": "geo"},
                },
            }
        ]
    }
    deployments = {
        "items": [
            _deployment("geo", "hotel-reservation", {"app": "geo"}),
        ]
    }

    faults = detect_service_selector_mismatches(
        services_json=services,
        deployments_json=deployments,
        namespace="hotel-reservation",
    )

    assert len(faults) == 1
    f = faults[0]
    assert isinstance(f, ServiceSelectorMismatchFault)
    assert f.service_name == "geo"
    assert f.deployment_name == "geo"
    assert f.mismatched_keys == ("current_service_name",)
    assert f.original_selector == {"app": "geo"}


def test_no_fault_when_selector_matches_pod_labels_exactly():
    services = {
        "items": [
            {
                "metadata": {"name": "rate", "namespace": "hotel-reservation"},
                "spec": {"selector": {"app": "rate"}},
            }
        ]
    }
    deployments = {
        "items": [
            _deployment("rate", "hotel-reservation", {"app": "rate"}),
        ]
    }

    faults = detect_service_selector_mismatches(
        services_json=services,
        deployments_json=deployments,
        namespace="hotel-reservation",
    )

    assert faults == []


def test_no_fault_when_no_corresponding_deployment_observed():
    """Absence of a corresponding Deployment must not be coerced into a
    mismatch -- the selector's ground truth is unknown, not violated."""
    services = {
        "items": [
            {
                "metadata": {"name": "orphan-svc", "namespace": "default"},
                "spec": {"selector": {"app": "orphan-svc", "extra": "x"}},
            }
        ]
    }

    faults = detect_service_selector_mismatches(
        services_json=services,
        deployments_json={"items": []},
        namespace="default",
    )

    assert faults == []


def test_detects_wrong_value_for_existing_key_not_just_extra_keys():
    services = {
        "items": [
            {
                "metadata": {"name": "profile", "namespace": "hotel-reservation"},
                "spec": {"selector": {"app": "wrong-value"}},
            }
        ]
    }
    deployments = {
        "items": [
            _deployment("profile", "hotel-reservation", {"app": "profile"}),
        ]
    }

    faults = detect_service_selector_mismatches(
        services_json=services,
        deployments_json=deployments,
        namespace="hotel-reservation",
    )

    assert len(faults) == 1
    assert faults[0].mismatched_keys == ("app",)


def test_remediation_emits_json_patch_removing_mismatched_key():
    fault = ServiceSelectorMismatchFault(
        service_name="geo",
        namespace="hotel-reservation",
        deployment_name="geo",
        mismatched_keys=("current_service_name",),
        original_selector={"app": "geo"},
    )

    commands, deployments = decide_service_selector_remediation_commands(
        faults=[fault], namespace="hotel-reservation"
    )

    assert len(commands) == 1
    assert commands[0] == (
        "kubectl patch service geo -n hotel-reservation --type=json "
        '-p=\'[{"op": "remove", "path": "/spec/selector/current_service_name"}]\''
    )
    assert deployments == ["geo"]


def test_remediation_escapes_slash_and_tilde_in_selector_keys_per_rfc6902():
    fault = ServiceSelectorMismatchFault(
        service_name="svc",
        namespace="default",
        deployment_name="svc",
        mismatched_keys=("weird/key~name",),
        original_selector={"app": "svc"},
    )

    commands, _ = decide_service_selector_remediation_commands(faults=[fault], namespace="default")

    assert len(commands) == 1
    assert "/spec/selector/weird~1key~0name" in commands[0]


def test_engine_wires_service_selector_mismatch_detection_and_remediation():
    engine = CompositePlannerEngine(namespace="hotel-reservation")

    deployments = {
        "items": [
            _deployment("geo", "hotel-reservation", {"app": "geo"}),
        ]
    }
    services = {
        "items": [
            {
                "metadata": {"name": "geo", "namespace": "hotel-reservation"},
                "spec": {"selector": {"app": "geo", "current_service_name": "geo"}},
            }
        ]
    }

    diagnosis = engine.run_diagnosis(
        deployments_json=deployments,
        services_json=services,
    )

    assert len(diagnosis.service_selector_mismatches) == 1
    assert "geo" in diagnosis.diagnosis_text

    mitigation = engine.run_mitigation(diagnosis)
    assert any("remove" in c and "selector/current_service_name" in c for c in mitigation.commands)
