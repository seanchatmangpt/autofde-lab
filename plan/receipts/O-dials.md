# O-dials receipt
Standing: PASS

Command: PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest ... pytest pipeline/tests/test_dials.py -q
Exit: 0. Output: 5 passed.
Files: pipeline/policy_dials.toml, pipeline/enterprise_pipeline/dials.py, pipeline/tests/test_dials.py.
Note: default_nte_cost_share_bps has no value in open_switches.toml; returns None (not chosen).
