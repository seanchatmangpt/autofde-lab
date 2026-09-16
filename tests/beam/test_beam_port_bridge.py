"""Chicago tests for AutoFDE-Lab BEAM stdio port bridge."""

import json
import subprocess
import sys


def test_beam_port_bridge_ping_and_allocate() -> None:
    bridge_script = "src/autofde_lab/beam/beam_port_bridge.py"
    proc = subprocess.Popen(
        [sys.executable, bridge_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # 1. Ping
        req_ping = {"op": "ping"}
        proc.stdin.write(json.dumps(req_ping) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        resp_ping = json.loads(line)
        assert resp_ping.get("ok") is True
        assert resp_ping.get("pong") is True

        # 2. CMCA Allocate
        req_alloc = {
            "op": "cmca_allocate",
            "plan_id": "beam_test_plan",
            "budget": {
                "total_ticks": 5000,
                "memory_bytes": 65536,
                "max_verification_depth": 5,
                "consequence_risk_budget": 0.5,
                "concurrency_lanes": 4,
            },
            "candidates": [
                {
                    "branch_id": "branch_alpha",
                    "option_entropy": 2.5,
                    "historical_yield": 0.9,
                    "estimated_cost": 10.0,
                },
                {
                    "branch_id": "branch_beta",
                    "option_entropy": 1.2,
                    "historical_yield": 0.4,
                    "estimated_cost": 20.0,
                },
            ],
        }
        proc.stdin.write(json.dumps(req_alloc) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        resp_alloc = json.loads(line)
        assert resp_alloc.get("ok") is True
        plan = resp_alloc.get("plan")
        assert plan["plan_id"] == "beam_test_plan"
        assert len(plan["allocations"]) == 2
        top_alloc = next(
            a for a in plan["allocations"] if a["branch_id"] == "branch_alpha"
        )
        assert top_alloc["allocated_fraction"] > 0.5
        assert top_alloc["standing"] == "ADMITTED"

    finally:
        proc.terminate()
        proc.wait(timeout=2)
