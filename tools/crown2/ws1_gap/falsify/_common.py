"""Shared real-shaped beam4pm base state for WS1 falsifiers. Imports the REAL target."""
from __future__ import annotations
import copy, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
from gap import classify_fixture, GapType  # noqa: E402  (real target, not a copy)

BASE = json.load(open(os.path.join(HERE, "..", "fixtures", "state_command_only_in_ci.json")))

def fresh_base() -> dict:
    fx = copy.deepcopy(BASE)
    fx.pop("expected_gap_type", None); fx.pop("tags", None)
    return fx

def run(name: str, fx: dict, expected: str, why: str) -> dict:
    got = classify_fixture(fx)
    rec = {"falsifier": name, "expected": expected, "got": got.gap_type.value,
           "reproduces": got.gap_type.value != expected,
           "observations": got.supporting_observations, "why": why}
    print(json.dumps(rec, sort_keys=True))
    return rec
