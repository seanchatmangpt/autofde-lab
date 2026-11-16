# K-L4-repair-r1
Standing: PARTIAL

Owned file: pipeline/tests/test_court_l4.py (no edit needed; its build() already declares the client primary).

Command: PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest ... pytest pipeline/tests/test_court_l4.py -q
Exit: 0; 15 passed (includes test_dispatch_override_permits_banned_provider_and_is_unique).

Not fixed (files not owned): pipeline/tests/helpers_world.py:29 and test_ocel_bridge.py:39 declare
secondary_client with no parent; store.py:290 raises NO_PARENT. test_staged.py fails on this
(test_events_refuse_bad_references reproduced). Fix: owner of helpers_world/test_ocel_bridge supplies a
parent primary client or uses primary_client.
Other listed ui/just/ledger failures: outside this lane, not run.
