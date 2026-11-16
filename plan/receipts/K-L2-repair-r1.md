# K-L2-repair-r1
Standing: PARTIAL

Edits: pipeline/tests/helpers_world.py and test_ocel_bridge.py (add primary parent client so the
secondary client is lawful, fixes NO_PARENT x32); test_staged.py (part-replacement: accept
compile-level MISSING as the pre-tag refusal).
Command: PLAN_SEARCH_TIMEOUT_S=5 PYTHONPATH=pipeline:pipeline/tests uv run ... pytest
test_staged.py test_ocel_bridge.py test_court_l1.py -q
Output: 34 passed (run 1 after parent fix: 1 failed, 33 passed); a later run had 1 failed
(test_full_flow, line 80, planner under load) and 33 passed; isolated reruns of that test 10/10 pass.
Not addressed: ui-jtbd/ui-chicago/justfile recipes, streamlit smoke, O-* reducer defects.
