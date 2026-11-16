"""Matrix machinery (synthetic registry, real run_kind) + per-kind K10/K17 + the full gate.

Run the full gate alone with `-k full_matrix`; it is expected to fail while kinds are missing."""
import pytest

import plan_matrix as pm
from plankinds import Case, Outcome, Skip, k10_pm4pytest, k17_stateful, run_kind


class _Mod:
    """Hand-written real adapter (not a mock) for exercising the matrix machinery."""
    def __init__(self, kind, results=None, skip=None):
        self.KIND, self.TITLE, self._r, self._s = kind, f"synthetic {kind}", results or [], skip

    def probe(self):
        return self._s

    def cases(self):
        return [Case(f"c{i}", e) for i, (e, _) in enumerate(self._r)]

    def run(self, case):
        return Outcome(self._r[int(case.id[1:])][1])


def test_missing_kind_fails_closed(tmp_path):
    reg = {"K1": _Mod("K1", [("PLAN", "PLAN")])}
    rows, uns = pm.collect(registry=reg, expected=["K1", "K2"])
    assert [r["status"] for r in rows] == ["PLAN", "MISSING"]
    with pytest.raises(AssertionError, match="K2 MISSING"):
        pm.check(rows, uns, out=tmp_path / "m.json")


def test_skip_and_unsupported_count_as_present(tmp_path):
    reg = {"K1": _Mod("K1", skip=Skip("no tool", "install it")),
           "K2": _Mod("K2", [("UNSUPPORTED", "UNSUPPORTED")])}
    rows, uns = pm.collect(registry=reg, expected=["K1", "K2"])
    assert len(uns) == 1 and uns[0]["kind"] == "K2"
    pm.check(rows, uns, out=tmp_path / "m.json")
    assert (tmp_path / "m.json").exists()


def test_divergent_case_fails(tmp_path):
    reg = {"K1": _Mod("K1", [("PLAN", "NO_PLAN")])}
    rows, uns = pm.collect(registry=reg, expected=["K1"])
    with pytest.raises(AssertionError, match="expected PLAN got NO_PLAN"):
        pm.check(rows, uns, out=tmp_path / "m.json")


@pytest.mark.parametrize("mod", [k10_pm4pytest, k17_stateful], ids=lambda m: m.KIND)
def test_kind_cases_all_ok(mod):
    assert mod.probe() is None
    rows = run_kind(mod)
    assert rows and all(r["ok"] for r in rows), rows


def test_full_matrix():
    pm.check()
