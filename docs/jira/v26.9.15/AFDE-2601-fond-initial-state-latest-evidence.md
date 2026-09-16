# AFDE-2601: `extract_initial_product_state` makes historical failure sticky — state not derived from latest evidence

- **Status**: Closed
- **Closed by**: 2026-09-15, `tests/agent/test_autodev_fond_evidence_chicago.py::TestAFDE2601LatestEvidence`
- **Closure evidence**: `extract_initial_product_state` now derives `test_failing` from the latest `ci_verification_*` event by `timestamp_ns` (stable log-order tie-break); an old failure followed by a green verification yields `repo_clean`. 4 falsifier tests green, including timestamp-ordering and no-evidence cases.

- **Severity**: Medium
- **Standing**: PARTIAL_ALIVE
- **Found by**: 14-hour cross-repo code review, window 2026-09-14 9:40 PM → 2026-09-15 11:40 AM PDT (inspection, not execution)

## Evidence

`extract_initial_product_state` documents the rule as approximately:

> recent CI verification failed → `test_failing`

but implements:

```python
if any("fail" in a.lower() for a in activities):
    facts.add("test_failing")
```

So a failure **anywhere** in the historical OCEL log wins forever, even if followed by successful verification.

## Impact

One old failure poisons the initial state of every subsequent planning episode — past uncertainty is over-retained (and, combined with AFDE-2602, the system simultaneously under-retains future uncertainty). Ranked #4 in the cross-repo closure order.

## Fix

Derive `test_failing` from the **latest relevant verification evidence** for the subject (most recent CI/test event), not from existence-anywhere in the event history.

## Falsifier (acceptance)

A `fail → pass` event history must initialize `repo_clean`, not `test_failing`.
