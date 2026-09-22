"""Chicago tests for the SA2A ops on AutoFDE-Lab's BEAM stdio port bridge.

Same discipline as ``test_beam_port_bridge.py``: spawn the real
``beam_port_bridge.py`` subprocess, write real JSON-lines requests to its
stdin, and assert on the real JSON responses it writes to stdout -- no
mocked subprocess, no mocked pipeline objects. Each op wraps the exact same
in-process object ``autofde_lab.sa2a.cli``'s Typer command of the same name
calls (see ``beam_port_bridge.py``'s module docstring).
"""

import json
import subprocess
import sys

BRIDGE_SCRIPT = "src/autofde_lab/beam/beam_port_bridge.py"


def _start_bridge() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, BRIDGE_SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _roundtrip(proc: subprocess.Popen, req: dict) -> dict:
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    assert line, f"no response line for request {req!r}; stderr={proc.stderr.read()}"
    return json.loads(line)


def test_sa2a_validate_default_profile() -> None:
    proc = _start_bridge()
    try:
        resp = _roundtrip(proc, {"op": "sa2a_validate"})
        assert resp["ok"] is True
        assert resp["status"] == "VALID"
        assert isinstance(resp["agent_id"], str) and resp["agent_id"]
        assert isinstance(resp["profile"], str) and resp["profile"]
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_sa2a_admit_and_plan_and_execute_and_replay_roundtrip() -> None:
    proc = _start_bridge()
    try:
        admit_resp = _roundtrip(
            proc,
            {
                "op": "sa2a_admit",
                "candidate_id": "cand-port-1",
                "query_id": "q-port-1",
                "assertion": "service:port-bridge requires-port",
                "source": "port-test",
                "evidence": {"source": "port-bridge-test"},
            },
        )
        assert "ok" in admit_resp
        assert "receipt_id" in admit_resp
        assert "standing" in admit_resp

        plan_resp = _roundtrip(
            proc,
            {
                "op": "sa2a_plan",
                "plan_id": "port_frontier_plan",
                "ticks": 500,
                "tokens": 10000,
                "experiments": 5,
                "candidates": [
                    {
                        "item_id": "item_alpha",
                        "description": "alpha",
                        "option_entropy": 2.0,
                        "estimated_cost": 5.0,
                        "historical_yield": 0.8,
                    },
                    {
                        "item_id": "item_beta",
                        "description": "beta",
                        "option_entropy": 1.0,
                        "estimated_cost": 15.0,
                        "historical_yield": 0.3,
                    },
                ],
            },
        )
        assert plan_resp["ok"] is True
        assert plan_resp["plan_id"] == "port_frontier_plan"
        assert isinstance(plan_resp["plan_hash"], str) and plan_resp["plan_hash"]
        item_ids = {a["item_id"] for a in plan_resp["allocations"]}
        assert item_ids == {"item_alpha", "item_beta"}

        exec_resp = _roundtrip(
            proc,
            {
                "op": "sa2a_execute",
                "query": "port-bridge-query",
                "compiled_rules": [["port-bridge-query", "port-bridge-answer"]],
            },
        )
        assert exec_resp["ok"] is True
        assert exec_resp["query"] == "port-bridge-query"
        assert exec_resp["result"] == "port-bridge-answer"
        assert exec_resp["llm_avoidance_ratio"] == 1.0

        manifest = {"a": 1, "b": [2, 3]}
        expected_hash = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        import hashlib

        expected_hash = hashlib.sha256(expected_hash.encode("utf-8")).hexdigest()

        replay_resp = _roundtrip(
            proc,
            {"op": "sa2a_replay", "manifest": manifest, "expected_hash": expected_hash},
        )
        assert replay_resp["ok"] is True
        assert replay_resp["verified"] is True
        assert replay_resp["computed_hash"] == expected_hash

        replay_mismatch_resp = _roundtrip(
            proc,
            {"op": "sa2a_replay", "manifest": manifest, "expected_hash": "deadbeef"},
        )
        assert replay_mismatch_resp["ok"] is False
        assert replay_mismatch_resp["verified"] is False
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_sa2a_unknown_op_still_routes_to_generic_refusal() -> None:
    proc = _start_bridge()
    try:
        resp = _roundtrip(proc, {"op": "sa2a_does_not_exist"})
        assert resp["ok"] is False
        assert "unknown_op" in resp["error"]
    finally:
        proc.terminate()
        proc.wait(timeout=5)
