# Lane F4-full-matrix receipt
Standing: PARTIAL
Subject: /Users/sac/plan (no git state read; coordinator owns git). Date 2026-11-11.
## Command
PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest --with factory-boy --with faker --with hypothesis --with allpairspy --with /Users/sac/pm4pytest --with playwright pytest pipeline/tests/test_plankinds_matrix.py -k full_matrix -x -q -s
Exit: rc=1 ("1 failed, 5 deselected, 33 warnings in 358.46s"). Log: /tmp/fm.log
## Outcome (re-read from pipeline/tests/.results/plankind_matrix.json)
All 17 kinds (K1..K17) produced typed outcomes; none MISSING. unsupported list: 0.
Per-kind ok/cases: K1 5/5, K2 8/8, K3 8/8, K4 4/4, K5 4/4, K6 7/7, K7 5/5, K8 56/62,
K9 39/39, K10 7/7, K11 7/7, K12 9/9, K13 3/3, K14 6/6, K15 6/6, K16 SKIP (0 cases), K17 2/2.
## Failures (6, all K8 plan-replay executor)
K8/dup-0, dup-1, dup-5, dup-6, dup-7, dup-8: expected REFUSED got PLAN
(rc=0 receipts=10 refused=None goal=True ledger AR=58000 AP=25500 margin=32500).
Pre-existing vs session-introduced: no edits made this session (only receipts/ and .results written
by the test run); failures are not session-introduced. Shared reducer files not touched.
Not fixed: K8 files not owned by this lane.
