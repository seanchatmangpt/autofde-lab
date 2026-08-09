"""Category-B13 Remediator: Missing/Corrupted Object Reconstruction."""

from __future__ import annotations

import json
from autofde_lab_planner.baselines.k8s_baselines import get_baseline_manifest
from autofde_lab_planner.models import MissingObjectFault


def decide_object_reconstruction_commands(
    faults: list[MissingObjectFault],
    namespace: str,
) -> tuple[list[str], list[str]]:
    """Generates kubectl apply and patch commands to reconstruct missing/corrupted core objects."""
    commands: list[str] = []
    deployments_to_restart: list[str] = []

    for f in faults:
        obj_name = f.object_name
        kind = f.kind
        ns = f.namespace or namespace

        if f.reason == "corrupted_service_selector":
            patch_cmd = (
                f"kubectl patch service {obj_name} -n {ns} "
                f'-p=\'{{"spec":{{"selector":{{"app":"{obj_name}"}}}}}}\''
            )
            commands.append(patch_cmd)
        else:
            manifest = get_baseline_manifest(kind=kind, object_name=obj_name, namespace=ns)
            manifest_json = json.dumps(manifest).replace("'", "'\\''")
            apply_cmd = f"echo '{manifest_json}' | kubectl apply -f -"
            commands.append(apply_cmd)

        if f.associated_deployment and f.associated_deployment not in deployments_to_restart:
            deployments_to_restart.append(f.associated_deployment)
        elif kind == "Service" and obj_name not in deployments_to_restart:
            deployments_to_restart.append(obj_name)

    for dep in deployments_to_restart:
        commands.append(f"kubectl rollout restart deployment/{dep} -n {namespace}")

    return commands, deployments_to_restart
