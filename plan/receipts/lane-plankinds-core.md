# Lane plankinds-core receipt
Standing: PARTIAL

Subject: K1 aries, K2 minizinc, K3 cpsat, K7 ledger adapters, coverage_cover.py, test_plankinds_core.py
under /Users/sac/plan/pipeline/tests (no git in this checkout; no SHA).

## Command and output (PLAN_TEST_SEED=11)

```
cd /Users/sac/plan && PYTHONPATH=pipeline:pipeline/tests PLAN_TEST_SEED=11 uv run --quiet \
  --with pytest --with factory-boy --with faker --with allpairspy --with playwright \
  pytest -q -p no:cacheprovider -s pipeline/tests/test_plankinds_core.py
...
11 passed in 204.74s (0:03:24)
```

Deviations from the dispatched command (why Standing is PARTIAL, not ALIVE):
- `--with pypict` fails to build (pypict 0.1.0 sdist needs Cython, undeclared; uv build error), so
  the generator is never pypict here. `--with allpairspy` replaced it.
- conftest.py imports ui_driver -> playwright, so `--with playwright` is required.

## Covering arrays (12 factors, 1408 valid rows of 4096)

```
pairwise: size=10 generator=greedy valid_space=1408
order-3: size=21 generator=greedy valid_space=1408
```
Generator order is pypict -> allpairspy -> greedy; allpairspy output was rejected by the exhaustive
coverage check under the constraints, so the in-file greedy generator produced both arrays.
Both are verified by an independent exhaustive tuple check in the test.

## Differential K2 vs K3 (identical drawn world and state per case)

All 8 cases agree: eligible, blacklisted, expired, filtered, nobody_unapproved_reactive_hire,
second_provider_rescues, provider_rate_above_client_rate, provider_rate_equals_client_rate.

Registered divergences (KD rows): none. `REGISTERED_DIVERGENCES = {}` in k03_cpsat.py. The
client_billable_rate 0 divergence is closed at source (align.py + alignment_dispatch.mzn, per
coordinator); both margin-boundary cases (equal, above) yield NO_PLAN / reactive hire on both
backends.

## Findings

- K1 first run: stage2_tag_withheld returned PLAN because factory Params (part) are not dict keys;
  fixed in draw_world (`w["part"]`). Re-run: all K1 cases match expectation.
- conftest prints a stale `.results` scenario table from other lanes; unrelated to this lane.
