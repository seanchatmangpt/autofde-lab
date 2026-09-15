# AFDE-2602: GymAct simulator deterministically chooses the `tests_pass` FOND successor

- **Status**: Closed
- **Closed by**: 2026-09-15, `tests/agent/test_autodev_fond_evidence_chicago.py::TestAFDE2602OutcomeOracle`
- **Closure evidence**: outcome selection is now an explicit `outcome_oracle` parameter (`reference` | `adversarial` | `alternate`), threaded through `run_autodev_cycle`; the hidden tests_pass sort bias is removed. Falsifier satisfied: the adversarial oracle reaches `tests_fail`/`test_failing`, and alternate mode visits both declared successors; unknown oracles are refused by contract.

- **Severity**: Medium
- **Standing**: PARTIAL_ALIVE
- **Found by**: 14-hour cross-repo code review, window 2026-09-14 9:40 PM → 2026-09-15 11:40 AM PDT (inspection, not execution)

## Evidence

`run_tests` is correctly represented as a nondeterministic FOND action with pass and fail outcomes. But the GymAct simulation sorts transitions so the outcome containing `tests_pass` is deliberately chosen first.

The nondeterministic edges therefore exist syntactically, but the fail successor is unreachable under the simulator's transition policy.

## Impact

For a FOND system this is particularly important: the planner declares uncertainty the simulator refuses to produce, so any strong-cyclic / strong-plan claim is validated against a strictly easier environment than the domain model asserts. Ranked #4 in the cross-repo closure order (paired with AFDE-2601).

## Fix

Remove the outcome sort-bias and either make transition selection genuinely nondeterministic or explicitly parameterize an outcome oracle (random and adversarial modes) used by simulation and evaluation.

## Falsifier (acceptance)

Repeated/adversarial execution of `run_tests` must make **both** declared FOND successors reachable — or the outcome oracle must be an explicit, documented parameter rather than a hidden deterministic preference.
