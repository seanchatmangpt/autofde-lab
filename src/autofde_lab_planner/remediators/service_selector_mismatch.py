"""Remediator for Service selector mismatch faults."""

from __future__ import annotations

from autofde_lab_planner.models import ServiceSelectorMismatchFault


def decide_service_selector_remediation_commands(
    faults: list[ServiceSelectorMismatchFault],
    namespace: str = "default",
) -> tuple[list[str], list[str]]:
    """Generates kubectl patch commands that remove the extraneous selector
    key(s) from each affected Service, restoring it to only the keys that
    actually match the backing Deployment's Pod-template labels.

    No rollout wait is required -- Endpoints reconciliation for a Service
    selector patch is near-instant and does not restart any Pods -- so the
    affected Deployment names are still returned for downstream visibility
    but callers are not required to block on a rollout for them.
    """
    commands: list[str] = []
    affected_deployments: list[str] = []

    for f in faults:
        ns = f.namespace or namespace
        for key in f.mismatched_keys:
            escaped_key = key.replace("~", "~0").replace("/", "~1")
            cmd = (
                f"kubectl patch service {f.service_name} -n {ns} --type=json "
                f'-p=\'[{{"op": "remove", "path": "/spec/selector/{escaped_key}"}}]\''
            )
            commands.append(cmd)

        if f.deployment_name not in affected_deployments:
            affected_deployments.append(f.deployment_name)

    return commands, affected_deployments
