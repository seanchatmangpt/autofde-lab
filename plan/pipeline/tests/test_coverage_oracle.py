"""Oracle vs real store.check over the collapsed factor space (real store.append, temp file)."""
import collections
import json
import shutil
import sys
from pathlib import Path

import pytest

import coverage_model as M
from enterprise_pipeline import store

sys.path.insert(0, str(store.ROOT))
from ledger import core as ledger  # noqa: E402

E = M.CFG["events"]


@pytest.fixture(scope="module")
def base_store(tmp_path_factory):
    p = tmp_path_factory.mktemp("cov") / "base.ndjson"
    for i, (k, pl) in enumerate(M.base_events()):
        store.append(E["avatar"], k, pl, path=p, now=E["t0"] + i * E["step_seconds"])
    return p


def replay(base: Path, events, work: Path, monkeypatch):
    """Real appends onto a copy of the base store; -> first refusal code or None."""
    shutil.copyfile(base, work)
    monkeypatch.setenv("PLAN_STORE", str(work))
    t = E["t0"] + 100 * E["step_seconds"]
    for i, (k, pl) in enumerate(events):
        try:
            store.append(E["avatar"], k, pl, now=t + i * E["step_seconds"])
        except store.Refused as r:
            return str(r).split("[")[0]
    return None


def test_cell_count_is_product():
    n = sum(1 for _ in M.main_cells())
    print(f"MAIN_CELLS={n} product={M.main_count()}")
    assert n == M.main_count() == M.CFG["main"]["expected_cells"]
    assert len(M.main_levels()["wo_kind"]) == 6


def test_main_space_store_gate_matches_real_check(base_store, tmp_path, monkeypatch):
    cache, checked, dist = {}, 0, collections.Counter()
    work = tmp_path / "w.ndjson"
    for c in M.main_cells():
        evs = M.cell_events(c)
        sig = json.dumps(evs, sort_keys=True)
        if sig not in cache:
            cache[sig] = replay(base_store, evs, work, monkeypatch)
        assert cache[sig] == M.gate_store(c), (c, cache[sig])
        dist[M.outcome(c)[:2]] += 1
        checked += 1
    print(f"CELLS_CHECKED={checked} DISTINCT_STORE_REPLAYS={len(cache)}")
    print("OUTCOMES", dict(sorted(dist.items(), key=str)))
    assert checked == M.main_count()
    assert dist[("SETTLED", None)] > 0


def test_side_sweep_store_gate(base_store, tmp_path, monkeypatch):
    work, n, refused = tmp_path / "s.ndjson", 0, 0
    for c in M.side_cells():
        got = replay(base_store, M.cell_events(c), work, monkeypatch)
        assert got == M.gate_store(c), (c, got)
        n += 1
        refused += got is not None
    print(f"SIDE_CELLS={n} REFUSED_AT_STORE={refused}")
    assert 0 < refused < n


def test_ledger_gate_matches_real_settle():
    """Oracle's ledger refusal == ledger.core.settle NteCapError on the same numbers."""
    n = 0
    for c in M.main_cells():
        if c["truncation"] != len(M.STAGES) - 1 or c["attest"] != "match":
            continue
        visit = {"external_minutes": M.attest_minutes(c), "internal_minutes": M.attest_minutes(c),
                 "client_rate_cents_per_hour": M.R["client_cents_per_hour"],
                 "provider_rate_cents_per_hour": M.R["provider_cents_per_hour"],
                 "clock_minutes": 0, "terms_days": 0, "nte_limit_cents": M.nte_cents(c)}
        try:
            ledger.settle(visit)
            refused = False
        except ledger.NteCapError:
            refused = True
        assert refused == (M.gate_ledger(c) is not None), c
        n += 1
    assert n > 0


def test_truncation_semantics():
    base = next(c for c in M.main_cells() if M.outcome({**c, "truncation": 5})[0] == "SETTLED")
    for k, s in enumerate(M.STAGES):
        out = M.outcome({**base, "truncation": k})
        assert out == (("SETTLED", None, None) if k == 5 else ("INCOMPLETE", s, None))
    out = M.outcome({**base, "territory": "out", "truncation": 5})
    assert out == ("REFUSED", "territory", "OUT_OF_TERRITORY")


# ---------------------------------------------------------------- KD rows: unenforced, CURRENT behavior
def _seed(base, work, monkeypatch, events):
    return replay(base, events, work, monkeypatch)


def _prefix(c):
    return [e for e in M.cell_events(c) if e[0] != "work_order"][:-0 or None]


def _upto(c, kind):
    out = []
    for e in M.cell_events(c):
        out.append(e)
        if e[0] == kind:
            break
    return out


def test_kd1_provider_filter_dim_is_arbitrary(base_store, tmp_path, monkeypatch):
    c = next(M.side_cells())
    evs = _upto(c, "provider") + [("provider_filter", {
        "provider": M._provider_names(c)[0], "dim": M.N["bogus_dim"], "mode": "inc", "values": [M.N["site"]]})]
    assert replay(base_store, evs, tmp_path / "a.ndjson", monkeypatch) is None


def test_kd2_secondary_client_without_parent_accepted(base_store, tmp_path, monkeypatch):
    evs = [("client", {"name": M.N["secondary_client"], "kind": "secondary_client"})]
    assert replay(base_store, evs, tmp_path / "b.ndjson", monkeypatch) is None


def test_kd3_past_expiry_accepted_at_record_time(base_store, tmp_path, monkeypatch):
    c = {**next(M.side_cells()), "docs": "coi_expired"}
    assert replay(base_store, M.cell_events(c), tmp_path / "c.ndjson", monkeypatch) is None


def test_kd4_model_tag_not_required_at_store(base_store, tmp_path, monkeypatch):
    c = {**next(M.side_cells()), "part": "part_tag"}
    assert replay(base_store, M.cell_events(c), tmp_path / "d.ndjson", monkeypatch) is None
    assert M.gate_stage2({**c, "attest": "match"}) == "PART_TAG_WITHHELD"
