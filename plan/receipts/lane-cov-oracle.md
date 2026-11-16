# Lane cov-oracle receipt
Standing: PASS

Subject: /Users/sac/plan (no git, SHA n/a). Files: pipeline/tests/coverage_model.py,
coverage_factors.toml, test_coverage_oracle.py.

## Command and output (exit 0)

`cd /Users/sac/plan && PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest
--with factory-boy --with faker --with playwright pytest -q -s -p no:cacheprovider
pipeline/tests/test_coverage_oracle.py`

```
MAIN_CELLS=62208 product=62208
CELLS_CHECKED=62208 DISTINCT_STORE_REPLAYS=6912
OUTCOMES {INCOMPLETE@dispatch 648, @eligibility 648, @stage2 216, @store 10368, @territory 5184,
          REFUSED@eligibility 18144, @ledger 144, @stage2 864, @territory 25920, SETTLED 72}
SIDE_CELLS=432 REFUSED_AT_STORE=288
9 passed in 426.38s (0:07:06)
```

Note: the contract command lacks `--with playwright`; the existing conftest.py imports
ui_driver (playwright) so collection fails without it (ModuleNotFoundError, observed).
Runtime is ~7 min: 6912 real store replays (cell store-signatures deduped; truncation and
other non-store factors share a replay).

## Factor space

Main product 62208 = wo_kind 6 (store.subtypes) x part 3 x docs 4 x site_filter 4 x
territory 2 x nte 3 x attest 2 x provider_count 3 x truncation 6. Collapsed out of the main
product into a side sweep (432 cells, every one replayed): client_kind 3 (incl. bad), provider_kind
3 (incl. bad), blacklist 2, nte 4 (incl. nonpositive), (provider_count, retries 0..count-1).
Docs/filter/blacklist apply uniformly to all providers of a cell.

## Oracle faithfulness

Gate 1 compared against real store.append/check (PLAN_STORE temp file): accept/refuse code equal
in all 62208 + 432 cells. Ledger gate compared against real ledger.core.settle (NteCapError iff
oracle NTE_CAP). Eligibility/territory/dispatch/stage-2 gates are oracle-only (not executed
against MiniZinc/planner in this lane).

## KD rows (unenforced; CURRENT behavior pinned by tests)

| id | surface | divergence | evidence | close condition |
|---|---|---|---|---|
| KD-COV-1 | provider_filter | `dim` arbitrary, accepted | test_kd1 | store validates dim in align.DIMS |
| KD-COV-2 | client | secondary_client without parent accepted | test_kd2 | store requires parent for secondary |
| KD-COV-3 | provider_doc | past expiry_date accepted at record time | test_kd3 | store refuses or flags expired docs |
| KD-COV-4 | work_order/checkout | part replacement w/o model tag photo accepted at store; refusal only in stage-2 | test_kd4 | store enforces tag before checkout |

Falsifier: any cell where oracle gate-1 disagrees with store.check fails the suite (none did).
