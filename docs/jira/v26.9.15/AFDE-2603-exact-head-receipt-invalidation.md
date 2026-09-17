# AFDE-2603: Encode exact-head receipt invalidation as machinery (stale-SHA episode)

- **Status**: Closed
- **Closed by**: 2026-09-15, `src/autofde_lab/agent/receipt_qualification.py` + `tests/agent/test_receipt_qualification_guard_chicago.py` (wired into the PR qualification gate's crown kernel list)
- **Closure evidence**: mechanical rule `qualified_head != current_head AND unbound current-standing claim => REFUSED_STALE_QUALIFICATION` with the mismatch surfaced in the verdict detail; head-bound point-in-time claims grade EXPIRED (lawful history). Falsifier satisfied: the stale-SHA fixture is refused automatically, and the repo-wide compliance test runs on every PR.

- **Severity**: Medium
- **Found by**: 14-hour cross-repo code review, window 2026-09-14 9:40 PM → 2026-09-15 11:40 AM PDT (inspection, not execution)

## Evidence

A real evidence-discipline failure and recovery occurred in this window:

1. The capstone receipt remained anchored to a previously green SHA while **five later feature commits** accumulated.
2. Three checks then failed at `3755bf0`.
3. Subsequent commits fixed Python-version dependency markers, pinned the formatter, and re-anchored the evidence to current head `1605cfc…`.
4. Current-head check results inspected during the review were success/skip rather than the stale green claim.

## Impact

The episode is a machine-experience rule worth retaining permanently:

> **A receipt's qualification expires whenever the subject SHA moves.**

A document with `qualified_head != current_head` must not be able to express current `ALIVE`. Ranked #6 in the cross-repo closure order — encode it as machinery so this episode cannot recur, in this repo and wherever capstone/evidence receipts are consumed.

## Fix

Add an enforced guard (check/gate) that invalidates or downgrades a receipt's standing whenever the subject's current SHA differs from the receipt's `qualified_head` — mechanically, not by prose convention.

## Falsifier (acceptance)

Commit any change on top of a qualified receipt without re-qualifying it; the receipt's current-standing claim must be refused/downgraded automatically by the guard, with the mismatch surfaced (not silently retained as green).
