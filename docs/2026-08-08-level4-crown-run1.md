# Level 4 crown run 1 — 8/10, then a repair that regressed to 5/10

`technicalStanding` only. `organizationalStanding` is `UNKNOWN` — nothing here computes it.

## Result: the crown is NOT complete

| Attempt | Score | Note |
|---|---|---|
| 1 | **8/10 ALIVE** | baseline, no repair applied |
| 2 | **5/10 ALIVE** | after repair — **regressed** |
| 3 | **5/10 ALIVE** | after further repair — still regressed |

`CrownRun.is_complete()` → `False`. The target is 10/10; the best observed is 8/10,
and it was not the last attempt. Every attempt is retained
(`docs/evidence/crown1/crown_run.json`) precisely so this cannot be reported as
"8/10 on the first try" with the regression dropped.

- Frozen denominator: **10**, unchanged across all three attempts.
- Manifest digest: `64121fbac6f4cfe29b0b68bf138c9c3f2f7d466dc61294bdde9772947587c7de`,
  re-verified by `load_crown` after every attempt.
- `verify_manifest` violations: `[]` on every attempt — no seed suppressed, none
  added, denominator never changed.
- Seeds drawn from OS entropy after the harness started.

## The regression is the headline finding

Attempt 1 failed only on the two `lock_and_key` seeds
(`1811868735`, `1382812562`), both `NO_TYPED_VALID_PLAN`. The repair aimed at
`lock_and_key` **broke `switchboard` and `resource_flow`**, which had been ALIVE:

| Provider | Seed | A1 | A2 | A3 |
|---|---|---|---|---|
| cube_counter | 890266799 | ALIVE | ALIVE | ALIVE |
| switchboard | 4064909771 | ALIVE | **NOT** | **NOT** |
| resource_flow | 3979297810 | ALIVE | **NOT** | **NOT** |
| lock_and_key | 1811868735 | NOT | NOT | NOT |
| cube_container_counter | 1635849486 | ALIVE | ALIVE | ALIVE |
| cube_counter | 1645242857 | ALIVE | ALIVE | ALIVE |
| switchboard | 1327771368 | ALIVE | **NOT** | **NOT** |
| resource_flow | 663999732 | ALIVE | ALIVE | ALIVE |
| lock_and_key | 1382812562 | NOT | NOT | NOT |
| cube_container_counter | 69813132 | ALIVE | ALIVE | ALIVE |

Two distinct failure signatures:

- `NO_TYPED_VALID_PLAN` — the typed model admits no plan reaching the goal. On
  `lock_and_key` this is expected-if-unrepaired: the provider hides a seeded
  key→lock permutation that passive probing cannot recover, and `force_latch`
  advances the chain while permanently jamming the rack, so a greedy prober can
  reach a state from which the goal is unreachable.
- `EXECUTED` with `real_goal_attained=False` — a plan was committed and actuated,
  the per-step consequences were independently observed, and the **goal was still
  not reached**. In attempt 3 `switchboard`/`resource_flow` show
  `independently_verified=True` alongside `real_goal_attained=False`. That pair is
  the whole point of separating the two fields: per-step verification passing is
  not goal attainment, and a crown that scored on the former alone would have read
  10/10 here while the world was in the wrong state.

## What this does not claim

- Not 10/10. Not "close to" 10/10. The last attempt scored 5/10.
- `lock_and_key` has never passed on either seed, in any attempt.
- The planner federation contributed **zero** committed plans on the counter
  providers: all 49 planners plan over the propositionalized `Recipe` built from
  the *untyped* model, and the typed gate correctly rejects their output
  (`unsound_candidates_rejected: 30` on a real cube_counter trial). The federation
  is currently evidence, not a plan source. Closing that needs the typed model
  projected into the planning representation, which is not done.

## See also

- `docs/evidence/crown1/crown_manifest.json`, `docs/evidence/crown1/crown_run.json`
- `docs/2026-08-08-level4-crown-progress.md`
- `docs/level4-discovery-architecture.md`
- `docs/STATUS.md`

## CORRECTION (same day): all three attempts are UNSCOREABLE, not 8/10 and 5/10

An adversarial audit of the evidence chain found the `REPLAY` factor was
**never verified in any attempt**. Three independent mechanisms let an
unverified replay read as green:

1. **The verdict field was never read.** The code did
   `getattr(rep, "admitted", None)`, but `gymact.replay.ReplayReport` has no
   `admitted` field — its verdict is `valid`. The expression returned `None`
   unconditionally. (Verified upstream: `ReplayReport.model_fields` contains
   `valid`, not `admitted`.)
2. **An exception made the gate pass.** On any raise the bridge returned
   `{"error": ...}` with no `mismatches` key; the caller's
   `.get("mismatches", [])` then produced `[]` and the conjunction passed. A
   replay that never ran was indistinguishable from one that verified, and
   the error string was dropped before reaching the durable record.
3. **`not row.get("replay_mismatches")` is true for a missing key**, so a row
   that never wrote the field at all scored ALIVE. `ocel_valid` was computed
   fail-closed and then omitted from the verdict entirely.

Re-scoring the real recorded rows under the corrected conjunction:

```text
attempt 1: reported 8/10  ->  0/10
attempt 2: reported 5/10  ->  0/10
attempt 3: reported 5/10  ->  0/10
```

**The precise reading — 0/10 means unscoreable, not proven-failed.** The
actuation and real goal attainment in attempt 1 genuinely happened: 8 trials
really reached their goal in the real world, independently verified per step.
What was never attested is REPLAY, and REPLAY is a conjunct of the acceptance
equation. So the correct standing for crown run 1 is `UNKNOWN` on every
trial, not `ALIVE` on 8 and not `BUILD_BROKEN`. **No valid Level 4 score has
been produced yet.**

Fixed forward (`is_alive`/`_row_is_alive` now require `replay_ran`,
`replay_valid`, `ocel_valid`, and present-and-empty collections; the bridge
reads `rep.valid` and fails closed on exception, persisting `replay_error`).
Five falsifiers pin each mechanism, including one that asserts upstream's
`ReplayReport` still has no `admitted` field so this cannot silently regress.

Crown run 1's attempt-1 evidence directories are copied into
`docs/evidence/crown1/attempt1/` so `DURABLE_RECEIPT` no longer depends on a
`/private/tmp` scratchpad surviving.
