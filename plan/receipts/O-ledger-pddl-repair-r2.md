# O-ledger-pddl-repair-r2
Standing: PARTIAL
Owned files (ledger/*, spec/servengine_ideal_domain.pddl): no defect attributable.
Command: PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest ... pytest ledger/tests -q -> 18 passed, rc 0.
ledger/__main__.py returns exit 2 with {"refused":...} on LedgerError; a refused plan never reaches settle, so
"Ledger rendered exit 0 after refused plan" is not produced by owned code (unconfirmed, caller-side).
Failures are non-owned: NO_PARENT secondary_client from jtbd_factories.py:204 / ui_driver.py:85 (TEST/O-store);
missing justfile.d/45-ui.just recipe ui-vince-continuum, ui_envelopes.toml no_plan_marker (TEST);
console.py:456 refusal text (O-console); align.py dispatch_override (O-stagedalign).
No edits made.
