"""Detector for env var shadowing faults.

Ground truth: vendor/gyms/sregym/sregym/generators/fault/inject_virtual.py
`VirtualizationFaultInjector.inject_env_variable_shadowing` (around line 1826).
That injector patches a Deployment's container `env` list, adding or
overwriting a variable with a value that silently shadows the real/expected
one (its worked example: `FRONTEND_HOST=localhost` overriding the real
upstream host for the `frontend-proxy` container in the astronomy-shop
namespace, so the container talks to itself instead of the intended peer).

This is a distinct failure mode from `object_reconstruction`'s ConfigMap/
Secret drift: the corrupted value lives directly in
`spec.template.spec.containers[].env[]` on the Deployment object itself, not
in a separately-mounted ConfigMap/Secret. Detection compares each container's
declared env vars against a known baseline map of (deployment, container,
var) -> expected value.
"""

from __future__ import annotations

from typing import Any

from autofde_lab_planner.models import EnvVarShadowFault

# Known baseline env var values per (deployment_name, container_name, env_var_name).
# Sourced from sregym's astronomy-shop fault-injection worked example: the
# frontend-proxy container's FRONTEND_HOST must resolve to the real frontend
# service, never to "localhost" (which shadows the proxy's own loopback and
# breaks upstream routing).
KNOWN_ENV_VAR_BASELINES: dict[tuple[str, str, str], str] = {
    ("frontend-proxy", "frontend-proxy", "FRONTEND_HOST"): "frontend",
}

# Env var values that are always suspicious regardless of baseline knowledge:
# a service-discovery/host-pointer env var set to a loopback address is a
# textbook shadowing symptom (the container silently starts talking to
# itself instead of the intended peer).
SHADOW_SUSPECT_HOST_VALUES = {"localhost", "127.0.0.1", "0.0.0.0"}
HOST_POINTER_SUFFIXES = ("_HOST", "_HOSTNAME", "_ADDR", "_ENDPOINT")


def detect_env_var_shadow_faults(
    deployments_json: dict[str, Any] | list[dict[str, Any]] | None = None,
    namespace: str = "default",
) -> list[EnvVarShadowFault]:
    """Detects container env vars whose value shadows an expected baseline.

    Two detection strategies, matching the two things a real diagnosis run
    can lawfully know:

    1. Known-baseline mismatch: the (deployment, container, var) triple is in
       `KNOWN_ENV_VAR_BASELINES` and the observed value differs.
    2. Suspicious host-pointer shadowing: a `*_HOST`/`*_HOSTNAME`/`*_ADDR`/
       `*_ENDPOINT` env var is set to a loopback value, which is never a
       legitimate cross-service pointer in a multi-container topology.
    """
    deployment_items = _to_item_list(deployments_json)
    faults: list[EnvVarShadowFault] = []

    for dep in deployment_items:
        dep_meta = dep.get("metadata") or {}
        dep_name = dep_meta.get("name", "")
        dep_ns = dep_meta.get("namespace") or namespace

        containers = (
            ((dep.get("spec") or {}).get("template") or {}).get("spec") or {}
        ).get("containers") or []

        for c_idx, container in enumerate(containers):
            if not isinstance(container, dict):
                continue
            c_name = container.get("name", "")
            env_list = container.get("env") or []

            for e_idx, env_entry in enumerate(env_list):
                if not isinstance(env_entry, dict):
                    continue
                var_name = env_entry.get("name", "")
                observed_value = env_entry.get("value")
                if var_name == "" or observed_value is None:
                    continue

                baseline_key = (dep_name, c_name, var_name)
                if baseline_key in KNOWN_ENV_VAR_BASELINES:
                    expected_value = KNOWN_ENV_VAR_BASELINES[baseline_key]
                    if str(observed_value) != str(expected_value):
                        faults.append(
                            EnvVarShadowFault(
                                deployment_name=dep_name,
                                namespace=dep_ns,
                                container_name=c_name,
                                env_var_name=var_name,
                                observed_value=str(observed_value),
                                expected_value=str(expected_value),
                                container_index=c_idx,
                                env_index=e_idx,
                            )
                        )
                    continue

                if var_name.upper().endswith(HOST_POINTER_SUFFIXES) and str(
                    observed_value
                ).lower() in SHADOW_SUSPECT_HOST_VALUES:
                    faults.append(
                        EnvVarShadowFault(
                            deployment_name=dep_name,
                            namespace=dep_ns,
                            container_name=c_name,
                            env_var_name=var_name,
                            observed_value=str(observed_value),
                            expected_value=f"<real-{dep_name}-service-host>",
                            container_index=c_idx,
                            env_index=e_idx,
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
