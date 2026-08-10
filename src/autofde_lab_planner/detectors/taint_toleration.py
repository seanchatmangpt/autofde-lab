"""Detector for taint/toleration scheduling faults.

Source mechanism (fault-injector evidence):
sregym/generators/fault/inject_virtual.py,
VirtualizationFaultInjector.inject_toleration_without_matching_taint()
(around line 2101):

    self.kubectl.exec_command(
        f"kubectl taint node {node_name} {taint_key}={taint_value}:{effect} --overwrite"
    )
    for svc in microservices:
        self.kubectl.exec_command(f"kubectl delete pod -l app={svc} -n {self.namespace}")

This taints a live node (default key/value/effect
``sre-fault=blocked:NoSchedule``) and deletes the target workload's Pods, so
the ReplicaSet reschedules replacement Pods onto a cluster that now includes
a tainted node the Pod spec carries no matching toleration for. The
observable symptom is Pods stuck ``Pending`` with a ``FailedScheduling``
event whose message includes the standard kubernetes scheduler phrase
``had untolerated taint``.

No existing detector inspects node taints or Pod tolerations at all
(confirmed via ``grep -l toleration src/autofde_lab_planner/detectors/*.py``
-> zero matches). This is distinct from scheduling_deadlock.py, which only
covers podAntiAffinity and nodeSelector constraints -- neither of which is
present in this fault's Pod spec.
"""

from __future__ import annotations

import re
from typing import Any

from autofde_lab_planner.models import TaintTolerationFault

_UNTOLERATED_TAINT_RE = re.compile(
    r"had untolerated taint\s*\{\s*([^:}]+?)\s*:\s*([^}]*?)\s*\}"
)


def detect_taint_toleration_faults(
    deployments_json: dict[str, Any] | list[dict[str, Any]] | None = None,
    pods_json: dict[str, Any] | list[dict[str, Any]] | None = None,
    events_json: dict[str, Any] | list[dict[str, Any]] | None = None,
    nodes_json: dict[str, Any] | list[dict[str, Any]] | None = None,
    namespace: str = "default",
) -> list[TaintTolerationFault]:
    """Detects Deployments whose Pods are Pending because of a node taint no
    Pod toleration matches, evidenced by a ``FailedScheduling`` event
    carrying the scheduler's ``had untolerated taint {key: value}`` message.
    """
    dep_items = _to_item_list(deployments_json)
    pod_items = _to_item_list(pods_json)
    event_items = _to_item_list(events_json)
    node_items = _to_item_list(nodes_json)

    # Map pending-pod-count and Pending status per deployment name (matched
    # by "app"/"io.kompose.service" label, same convention as the pod-owner
    # heuristic already used in scheduling_deadlock.py).
    pending_by_dep: dict[str, int] = {}
    for pod in pod_items:
        labels = (pod.get("metadata") or {}).get("labels") or {}
        dep_name = labels.get("app") or labels.get("io.kompose.service") or ""
        phase = (pod.get("status") or {}).get("phase", "")
        if dep_name and phase == "Pending":
            pending_by_dep[dep_name] = pending_by_dep.get(dep_name, 0) + 1

    dep_names = {(dep.get("metadata") or {}).get("name", "") for dep in dep_items}
    dep_names.discard("")

    # Extract (dep_name -> (taint_key, taint_value)) from FailedScheduling events.
    taint_by_dep: dict[str, tuple[str, str]] = {}
    for ev in event_items:
        reason = ev.get("reason", "")
        msg = ev.get("message") or ""
        if reason != "FailedScheduling":
            continue
        match = _UNTOLERATED_TAINT_RE.search(msg)
        if not match:
            continue
        taint_key, taint_value = match.group(1).strip(), match.group(2).strip()

        obj_name = (ev.get("involvedObject") or {}).get("name", "")
        for dep_name in dep_names:
            if dep_name and obj_name.startswith(dep_name):
                taint_by_dep[dep_name] = (taint_key, taint_value)

    if not taint_by_dep:
        return []

    # Resolve effect and a concrete node name for each observed taint by
    # cross-referencing live Node objects; fall back to the fault injector's
    # own documented default (NoSchedule) with no node name if Node data
    # wasn't supplied -- absence of node evidence must not be coerced into a
    # fabricated node identity.
    node_taint_index: dict[tuple[str, str], tuple[str, str]] = {}
    for node in node_items:
        node_name = (node.get("metadata") or {}).get("name", "")
        for taint in (node.get("spec") or {}).get("taints") or []:
            key = taint.get("key", "")
            value = taint.get("value", "")
            effect = taint.get("effect", "NoSchedule")
            if key:
                node_taint_index[(key, value)] = (node_name, effect)

    faults: list[TaintTolerationFault] = []
    for dep in dep_items:
        dep_meta = dep.get("metadata") or {}
        dep_name = dep_meta.get("name", "")
        dep_ns = dep_meta.get("namespace") or namespace

        if dep_name not in taint_by_dep:
            continue

        spec_rep = (dep.get("spec") or {}).get("replicas", 1)
        ready_rep = (dep.get("status") or {}).get("readyReplicas", 0)
        is_unready = spec_rep > ready_rep or pending_by_dep.get(dep_name, 0) > 0
        if not is_unready:
            continue

        taint_key, taint_value = taint_by_dep[dep_name]
        node_name, effect = node_taint_index.get((taint_key, taint_value), ("", "NoSchedule"))

        faults.append(
            TaintTolerationFault(
                deployment_name=dep_name,
                namespace=dep_ns,
                node_name=node_name,
                taint_key=taint_key,
                taint_value=taint_value,
                taint_effect=effect,
                unready_replicas=max(spec_rep - ready_rep, pending_by_dep.get(dep_name, 0)),
                desired_replicas=spec_rep,
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
