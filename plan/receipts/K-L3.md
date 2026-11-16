# K-L3 court receipt
Standing: PASS

File: pipeline/tests/test_court_l3.py (14 tests, positive + anti-vacuity twins).
Command: PYTHONPATH=pipeline:pipeline/tests PLAN_SEARCH_TIMEOUT_S=5 uv run --quiet --with pytest
 --with factory-boy --with faker --with hypothesis --with allpairspy --with /Users/sac/pm4pytest
 pytest pipeline/tests/test_court_l3.py -q
Result: 3 consecutive runs, rc=0, "14 passed".
Covers: clock clamp (+later-pin twin), past-expiry record accepted, coi/license 2x2 matrix, undated
w9/contract non-expiring, dated w9/contract veto (default) vs record_and_warn, 5-provider MiniZinc
vs python unexpired diff, required_media/missing_media, soft default, hard_refuse, Stage-2 gate.
Early run (before owners landed) failed 8/14 on missing clamp and required_media: since landed.
Cross-owner defect: pipeline/tests/helpers_world.py:25 builds a parentless secondary_client, which
store.py:291 refuses (NO_PARENT); test_court_l3.py works around it locally (primary_client swap).
