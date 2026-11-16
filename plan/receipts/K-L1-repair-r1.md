# K-L1-repair-r1
Standing: PARTIAL
Fixed: pipeline/tests/test_court_l1.py (24 TEST x NO_PARENT) via primary_client build wrapper
(same disclosed pattern as test_court_l3.py). Command: pytest pipeline/tests/test_court_l1.py -q
rc=0, 24 passed.
Not mine / not fixed: root cause helpers_world.py:29 (secondary_client without parent) still
breaks test_staged x5, test_ocel_bridge x3, ui scenarios; owner should change helper to
primary_client. Other listed items (justfile.d/45-ui.just, streamlit, O-* reducer defects) untouched.
