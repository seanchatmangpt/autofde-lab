import json, re, subprocess, sys
from pathlib import Path
import pytest
from hypothesis import given, strategies as st
from ledger import (cents_for, due_timestamp, margin_bp, post_ar, post_ap, settle,
                    MarginGuardError, NteCapError)

ROOT = Path(__file__).resolve().parents[2]
PDDL = ROOT / "spec" / "servengine_ideal_domain.pddl"
mins = st.integers(0, 10**5)
rates = st.integers(0, 10**6)


def visit(**kw):
    v = dict(clock_minutes=0, terms_days=45, external_minutes=240, internal_minutes=180,
             client_rate_cents_per_hour=14500, provider_rate_cents_per_hour=8500,
             nte_limit_cents=150000)
    v.update(kw)
    return v


def test_canonical():
    s = settle(visit())
    assert (s.ar_cents, s.ap_cents, s.margin_cents, s.margin_bp) == (58000, 25500, 32500, 5603)
    assert s.due_timestamp == 45 * 1440


# (a) source isolation
@given(e=mins, i=mins, cr=rates, pr=rates, i2=mins, e2=mins)
def test_ar_ap_independence(e, i, cr, pr, i2, e2):
    assert post_ar(e, cr)[0] == cents_for(e, cr)
    assert post_ap(i, pr)[0] == cents_for(i, pr)
    # AR is invariant under internal duration; AP under external
    ar = lambda ii: settle_ar(e, cr, ii)
    assert ar(i) == ar(i2)
    assert post_ap(i, pr)[0] == post_ap(i, pr)[0]


def settle_ar(e, cr, internal):
    return post_ar(e, cr)[0]


@given(e=st.integers(1, 5000), i=st.integers(1, 5000), i2=st.integers(1, 5000), e2=st.integers(1, 5000))
def test_settle_ar_ignores_internal_ap_ignores_external(e, i, i2, e2):
    kw = dict(nte_limit_cents=10**12, override_receipt={"id": "o", "reason": "t"})
    a = settle(visit(external_minutes=e, internal_minutes=i, **kw))
    b = settle(visit(external_minutes=e, internal_minutes=i2, **kw))
    c = settle(visit(external_minutes=e2, internal_minutes=i, **kw))
    assert a.ar_cents == b.ar_cents
    assert a.ap_cents == c.ap_cents


# (b) rounding
@given(m=mins, r=rates)
def test_ceil_rule(m, r):
    c = cents_for(m, r)
    assert c * 60 >= m * r and (c - 1) * 60 < m * r or c == 0
    assert isinstance(c, int)


def test_rounding_examples():
    assert cents_for(1, 100) == 2      # 1.666.. -> 2
    assert cents_for(60, 14500) == 14500
    assert cents_for(0, 14500) == 0
    assert cents_for(90, 101) == 152   # 151.5 -> 152


# due
@given(c=mins, d=st.integers(0, 365))
def test_due(c, d):
    assert due_timestamp(c, d) == c + d * 1440


# (c) margin guard
@given(m=st.integers(1, 5000), cr=st.integers(1, 10**5), pr=st.integers(1, 10**5))
def test_margin_guard(m, cr, pr):
    ar, ap = cents_for(m, cr), cents_for(m, pr)
    v = visit(external_minutes=m, internal_minutes=m, client_rate_cents_per_hour=cr,
              provider_rate_cents_per_hour=pr, nte_limit_cents=10**12)
    if ar <= ap:
        with pytest.raises(MarginGuardError):
            settle(v)
        s = settle({**v, "override_receipt": {"id": "R1", "reason": "loss leader"}})
        assert s.override_used
    else:
        assert not settle(v).override_used


def test_bad_override_refused():
    v = visit(internal_minutes=240, client_rate_cents_per_hour=100, provider_rate_cents_per_hour=100)
    for bad in (None, {}, {"id": "x"}, "yes", True):
        with pytest.raises(MarginGuardError):
            settle({**v, "override_receipt": bad})


# (d) NTE
@given(nte=st.integers(0, 200000))
def test_nte(nte):
    v = visit(nte_limit_cents=nte)
    if 58000 > nte:
        with pytest.raises(NteCapError):
            settle(v)
        with pytest.raises(NteCapError):
            settle({**v, "change_order": {"approved": False, "new_nte_limit_cents": 10**9}})
        with pytest.raises(NteCapError):
            settle({**v, "change_order": {"approved": True, "new_nte_limit_cents": 57999}})
        assert settle({**v, "change_order": {"approved": True, "new_nte_limit_cents": 58000}})
    else:
        assert settle(v).ar_cents == 58000


# (e) conservation
@given(e=mins, i=mins, cr=rates, pr=rates)
def test_conservation(e, i, cr, pr):
    for ps in (post_ar(e, cr)[1], post_ap(i, pr)[1]):
        assert sum(p.amount for p in ps) == 0
    v = visit(external_minutes=e, internal_minutes=i, client_rate_cents_per_hour=cr,
              provider_rate_cents_per_hour=pr, nte_limit_cents=10**13,
              override_receipt={"id": "o", "reason": "t"})
    s = settle(v)
    assert sum(p.amount for p in s.postings) == 0
    for t in ("AR", "AP"):
        assert sum(p.amount for p in s.postings if p.txn == t) == 0


@given(ar=st.integers(1, 10**9), ap=st.integers(0, 10**9))
def test_margin_bp_floor(ar, ap):
    assert margin_bp(ar, ap) == ((ar - ap) * 10000) // ar


def test_no_float_in_source():
    import ast
    tree = ast.parse((ROOT / "ledger" / "core.py").read_text())
    for n in ast.walk(tree):
        assert not (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div))
        assert not (isinstance(n, ast.Constant) and isinstance(n.value, float))
        assert not (isinstance(n, ast.Name) and n.id == "float")


# PDDL conformance (read-only)
def _effects():
    t = PDDL.read_text()
    ar = re.search(r"\(assign \(invoice-amount \?inv\) \(\* \(external-client-duration \?v\) \(client-labor-rate \?c \?t\)\)\)", t)
    ap = re.search(r"\(assign \(ap-payout-amount \?pay\) \(\* \(internal-actual-duration \?v\) \(provider-agreed-rate \?p \?t\)\)\)", t)
    due = re.search(r"\(assign \(invoice-due-timestamp \?inv\) \(\+ \(current-clock\) \(\* \(client-payment-terms-days \?c\) (\d+)\)\)\)", t)
    return ar, ap, due


def test_pddl_effect_expressions_match_library_structure():
    ar, ap, due = _effects()
    assert ar, "AR effect not external-duration x client-rate"
    assert ap, "AP effect not internal-duration x provider-rate"
    assert due and int(due.group(1)) == 1440


def test_pddl_numeric_semantics_whole_hours():
    # evaluate the PDDL product on the problem file's numbers and compare
    prob = (ROOT / "spec" / "problem_enterprise_ops.pddl").read_text()
    g = lambda pat: int(re.search(pat, prob).group(1))
    ext = g(r"\(= \(external-client-duration vis_9001_01\) (\d+)\)")
    internal = g(r"\(= \(internal-actual-duration vis_9001_01\) (\d+)\)")
    cr = g(r"\(= \(client-labor-rate cli_facility_broker tr_hvac\) (\d+)\)")
    pr = g(r"\(= \(provider-agreed-rate prov_sean_hvac tr_hvac\) (\d+)\)")
    terms = g(r"\(= \(client-payment-terms-days cli_facility_broker\) (\d+)\)")
    assert ext * cr == 58000 and internal * pr == 25500  # PDDL (* a b)
    assert post_ar(ext * 60, cr)[0] == ext * cr
    assert post_ap(internal * 60, pr)[0] == internal * pr
    assert due_timestamp(0, terms) == 0 + terms * 1440


@given(h=st.integers(0, 2000), r=rates)
def test_whole_hour_equals_pddl_product(h, r):
    assert cents_for(h * 60, r) == h * r


# CLI
def _cli(payload):
    return subprocess.run([sys.executable, "-m", "ledger", "settle"], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=ROOT)


def test_cli_canonical_and_refusal():
    p = _cli(visit())
    assert p.returncode == 0
    o = json.loads(p.stdout)
    assert (o["ar_cents"], o["ap_cents"], o["margin_cents"]) == (58000, 25500, 32500)
    q = _cli(visit(nte_limit_cents=1000))
    assert q.returncode == 2 and json.loads(q.stdout)["refused"] == "NteCapError"


def test_visits_aggregate_ar_ap():
    one = settle(visit())
    two = settle(visit(visits=[dict(external_minutes=240, internal_minutes=180),
                               dict(external_minutes=240, internal_minutes=180)],
                       nte_limit_cents=10**6))
    assert (two.ar_cents, two.ap_cents) == (2 * one.ar_cents, 2 * one.ap_cents)
    for t in ("AR", "AP"):
        legs = [p for p in two.postings if p.txn == t]
        assert len(legs) == 4 and sum(p.amount for p in legs) == 0


def test_pddl_new_surfaces_and_copies_identical():
    txt = PDDL.read_text()
    for name in ("derive-wo-territory-cleared", "reactive-hire-handoff", "wo-linked-parent",
                 "wo-state-proposal-pending", "provider-pay-duration", "open-follow-up-visit"):
        assert name in txt
    assert txt == (ROOT / "executor" / "fixtures" / "servengine_ideal_domain.pddl").read_text()
