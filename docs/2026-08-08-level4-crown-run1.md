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

## Attempts 6 and 7 (task C rerun, same frozen crown)

Manifest re-verified, **not** re-frozen:
`load_crown(docs/evidence/crown1/crown_manifest.json)` recomputed digest
`64121fbac6f4cfe29b0b68bf138c9c3f2f7d466dc61294bdde9772947587c7de`,
denominator `10`. `verify_manifest` returned `MANIFEST_VIOLATIONS: []` on both
attempts: all 10 frozen seeds executed, none dropped, reordered, or substituted.

### Attempt 6 — UNSCOREABLE (harness defect in the driver, not the product)

The driver serialized each `TrialReport` via `rep.__dict__` instead of
`rep.to_row()`, so the `Standing` object reached the scoreboard as a repr
*string*. Every row scored `UNKNOWN`. Reported for completeness as `0/10`,
`{UNKNOWN: 10}` — and it is unscoreable, not proven-failed, exactly as
attempts 1-3 were. Evidence retained at `docs/evidence/crown1/attempt6/`.

A second, real harness defect surfaced first: `Level4GymActBridge` writes its
`bridge.py` to `evidence_dir / "bridge.py"` but launches the subprocess with
`cwd=/Users/sac/gymact` (`level4_gymact_bridge.py:296,426`). A **relative**
evidence root therefore resolves against the gymact checkout and every trial
dies with `can't open file '/Users/sac/gymact/docs/evidence/...'`. Absolute
evidence roots are load-bearing and nothing enforces that.

### Attempt 7 — the first scoreable rerun: **2/10**

| # | seed | provider | outcome | verdict | standing |
|---|---|---|---|---|---|
| 1 | 890266799 | cube_counter | NO_TYPED_VALID_PLAN | UNKNOWN | UnknownEvidence |
| 2 | 4064909771 | switchboard | NO_TYPED_VALID_PLAN | UNKNOWN | UnknownEvidence |
| 3 | 3979297810 | resource_flow | EXECUTED | **ALIVE** | Level4AliveEvidence |
| 4 | 1811868735 | lock_and_key | NO_TYPED_VALID_PLAN | UNKNOWN | UnknownEvidence |
| 5 | 1635849486 | cube_container_counter | NO_TYPED_VALID_PLAN | UNKNOWN | UnknownEvidence |
| 6 | 1645242857 | cube_counter | NO_TYPED_VALID_PLAN | UNKNOWN | UnknownEvidence |
| 7 | 1327771368 | switchboard | NO_TYPED_VALID_PLAN | UNKNOWN | UnknownEvidence |
| 8 | 663999732 | resource_flow | EXECUTED | **ALIVE** | Level4AliveEvidence |
| 9 | 1382812562 | lock_and_key | EXECUTED | **NOT_ALIVE** | ConformantButGoalUnmetEvidence |
| 10 | 69813132 | cube_container_counter | NO_TYPED_VALID_PLAN | UNKNOWN | UnknownEvidence |

`REAL_ALIVE: 2/10`, distribution `{UNKNOWN: 7, ALIVE: 2, NOT_ALIVE: 1}`.
**Down from attempts 4-5's 3/10.** The number is reported as measured.

### Alive-in-order, every attempt

```text
attempt 1: 8/10 reported -> FALSE_GREEN, rescored 0/10 UNSCOREABLE
attempt 2: 5/10 reported -> FALSE_GREEN, rescored 0/10 UNSCOREABLE
attempt 3: 5/10 reported -> FALSE_GREEN, rescored 0/10 UNSCOREABLE
attempt 4: 3/10  (first legitimately scoreable)
attempt 5: 3/10
attempt 6: UNSCOREABLE (driver serialized Standing as a repr string)
attempt 7: 2/10   {UNKNOWN: 7, ALIVE: 2, NOT_ALIVE: 1}
```

### REPLAY really ran on the executed trials

Not absence-read-as-clean — the real `ReplayReport` inside each standing:

```text
seed 3979297810: EVIDENCE_REPLAY valid=True record_count=9 mismatches=[]
                 head=d0ab3e7eca1c14eb3b1f42020eeda8337e59ed62015a6835925159bd9c65096e
                 conformance conformant=True deviations=[]  goal.passed=True
seed 663999732:  EVIDENCE_REPLAY valid=True record_count=3 mismatches=[]
seed 1382812562: EVIDENCE_REPLAY valid=True record_count=7 mismatches=[]  goal.passed=False
```

Seed 1382812562 is the load-bearing one: a *clean, replay-valid, conformant*
episode whose real goal was not attained. `NOT_ALIVE`, not `UNKNOWN` — the
process was checked and the goal was checked and failed.

### The 4 counter seeds: NO_APPLICABLE_ACTION_DISCOVERED is gone

Verified, not assumed. The authority fix recovered discovery: every counter
seed now probes real actions (`n_probes` 4-6 on the counter providers, 12 on
switchboard/lock_and_key) and no trial reports
`NO_APPLICABLE_ACTION_DISCOVERED` anywhere in attempt 7. The blocker moved one
transition downstream to `NO_TYPED_VALID_PLAN`.

### Per-failed-seed classification

All seven `UNKNOWN` rows fail at the **same transition**: typed model -> valid
plan. `unsound_candidates_rejected: 0` and `planners_producing_candidates: []`
with `n_planner_attempts: 49`, `n_supported_solvers: 49` — the 49 federated
planners produced **zero** candidates, so nothing even reached the typed gate.
This is not the "federation proposes, gate rejects" failure recorded earlier;
it is upstream of that.

* seeds 890266799, 1645242857 (cube_counter), 1635849486, 69813132
  (cube_container_counter) — **representational**. `typed_derived_dimensions:
  ['counter']`: the goal dimension is *derived*, so under the self-inverse rule
  no action may claim it, and no action-set can be assembled that provably
  reaches `counter == target`. Same class as the known switchboard failure,
  now generalized to the counter providers. Also carries a named loss:
  `reward: UNREPRESENTABLE:CONTINUOUS_DIMENSION_HAS_NO_SOUND_PROPOSITIONAL_ENCODING`.
* seeds 4064909771, 1327771368 (switchboard) — **representational**, the
  already-recorded failure: `typed_derived_dimensions: ['required_on',
  'toggles']`, `required_on` a count derived from self-inverse booleans. Needs
  derived-dimension inference, never a weakened rule.
* seed 1811868735 (lock_and_key) — **representational**, unchanged: the
  relational precondition `held_key == perm[locks_open]` is not expressible in
  the induced model (`typed_derived_dimensions: []`, no loss recorded, so the
  model is silently too weak rather than refusing). Seed 1382812562 on the same
  provider does get a plan and executes, so the machinery works at depth 2 —
  this is a depth-3 representational gap, not a dead provider.
* seed 1382812562 (lock_and_key, `NOT_ALIVE`) — **product**. Plan
  `('force_latch', 'pick_key[key=1]', 'open_lock')` executed with
  `step_standings ('ALIVE', 'REFUSED', 'REFUSED')`; final state `locks_open: 1`
  of `depth: 2`, `rack_jammed: True`. The committed plan's first action jammed
  the rack, and the model did not predict that effect.

### Second finding: the two scoring paths disagree (dual bookkeeping)

Same attempt-7 rows, two paths, two answers:

```text
REAL_ALIVE (TrialReport.verdict):    2/10   {UNKNOWN: 7, ALIVE: 2, NOT_ALIVE: 1}
ROW_PATH   (runner _row_is_alive):   0/10   {UNKNOWN: 10}
```

`CrownAttempt.alive_count` (`level4_crown_runner.py:360`) scores through
`_row_is_alive` -> `conjunction_from_row` -> `factors_from_row`, which
reconstructs from `real_goal_attained` / `independently_verified` /
`ocel_valid` / `replay_ran` / `replay_valid` or a `crown_factors` list.
The current `TrialReport.to_row()` emits **none of those keys** — the
`Standing` split replaced them — so `factors_from_row` takes its legacy branch
and returns `UNKNOWN` for every factor of every current-era row. The persisted
scoreboard therefore reads `0/10` on a run that genuinely produced two
`Level4AliveEvidence` trials.

Fail-closed, so it is not a false green — but it is exactly the dual
bookkeeping `.claude/rules/no-dual-bookkeeping.md` bans: standing computed
twice, from two representations, with the durable one now structurally unable
to observe a pass. Reported, not repaired here: `level4_crown_runner.py` and
`crown_factor.py` are owned by other tasks in this workflow.

Evidence: `docs/evidence/crown1/attempt7/` (10 trial dirs, `crown_run.json`,
`verdicts.json`), `docs/evidence/crown1/attempt6/`.
