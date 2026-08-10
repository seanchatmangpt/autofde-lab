"""Remediator for taint/toleration scheduling faults."""

from __future__ import annotations

import json

from autofde_lab_planner.models import TaintTolerationFault


def decide_taint_toleration_remediation_commands(
    faults: list[TaintTolerationFault],
    namespace: str = "default",
) -> tuple[list[str], list[str]]:
    """Generates kubectl patch commands that add a Pod toleration matching
    each observed node taint, so pending replacement Pods become schedulable
    again, followed by a rollout restart to force the ReplicaSet to retry
    scheduling.

    A JSON-patch ``add`` at ``/spec/template/spec/tolerations`` is used
    (rather than ``append``/``-`` array insertion) because the fault leaves
    this field absent on the affected workloads; ``add`` both creates the
    field when missing and replaces it when present, which matches the exact
    JSON-patch semantics RFC 6902 defines for that op.
    """
    commands: list[str] = []
    deployments_to_restart: list[str] = []

    for f in faults:
        ns = f.namespace or namespace
        toleration = {
            "key": f.taint_key,
            "operator": "Equal",
            "value": f.taint_value,
            "effect": f.taint_effect,
        }
        patch = json.dumps(
            [
                {
                    "op": "add",
                    "path": "/spec/template/spec/tolerations",
                    "value": [toleration],
                }
            ]
        )
        cmd = f"kubectl patch deployment {f.deployment_name} -n {ns} --type=json -p='{patch}'"
        commands.append(cmd)

        if f.deployment_name not in deployments_to_restart:
            deployments_to_restart.append(f.deployment_name)

    for dep in deployments_to_restart:
        commands.append(f"kubectl rollout restart deployment/{dep} -n {namespace}")

    return commands, deployments_to_restart
