# gate-8plan receipt
Standing: BLOCKED

Subject: /Users/sac/plan on-disk state (non-git dir; no SHA). RUN-ONLY lane; no source edited.

## Commands and exits
1. `just --justfile justfile.d/45-ui.just ui-jtbd-scenarios` (cwd plan): rc=5, "no tests ran"
   (INFRA: with --justfile the recipe cwd is justfile.d/, so pipeline/tests/... paths miss).
   Same for ui-chicago (rc=4, file not found).
2. Re-run with `--working-directory /Users/sac/plan`:
   - ui-jtbd-scenarios: rc=1, `7 failed, 1 passed in 298.46s` (expected 4 pass / 4 refused)
   - ui-chicago: rc=1, `1 failed, 1 passed in 36.57s`
     (FAILED test_chicago_visual_blank_slate_to_settlement, seed=117623734)

## Failures
- jtbd: refuse_then_flip, two_providers, no_part: `TimeoutError: poll timed out: event client not
  recorded` at plan step 8 (ui_driver.py:203 submit). withhold_tag, attest_mismatch, nte_below_charge,
  expired_coi: ANTI-VACUITY (expected fail, passed) wrapping the same step-8 client failure.
  Only part_with_tag passed.
- chicago: identical `event client not recorded` (ui_driver.py:203, via line 277 S(b,"client")).

## Root cause (reproduced without browser)
store.append("client", kind=secondary_client, no parent) -> Refused NO_PARENT[...]
(store.py:~290). primary_client x all 3 channels: ok. Factories draw kind by
`rg().choice(store.subtypes("client"))` (jtbd_factories.py:204; ui_driver.py:85) with no parent field,
so the secondary_client draw is refused and no event is written.

## Owner classification
- TEST (primary): jtbd_factories.py:204 / ui_driver.py:85 / ui_plan form for client must pick
  primary_client or supply a parent (secondary needs a prior primary + parent select).
- O-store: NO_PARENT / entity rules arrived with the R2 multi-entity edits (law is plausible; not a store bug
  unless dials say secondary needs no parent).
- Not attributable: O-stagedalign, O-console, O-ledger-pddl, O-dials (never reached; step 8 of ~35).
Pre-existing vs introduced: UNVERIFIED (no git baseline run).
