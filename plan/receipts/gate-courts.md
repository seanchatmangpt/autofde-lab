# gate-courts receipt
Standing: PASS

Command (cwd /Users/sac/plan):
PLAN_SEARCH_TIMEOUT_S=5 PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest --with factory-boy --with faker --with hypothesis --with allpairspy --with playwright --with /Users/sac/pm4pytest pytest pipeline/tests/test_court_*.py pipeline/tests/test_dials.py pipeline/tests/test_artifact_sync.py pipeline/tests/test_staged.py pipeline/tests/test_pipeline.py pipeline/tests/test_ocel_bridge.py -q --maxfail=1000 -p no:cacheprovider

Files run: test_court_b5, l1..l6, test_dials, test_artifact_sync, test_staged, test_pipeline, test_ocel_bridge.
Output: "115 passed in 57.67s" (exit code not captured: pipe to tail under zsh; pass line is the evidence).
Failures: 0. Owner classification: none (O-store 0, O-stagedalign 0, O-console 0, O-ledger-pddl 0, O-dials 0, TEST 0).
Pre-existing vs introduced: none observed.
