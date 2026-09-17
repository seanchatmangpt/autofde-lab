# v26.9.15 — autofde-lab: FOND simulator semantics + exact-head receipt invalidation

- **Date**: 2026-09-15
- **Source**: 14-hour cross-repo code review, window Sep 14 9:40 PM PDT → Sep 15 11:40 AM PDT.
- **Method**: inspection of commits, PR heads, and exact source files. No code executed, nothing changed by the reviewer.

## Result

Substantial closure work landed in the window: counterfactual OCEL validation, alternate process libraries, OPQL/Ocelescope, a closed-loop auto-dev layer, formal CMCA work, and exact-head qualification repair.

Two specific defects exist in the auto-dev domain, and together they are contradictory:

- **past uncertainty is over-retained**: one old CI failure poisons the initial state forever (`extract_initial_product_state` matches `"fail"` anywhere in the historical OCEL log);
- **future uncertainty is under-retained**: `run_tests` is declared as a nondeterministic FOND action, but the GymAct simulation sorts transitions so the `tests_pass` successor is always chosen — the fail edge is unreachable under the simulator's transition policy.

The exact-head evidence handling failure and recovery during the window (stale capstone receipt re-anchored from a previously green SHA to current head) should be encoded as permanent machinery so the episode cannot recur.

## Tickets

| ID                                                                              | Title                                                                                                    | Severity | Closure order |
| ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | -------- | ------------- |
| [AFDE-2601](./AFDE-2601-fond-initial-state-latest-evidence.md)                  | `extract_initial_product_state` makes historical failure sticky — state not derived from latest evidence  | Medium   | #4            |
| [AFDE-2602](./AFDE-2602-fond-run-tests-adversarial-outcomes.md)                | GymAct simulator deterministically chooses the `tests_pass` FOND successor                               | Medium   | #4            |
| [AFDE-2603](./AFDE-2603-exact-head-receipt-invalidation.md)                    | Encode exact-head receipt invalidation as machinery (stale-SHA episode)                                  | Medium   | #6            |
