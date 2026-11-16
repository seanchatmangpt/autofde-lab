# K-L4 receipt
Standing: PARTIAL_ALIVE

Command: PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest --with factory-boy --with faker --with hypothesis --with allpairspy --with /Users/sac/pm4pytest pytest pipeline/tests/test_court_l4.py -q
Exit: 1 (14 passed, 1 failed).

Files: pipeline/tests/test_court_l4.py (new), pipeline/tests/ui_plan.py (settle oracle sums visits).

Failure (introduced by missing owner work, not this lane): test_dispatch_override_permits_banned_provider_and_is_unique.
store_cli.py cmd_dispatch refuses with REFUSED[not eligible] even when wo["dispatch_override"] names the
provider; it must honor the override (CONTRACT L4).

Pre-existing: helpers_world.build declares a secondary_client without parent, now refused NO_PARENT by
store.py; test_court_l4 wraps it locally (primary_client). helpers_world owner should fix.
