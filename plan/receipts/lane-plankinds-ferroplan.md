# lane-plankinds-ferroplan (F3: ferroplan K11-K13)
Standing: PASS

Base state: /Users/sac/plan, not a git repo (no SHA available); ferroplan at /Users/sac/ferroplan,
wasm /Users/sac/ex4pm/priv/ferroplan/ferroplan_wasm.wasm (K11 default paths).

## Command
PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest --with factory-boy --with faker
--with hypothesis --with allpairspy --with /Users/sac/pm4pytest pytest
pipeline/tests/test_plankinds_ferroplan.py -v -p no:cacheprovider

Exit code: 0 (pytest rc via PIPESTATUS).

## Output
test_kind_rows[K11] PASSED; test_kind_rows[K12] PASSED; test_kind_rows[K13] PASSED
3 passed in 3.23s (PLAN_TEST_SEED=1842539826)

Note: running pipeline/tests/plankinds/k1*.py directly collects 0 items (adapters, not test files);
the test driver is test_plankinds_ferroplan.py.

## Files touched
receipts/lane-plankinds-ferroplan.md only. No pre-existing or session-introduced failures observed.
