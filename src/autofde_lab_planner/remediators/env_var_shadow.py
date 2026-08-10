"""Remediator for env var shadowing faults.

Generates `kubectl patch` JSON-patch commands against the Deployment's
`spec.template.spec.containers[].env[]` path. When the real expected value is
known (baseline match) the patch replaces the shadowed value in place. When
only a suspicious host-pointer shadow was detected (no known baseline value),
the patch removes the injected env entry entirely, restoring the container to
whatever default/inherited value it had before the fault was injected -- the
safe action when the correct real value cannot be independently confirmed.
"""

from __future__ import annotations

from autofde_lab_planner.models import EnvVarShadowFault

_UNKNOWN_BASELINE_PREFIX = "<real-"


def decide_env_var_shadow_remediation_commands(
    faults: list[EnvVarShadowFault],
    namespace: str = "default",
) -> tuple[list[str], list[str]]:
    """Generates kubectl patch commands for env var shadowing faults.

    Returns (commands, deployments_to_restart).
    """
    commands: list[str] = []
    deployments_to_restart: list[str] = []

    for f in faults:
        ns = f.namespace or namespace
        c_idx = f.container_index
        e_idx = f.env_index

        if f.expected_value.startswith(_UNKNOWN_BASELINE_PREFIX):
            # No confirmed real baseline value -- remove the injected shadow
            # entry rather than guess a replacement value.
            patch_cmd = (
                f"kubectl patch deployment {f.deployment_name} -n {ns} --type=json "
                f'-p=\'[{{"op": "remove", '
                f'"path": "/spec/template/spec/containers/{c_idx}/env/{e_idx}"}}]\''
            )
        else:
            patch_cmd = (
                f"kubectl patch deployment {f.deployment_name} -n {ns} --type=json "
                f'-p=\'[{{"op": "replace", '
                f'"path": "/spec/template/spec/containers/{c_idx}/env/{e_idx}/value", '
                f'"value": "{f.expected_value}"}}]\''
            )

        commands.append(patch_cmd)

        if f.deployment_name not in deployments_to_restart:
            deployments_to_restart.append(f.deployment_name)

    return commands, deployments_to_restart
