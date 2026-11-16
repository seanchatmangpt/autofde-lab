# L7-generator

Standing: PARTIAL

Subject: /Users/sac/plan (no git; SHA unavailable). Files: pipeline/rules_report.py,
pipeline/tests/laws_ledger.py, pipeline/tests/test_rules_report.py, justfile.d/47-rules.just.

## Commands
- `PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest pytest -q -p no:cacheprovider
  pipeline/tests/test_rules_report.py` -> `6 passed in 1.01s` (exit 0)
- `python pipeline/rules_report.py` on the real LAWS.md/OPEN.md -> exit 1, listing unresolved
  references (e.g. L21 check BAD_LINK, L14 pddl clock_policy, test_laws.py nodes not yet
  collected). Those belong to lanes L1-L6 and the tests lane; no RULES-REPORT.md written
  until they land (fail-closed). Rows with status OPEN/UNSUPPORTED are exempt from resolution.

## Pending
Run `just rules-report` after the other lanes land, then `just rules-report-check`.
