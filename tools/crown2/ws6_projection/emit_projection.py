#!/usr/bin/env python3
"""
emit_projection.py — WS6 demo + OCEL emission.

Runs the before/after story end to end against the real evidence plane:

  1. empty graph -> project domain (before)          -> DomainProjected #1
  2. add_qualified(one capability)  (NEW graph)      -> CapabilityGraph object
  3. project domain again (after)                    -> DomainProjected #2
  4. print the digest delta, validate the OCEL log (exit 1 if not green)

CLI:
    python3 emit_projection.py <out_dir>

Writes <out_dir>/ws6.ocel.json, <out_dir>/graphs/<sha256>.json (content-
addressed graph store) and <out_dir>/delta.json; prints delta.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OCEL_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "ocel_v2"))
sys.path.insert(0, HERE)
sys.path.insert(0, OCEL_DIR)

import emitter  # noqa: E402  (tools/ocel_v2/emitter.py)
from capability_graph import (  # noqa: E402
    QualifiedCapabilityReceipt,
    add_qualified,
    empty_graph,
    graph_digest,
    project_domain,
    save_graph,
)

WORLD_STATE = {"label": "lab", "facts": ["repo_clean", "tests_green"]}
AUTHORITY = {"decision": "granted", "scopes": ["git:commit"]}
RECEIPT = QualifiedCapabilityReceipt(
    capability_id="cap.git.commit.v1",
    action="git_commit",
    qualification_run_id="qr-ws6-0001",
    evidence_digest="sha256:0000000000000000000000000000000000000000000000000000000000000000",
    preconditions=("repo_clean", "tests_green"),
    effects=("commit_created",),
    scopes=("git:commit",),
)


def _emit_projection(log_path: str, n: int, graph: dict, domain: dict, graph_obj_id: str) -> None:
    emitter.add_event(
        log_path,
        "DomainProjected",
        f"ev-ws6-projected-{n}",
        {
            "graph_digest": domain["graph_digest"],
            "domain_digest": domain["digest"],
            "action_count": len(domain["actions"]),
            "actions_json": domain["actions"],
        },
        [graph_obj_id, "ws-ws6-lab", "ad-ws6-granted", "domain-ws6"],
    )


def run(out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "ws6.ocel.json")
    store = os.path.join(out_dir, "graphs")
    emitter.init(log_path)

    emitter.add_object(log_path, "WorldState", "ws-ws6-lab",
                       {"label": WORLD_STATE["label"], "observed_at": emitter._now_iso(),
                        "state_json": WORLD_STATE})
    emitter.add_object(log_path, "AuthorityDecision", "ad-ws6-granted",
                       {"decision": AUTHORITY["decision"], "rationale": "lab authority",
                        "decided_at": emitter._now_iso()})
    emitter.add_object(log_path, "Domain", "domain-ws6",
                       {"name": "ws6-lab-domain", "description": "projected from capability graph"})

    # --- before ---
    g0 = empty_graph()
    d0 = graph_digest(g0)
    p0 = save_graph(store, g0)
    emitter.add_object(log_path, "CapabilityGraph", "cg-" + d0.split(":")[1][:12],
                       {"digest": d0, "capability_ids": ""})
    dom0 = project_domain(g0, WORLD_STATE, AUTHORITY)
    _emit_projection(log_path, 1, g0, dom0, "cg-" + d0.split(":")[1][:12])

    # --- add one qualified capability (pure; g0 untouched) ---
    g1, d1 = add_qualified(g0, RECEIPT)
    assert graph_digest(g0) == d0, "add_qualified mutated its input"
    p1 = save_graph(store, g1)
    emitter.add_object(log_path, "CapabilityGraph", "cg-" + d1.split(":")[1][:12],
                       {"digest": d1, "capability_ids": ",".join(sorted(g1["capabilities"]))})

    # --- after ---
    dom1 = project_domain(g1, WORLD_STATE, AUTHORITY)
    _emit_projection(log_path, 2, g1, dom1, "cg-" + d1.split(":")[1][:12])

    validate = subprocess.run(
        [sys.executable, os.path.join(OCEL_DIR, "validate.py"), log_path],
        capture_output=True, text=True, check=False,
    )
    delta = {
        "before": {"graph_digest": d0, "graph_path": p0,
                   "domain_digest": dom0["digest"], "actions": dom0["actions"]},
        "after": {"graph_digest": d1, "graph_path": p1,
                  "domain_digest": dom1["digest"], "actions": dom1["actions"]},
        "added_capability": RECEIPT.capability_id,
        "graph_digest_changed": d0 != d1,
        "domain_digest_changed": dom0["digest"] != dom1["digest"],
        "ocel_log": log_path,
        "validate_stdout": validate.stdout.strip(),
        "validate_exit": validate.returncode,
    }
    with open(os.path.join(out_dir, "delta.json"), "w", encoding="utf-8") as f:
        json.dump(delta, f, indent=2, sort_keys=True)
        f.write("\n")
    return delta


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: emit_projection.py <out_dir>", file=sys.stderr)
        return 2
    delta = run(argv[1])
    print(json.dumps(delta, indent=2, sort_keys=True))
    return 0 if delta["validate_exit"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
