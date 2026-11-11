"""Lane B4: rl_shielded and powl kinds through real subprocess calls."""

from __future__ import annotations

import json
import subprocess
import sys

from faker import Faker
import factory
import factory.random

fake = Faker()
Faker.seed(20261112)
factory.random.reseed_random(20261112)


def call(kind, payload, options=None, timeout=300):
    proc = subprocess.run(
        [sys.executable, "-m", "autofde_lab.coprocessor", kind],
        input=json.dumps({"kind": kind, "payload": payload, "options": options or {}}),
        capture_output=True, text=True, timeout=timeout,
    )
    return proc.returncode, json.loads(proc.stdout)


def _stand_payload():
    return {
        "n_stands": fake.random_int(min=3, max=5),
        "horizon": fake.random_int(min=15, max=25),
        "seed": fake.random_int(min=0, max=10_000),
    }


def test_rl_shielded_never_double_books_and_beats_unshielded():
    payload = _stand_payload()
    rc, out = call("rl_shielded", payload, {"timesteps": 20000})
    assert rc == 0 and out["status"] == "PLAN", out
    d = out["diagnostics"]
    assert d["train_seconds"] <= 60
    # Replay the emitted sequence: no stand is booked while still occupied.
    free_at = {}
    for a in out["actions"]:
        if a["stand"] is None:
            continue
        assert free_at.get(a["stand"], 0) <= a["t"], a
        free_at[a["stand"]] = a["t"] + a["dwell"]
    assert len(out["actions"]) == payload["horizon"]
    assert d["shielded_conflicts"] == 0 and d["shielded_conflicts_mean"] == 0
    # Same policy, no shield: conflicts occur (environment is not vacuous).
    assert d["unshielded_conflicts_mean"] > d["shielded_conflicts_mean"]


def test_rl_shielded_infeasible_and_refused():
    payload = _stand_payload()
    payload["blocked_stands"] = list(range(payload["n_stands"]))
    rc, out = call("rl_shielded", payload, {"timesteps": 100})
    assert rc == 2 and out["status"] == "INFEASIBLE"
    rc, out = call("rl_shielded", {"n_stands": 1, "horizon": 5})
    assert rc == 2 and out["status"] == "REFUSED"
    rc, out = call("rl_shielded", _stand_payload(), {"timesteps": 10**9})
    assert rc == 2 and out["status"] == "REFUSED"


def test_powl_roundtrips_plan_in_order():
    objs = [fake.unique.word() for _ in range(4)]
    plan = [f"(unstack {objs[0]} {objs[1]})", f"(put-down {objs[0]})",
            f"(pick-up {objs[2]})", f"(stack {objs[2]} {objs[3]})", "; cost = 4"]
    rc, out = call("powl", {"plan": plan})
    assert rc == 0 and out["status"] == "PLAN", out
    assert out["actions"] == plan[:4]
    assert out["cost"] == 4


def test_powl_refuses_empty_and_malformed_plan():
    rc, out = call("powl", {"plan": ["; only a comment"]})
    assert rc == 2 and out["status"] == "REFUSED"
    rc, out = call("powl", {"plan": "not-a-list"})
    assert rc == 2 and out["status"] == "REFUSED"
