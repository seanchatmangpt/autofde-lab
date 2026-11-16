# K-L1 court receipt
Standing: PARTIAL
Cmd: PYTHONPATH=pipeline:pipeline/tests uv run ... pytest pipeline/tests/test_court_l1.py -q
Exit: 1. Result: 15 passed, 9 failed (re-run at write time).
Failures are all owner-S gaps (store.py lacks BAD_DIM check, invoice_left_on_site,
site_manager_clash events; staged.plan_wo lacks `flags`). Positive+twin tests pass for
valid DIMS, bad mode, baseline eligibility, flip-filter-mode, no-handoff twins.
