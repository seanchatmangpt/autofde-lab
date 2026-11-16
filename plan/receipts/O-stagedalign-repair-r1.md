# O-stagedalign-repair-r1
Standing: PARTIAL
Fixed: align.py apply_override no longer excludes blacklisted providers (CONTRACT-LAWS l.117-119:
override permits a provider the court rejects). Command: pytest test_court_l4.py test_staged.py
(PYTHONPATH=pipeline:pipeline/tests uv run ... pytest) -> 16 passed, 5 failed; l4 override test now passes.
Remaining 5 test_staged failures: NO_PARENT[...] raised at store.py:291 from tests/helpers_world.py:29
(secondary_client without parent). Neither file is owned by this lane; needs helper to build a primary
client + parent (or store owner to relax). Not fixed here. Other listed failures (ui/ledger/console) not owned.
