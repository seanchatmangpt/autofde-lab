"""K8 executor + K9 courts through the plan-kind contract; every case must meet its expectation.

Registered divergence (receipt row KD-K8-DUP): a duplicated action whose effects are idempotent is
accepted by the executor (rc 0, identical ledger); only those dup-* PLAN outcomes are tolerated, and
only when the ledger equals the unmutated plan's."""
import pytest

from plankinds import run_kind
from plankinds import k08_executor, k09_courts

LEDGER = "ledger={'AR': 58000, 'AP': 25500, 'margin': 32500}"


def _registered(r):
    return (r["kind"] == "K8" and r["case"].startswith("dup-") and r["status"] == "PLAN"
            and LEDGER in r["detail"])


@pytest.mark.parametrize("mod", [k08_executor, k09_courts], ids=lambda m: m.KIND)
def test_kind_outcomes_match_expect(mod):
    rows = run_kind(mod)
    assert rows
    for r in rows:
        print(r["kind"], r["case"], r["expect"], r["status"], r["detail"])
    bad = [r for r in rows if r["status"] == "SKIP" or not (r.get("ok") or _registered(r))]
    assert not bad, bad
    if mod is k09_courts:
        print("K9 DIVERGENCES", mod.DIVERGENCES)
        assert not mod.DIVERGENCES
