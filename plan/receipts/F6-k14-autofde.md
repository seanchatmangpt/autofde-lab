# F6-k14-autofde receipt
Standing: PASS

Base: /Users/sac/plan (no git, unhashed). Edited: pipeline/tests/plankinds/k14_autofde.py;
added pipeline/tests/test_k14_crash_class.py.

## Change
- `classify_pddl_exit(rc, stderr)`: a Python traceback maps to status `CRASH` (distinct from
  NO_PLAN rc=1); FOND path likewise. plan_matrix fails closed on any status != expect.
- Current engine no longer crashes on the cyclic-goal case: it prints
  "no plan exists (search exhausted)" rc=1 (pre-existing defect fixed upstream; observed).

## Commands
- pytest pipeline/tests/test_k14_crash_class.py: exit 0, `2 passed` (real subprocess AttributeError).
- Run of all 6 K14 cases: all status==expect (PLAN, NO_PLAN, REFUSED, PLAN, INFEASIBLE, INFEASIBLE).

## Evaluation (read-only)
- ~/autofde-lab: skdecide, autofde_lab_planner packages present; engine/fond_policy already wired;
  no further rules adopted this lane. ~/graphlaw: Rust courts (castle-diff, code-partition);
  no reusable PDDL rule found; not adopted. UNVERIFIED beyond directory listing.
