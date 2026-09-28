"""Chicago-style tests: the real published graphlaw WASI module, no test doubles."""

from __future__ import annotations

import pytest

from autofde_lab.fabric import graphlaw_court as gc
from autofde_lab.fabric.guardrails import GuardrailStanding, guarded_candidate

_MODULE_OK = True
try:
    gc.find_graphlaw_wasm()
except gc.GraphlawModuleMissing:
    _MODULE_OK = False

pytestmark = [
    pytest.mark.skipif(not gc.AVAILABLE, reason="wasmtime package not installed"),
    pytest.mark.skipif(
        not _MODULE_OK, reason="graphlaw_wasm.wasm absent ($GRAPHLAW_WASM / default path)"
    ),
]

EX = "http://example.org/"
STATE = [(EX + "a", EX + "at", EX + "start")]
GOAL = [(EX + "a", EX + "at", EX + "end")]


def _t(s: str, o: str) -> tuple[str, str, str]:
    return (EX + s, EX + "at", EX + o)


def _plan() -> list[dict]:
    return [
        {"name": "m1", "pre": [_t("a", "start")], "add": [_t("a", "mid1")], "del": [_t("a", "start")]},
        {"name": "m2", "pre": [_t("a", "mid1")], "add": [_t("a", "mid2")], "del": [_t("a", "mid1")]},
        {"name": "m3", "pre": [_t("a", "mid2")], "add": [_t("a", "end")], "del": [_t("a", "mid2")]},
    ]


def test_valid_plan_admitted_with_chained_receipts():
    adm = gc.admit_plan(STATE, _plan(), GOAL)
    assert len(adm.receipts) == 3
    for prev, cur in zip(adm.receipts, adm.receipts[1:]):
        assert cur["parent"] == prev["child"]


def test_falsifier_missing_precondition_refused_at_index():
    plan = _plan()
    plan[1] = dict(plan[1], pre=[_t("a", "nowhere")])
    with pytest.raises(gc.PlanRefused) as exc:
        gc.admit_plan(STATE, plan, GOAL)
    assert exc.value.index == 1
    assert exc.value.action == "m2"
    assert exc.value.message.startswith("plan refused at step 1")


def test_replay_is_byte_identical():
    a = gc.admit_plan(STATE, _plan(), GOAL)
    b = gc.admit_plan(STATE, _plan(), GOAL)
    assert a.receipts == b.receipts and a.states == b.states


class _Provider:
    def __init__(self, actions):
        self.actions = actions

    def propose(self, observation):
        return {"plan": self.actions}


def _court(candidate):
    return gc.admit_plan(STATE, candidate["plan"], GOAL)


def test_guarded_candidate_court_admits_valid_refuses_mutated():
    ok = guarded_candidate(_Provider(_plan()), {}, court=_court)
    assert ok.standing is GuardrailStanding.CANDIDATE
    bad_plan = _plan()
    bad_plan[2] = dict(bad_plan[2], pre=[_t("a", "nowhere")])
    bad = guarded_candidate(_Provider(bad_plan), {}, court=_court)
    assert bad.standing is GuardrailStanding.REFUSED_OUTPUT
    assert "plan refused at step 2" in bad.reason


def test_default_court_none_unchanged():
    d = guarded_candidate(_Provider(_plan()), {})
    assert d.standing is GuardrailStanding.CANDIDATE
