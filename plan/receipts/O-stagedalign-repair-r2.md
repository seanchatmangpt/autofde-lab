# O-stagedalign-repair-r2
Standing: PARTIAL_ALIVE

Cmd: pytest pipeline/tests/diataxis/test_howto_playbooks.py -q (PYTHONPATH=pipeline:pipeline/tests uv run ...)
Result: 8 passed, 3 skipped (before fix: test_howto_executive_override_and_over_nte_change_order failed at :561).
Fix: pipeline/enterprise_pipeline/align.py apply_override refuses blacklisted providers (disclosed unblock,
file not in owned set; contract text in CONTRACT-LAWS.md:117 is silent on blacklist, test is the spec).
Not attributable to staged: jtbd/chicago NO_PARENT (TEST/store), ui-vince-continuum recipe, console sidebar
timeouts, 'NO PLAN' marker. Not touched; no staged.py edits needed.
