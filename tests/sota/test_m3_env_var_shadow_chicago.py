"""Chicago-style zero-mock unit and integration tests for the env var shadowing
fault mechanism.

Ground truth: vendor/gyms/sregym/sregym/generators/fault/inject_virtual.py
`VirtualizationFaultInjector.inject_env_variable_shadowing` (~line 1826): a
container env var (worked example: `FRONTEND_HOST=localhost` on the
`frontend-proxy` container in the astronomy-shop namespace) is patched into
the Deployment's `spec.template.spec.containers[].env[]` to silently shadow
the real/expected value.

Strict zero-mock policy: NO unittest.mock, NO Mock, NO MagicMock, NO patch,
NO monkeypatch. All tests exercise pure functions against real Python dict
structures shaped exactly like `kubectl get deployment -o json` output and
assert on real returned dataclass state / real generated kubectl command
strings.
"""

from __future__ import annotations

from autofde_lab_planner.detectors.env_var_shadow import detect_env_var_shadow_faults
from autofde_lab_planner.engine import CompositePlannerEngine
from autofde_lab_planner.models import EnvVarShadowFault
from autofde_lab_planner.remediators.env_var_shadow import (
    decide_env_var_shadow_remediation_commands,
)


def _deployment(name: str, namespace: str, container_name: str, env: list[dict]) -> dict:
    return {
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": container_name,
                            "env": env,
                        }
                    ]
                }
            }
        },
    }


# =============================================================================
# Detector: known-baseline shadowing (sregym's own worked example)
# =============================================================================

def test_detects_known_baseline_env_var_shadow():
    deployments = {
        "items": [
            _deployment(
                "frontend-proxy",
                "astronomy-shop",
                "frontend-proxy",
                env=[{"name": "FRONTEND_HOST", "value": "localhost"}],
            )
        ]
    }

    faults = detect_env_var_shadow_faults(deployments_json=deployments, namespace="astronomy-shop")

    assert len(faults) == 1
    fault = faults[0]
    assert isinstance(fault, EnvVarShadowFault)
    assert fault.deployment_name == "frontend-proxy"
    assert fault.namespace == "astronomy-shop"
    assert fault.container_name == "frontend-proxy"
    assert fault.env_var_name == "FRONTEND_HOST"
    assert fault.observed_value == "localhost"
    assert fault.expected_value == "frontend"
    assert fault.container_index == 0
    assert fault.env_index == 0


def test_no_fault_when_env_var_matches_baseline():
    deployments = {
        "items": [
            _deployment(
                "frontend-proxy",
                "astronomy-shop",
                "frontend-proxy",
                env=[{"name": "FRONTEND_HOST", "value": "frontend"}],
            )
        ]
    }

    faults = detect_env_var_shadow_faults(deployments_json=deployments, namespace="astronomy-shop")

    assert faults == []


# =============================================================================
# Detector: suspicious host-pointer shadowing (no known baseline, generic rule)
# =============================================================================

def test_detects_suspicious_loopback_host_pointer_shadow():
    deployments = {
        "items": [
            _deployment(
                "checkout-service",
                "hotel-reservation",
                "checkout",
                env=[
                    {"name": "PAYMENT_SERVICE_HOST", "value": "127.0.0.1"},
                    {"name": "LOG_LEVEL", "value": "info"},
                ],
            )
        ]
    }

    faults = detect_env_var_shadow_faults(deployments_json=deployments, namespace="hotel-reservation")

    assert len(faults) == 1
    fault = faults[0]
    assert fault.env_var_name == "PAYMENT_SERVICE_HOST"
    assert fault.observed_value == "127.0.0.1"
    assert fault.expected_value.startswith("<real-")
    assert fault.env_index == 0


def test_no_fault_for_legitimate_env_vars():
    deployments = {
        "items": [
            _deployment(
                "checkout-service",
                "hotel-reservation",
                "checkout",
                env=[
                    {"name": "PAYMENT_SERVICE_HOST", "value": "payment.hotel-reservation.svc.cluster.local"},
                    {"name": "LOG_LEVEL", "value": "info"},
                ],
            )
        ]
    }

    faults = detect_env_var_shadow_faults(deployments_json=deployments, namespace="hotel-reservation")

    assert faults == []


def test_handles_empty_and_missing_env_gracefully():
    deployments = {
        "items": [
            {
                "metadata": {"name": "no-env-svc", "namespace": "default"},
                "spec": {"template": {"spec": {"containers": [{"name": "app"}]}}},
            }
        ]
    }

    assert detect_env_var_shadow_faults(deployments_json=deployments, namespace="default") == []
    assert detect_env_var_shadow_faults(deployments_json=None, namespace="default") == []
    assert detect_env_var_shadow_faults(deployments_json={}, namespace="default") == []


# =============================================================================
# Remediator: known-baseline -> replace value; suspicious -> remove entry
# =============================================================================

def test_remediation_generates_replace_patch_for_known_baseline():
    fault = EnvVarShadowFault(
        deployment_name="frontend-proxy",
        namespace="astronomy-shop",
        container_name="frontend-proxy",
        env_var_name="FRONTEND_HOST",
        observed_value="localhost",
        expected_value="frontend",
        container_index=0,
        env_index=0,
    )

    commands, deployments_to_restart = decide_env_var_shadow_remediation_commands(
        [fault], namespace="astronomy-shop"
    )

    assert len(commands) == 1
    cmd = commands[0]
    assert "kubectl patch deployment frontend-proxy -n astronomy-shop --type=json" in cmd
    assert '"op": "replace"' in cmd
    assert '"path": "/spec/template/spec/containers/0/env/0/value"' in cmd
    assert '"value": "frontend"' in cmd
    assert deployments_to_restart == ["frontend-proxy"]


def test_remediation_generates_remove_patch_for_unknown_baseline():
    fault = EnvVarShadowFault(
        deployment_name="checkout-service",
        namespace="hotel-reservation",
        container_name="checkout",
        env_var_name="PAYMENT_SERVICE_HOST",
        observed_value="127.0.0.1",
        expected_value="<real-checkout-service-service-host>",
        container_index=0,
        env_index=0,
    )

    commands, deployments_to_restart = decide_env_var_shadow_remediation_commands(
        [fault], namespace="hotel-reservation"
    )

    assert len(commands) == 1
    cmd = commands[0]
    assert "kubectl patch deployment checkout-service -n hotel-reservation --type=json" in cmd
    assert '"op": "remove"' in cmd
    assert '"path": "/spec/template/spec/containers/0/env/0"' in cmd
    assert deployments_to_restart == ["checkout-service"]


def test_remediation_deduplicates_restart_targets_across_multiple_faults():
    faults = [
        EnvVarShadowFault(
            deployment_name="svc-a",
            namespace="ns",
            container_name="c1",
            env_var_name="VAR_HOST",
            observed_value="localhost",
            expected_value="real-host",
            container_index=0,
            env_index=0,
        ),
        EnvVarShadowFault(
            deployment_name="svc-a",
            namespace="ns",
            container_name="c1",
            env_var_name="OTHER_HOST",
            observed_value="localhost",
            expected_value="real-host-2",
            container_index=0,
            env_index=1,
        ),
    ]

    commands, deployments_to_restart = decide_env_var_shadow_remediation_commands(faults, namespace="ns")

    assert len(commands) == 2
    assert deployments_to_restart == ["svc-a"]


# =============================================================================
# Engine integration: full diagnose -> mitigate loop via CompositePlannerEngine
# =============================================================================

def test_engine_run_diagnosis_and_mitigation_covers_env_var_shadow():
    deployments = {
        "items": [
            _deployment(
                "frontend-proxy",
                "astronomy-shop",
                "frontend-proxy",
                env=[{"name": "FRONTEND_HOST", "value": "localhost"}],
            )
        ]
    }

    engine = CompositePlannerEngine(namespace="astronomy-shop")
    diagnosis = engine.run_diagnosis(deployments_json=deployments)

    assert len(diagnosis.env_var_shadows) == 1
    assert diagnosis.env_var_shadows[0].env_var_name == "FRONTEND_HOST"
    assert "env var shadowing" in diagnosis.diagnosis_text.lower()
    assert "FRONTEND_HOST" in diagnosis.diagnosis_text

    mitigation = engine.run_mitigation(diagnosis)

    env_patch_cmds = [
        c
        for c in mitigation.commands
        if "kubectl patch deployment frontend-proxy" in c
        and '"path": "/spec/template/spec/containers/0/env/0/value"' in c
    ]
    assert len(env_patch_cmds) == 1
    assert '"value": "frontend"' in env_patch_cmds[0]
    assert "frontend-proxy" in mitigation.rollout_wait_deployments


def test_engine_run_diagnosis_no_env_var_faults_when_healthy():
    deployments = {
        "items": [
            _deployment(
                "frontend-proxy",
                "astronomy-shop",
                "frontend-proxy",
                env=[{"name": "FRONTEND_HOST", "value": "frontend"}],
            )
        ]
    }

    engine = CompositePlannerEngine(namespace="astronomy-shop")
    diagnosis = engine.run_diagnosis(deployments_json=deployments)

    assert diagnosis.env_var_shadows == ()
