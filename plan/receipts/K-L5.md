# K-L5 roles court
Standing: PASS

Command: PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest --with factory-boy --with faker --with hypothesis --with allpairspy --with /Users/sac/pm4pytest pytest pipeline/tests/test_court_l5.py -q -p no:cacheprovider
Exit: 0 ; output: 11 passed in 0.26s
Files: pipeline/tests/test_court_l5.py (new), pipeline/tests/avatar_roster.toml ([kinds] added).
Note: helpers_world.build() failed mid-run with NO_PARENT[secondary_client] (other lane's store change);
court uses its own entity+primary_client world. Pre-existing/other-owner: helpers_world.build needs parent.
