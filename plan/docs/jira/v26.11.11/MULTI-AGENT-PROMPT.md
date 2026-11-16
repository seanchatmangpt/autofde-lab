# docs/jira/v26.11.11 — Multi-agent prompt: lock 18 laws, test 11 thresholds

Standing: UNVERIFIED

## Contract (identical in every lane prompt)
- Repo: /Users/sac/plan, one canonical checkout. No worktrees, no stash, no git state commands
  in lanes. The coordinator owns commits and stages explicit paths only.
- Each lane owns disjoint files (table below) and writes `docs/jira/v26.11.11/receipts/<lane>.md`
  with `Standing:` on line 2 (ALIVE | PARTIAL | PASS | BLOCKED | UNVERIFIED), the exact SHA of the
  tree it ran on, commands, exit codes and real output.
- Chicago style: real Chromium, real solvers, real store. No mocks, no sleeps (bounded polls).
- Values come from factory_boy and TOML envelopes. No literals in test code.
- Wave 1 is read-only. Courts decide, not pre-thinking.

## Inputs
- /Users/sac/tony.txt (transcript, with line refs)
- CLAIMS-VS-CODE.pdf and the S-nn audit IDs (read them; do not trust this prompt's summary)
- docs/jira/v26.11.11/LAWS.md (bucket A) and OPEN.md (bucket B), written by lane L0

## Wave 0 — L0: ledger of laws
Write LAWS.md (18 rows: id, law, transcript quote with line number, affected files, test that
will pin it) and OPEN.md (11 rows: question, option A, option B, default, owner = Tony|Vince).
Every law must cite a transcript line. A law with no citation moves to OPEN.md.

## Wave 1 — lock the 18 laws (parallel lanes)
| Lane | Laws | Owns |
|---|---|---|
| L1 dispatch | #1 filter dim validated against the 10-dim set; #2 site clash excludes the site only, global ban separate; #4 nobody eligible hands off to the coordinator | store.py check, align.py, tests |
| L2 territory | #6 primary out-of-coverage still plans and emits a sales flag; #7 automatic sales-rep notification event; #9 secondary requires parent, or a `quick_add` marker | store.py, staged.py, mega_factories.py |
| L3 compliance | #10 expired document stored, dispatch vetoed when expiry <= clock; #13 interactive photo prompt on upload plus QA at closeout | align.py, console.py |
| L4 time and lineage | #14 external clock = quote, internal clock = reality; #19 multi-visit and multi-provider; #21 change order and recall link to the original | store.py, staged.py, PDDL |
| L5 roles | #23 multiple roles per person; #24 super user all, entity lead per client | avatar_roster.toml, console.py |
| L6 multi-entity | #25 remove `SINGLE_ENTITY_STORE`; multiple entities and DBAs | store.py reducer and all consumers |
| L7 deliverable | #28 Monday rules report; #29 flow Entity → Client → Vendor → Work Order → Dispatch | docs, test_vince_continuum_mega.py |

L6 touches shared reducer code. Run it first, inside a compile-freeze SLA of 10 minutes.
After it lands, every other lane rebases its edits onto the new reducer by re-reading the file.

## Wave 2 — the 11 open thresholds
One lane per question that has a testable default (#5, #3, #8, #11, #12, #15, #17, #16, #18, #20,
#26/#27). Each lane encodes BOTH options as a TOML switch and writes a differential court that
runs the same factory scenario under A and B, then records the divergence as a `KD-nn` row.
No option is chosen by a lane. The coordinator sends OPEN.md to Tony and Vince.

## Gall checkpoints
A checkpoint is a gate that must be green before the next ring starts. A failing gate stops the
wave; the owner reverts or fixes within 10 minutes.

- G0 (before any lane): `just check` and `just ui-chicago` PASS on the starting SHA. Record the
  SHA and output in `receipts/G0.md`. A red baseline blocks everything.
- G1 (after L6, multi-entity): the existing 8-plan suite (`just ui-jtbd-scenarios`) still gives
  4 pass / 4 fail with the same gates. If not, L6 broke the working kernel; revert.
- G2 (after each lane, before the next merges): the lane's own tests pass and G1 still holds.
  Cheapest-first order: store tests, solver tests, one real-browser plan.
- G3 (after Wave 1): the Vince continuum runs end to end in real Chromium. Expected result
  changes with #6: CVS out-of-coverage now plans, so the per-work-order table is re-derived from
  LAWS.md, not carried over from the old expectations.
- G4 (anti-vacuity): flip one trait for each law (for example remove the parent on a secondary
  client). The named test must go red. A law whose test cannot fail is rejected.
- G5 (before the report): grep for literals and sleeps over new files; `just check` PASS; seed
  replay gives identical plans. Receipts are re-read from disk at fill time, never from memory.

## Exit
A coordinator receipt: subject SHA, lanes and standings (re-read from receipts), diff, commands
and exit codes, gate results G0–G5, open KD rows, and the 11 questions still waiting on Tony and Vince.
