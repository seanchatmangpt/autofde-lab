# POWL-runner-mediated SREGym actuation — running progress ledger

Started 2026-08-09 late evening, autonomous 30-min swarm loop, per explicit user
instruction: continue until the POWL runner can actuate through all possible
SREGym challenges (real trials, real OCEL evidence, real CONFIRMED/DISPUTED
verdicts) without asking questions or stopping between cycles.

**Standing law applies**: every row below is `ALIVE` only with a real command
run this session, real output quoted. No row is upgraded to ALIVE by design,
connection, or a plausible-sounding agent report alone — independently
re-verify (real pytest run, real grep) before recording ALIVE.

## Branch
`feat/crown-receipt-architecture` (see session history: this superseded
`feat/sregym-dspy-pipeline` mid-session after a concurrent branch switch;
all real work lives here now).

## Cycle log

(Each cycle appends one dated section below. Never overwrite a prior entry —
if a prior claim is wrong, add a retraction next to it, per docs/CLAUDE.md's
"historical corrections stay visible" invariant.)

### Cycle 0 (bootstrap, pre-loop)
- Real components landed and independently re-verified this session: scanner,
  φ, dispatch, POWL runner (structural), turtle/soundness bridges, capability
  gate, case_library outcome predicate, dead-end guard, node-affinity fix.
- `wm112zth9` workflow in flight: implementing capability-gated actuation
  bindings in runner.py + a real gymact_diagnosis_driver.py + one live
  verification run.
- Real problem list (~90 IDs) enumerated from a live `main.py` argparse error
  this session -- this is the actual target set "all possible sregym
  challenges" refers to. Not yet attempted: any of them through the
  runner-mediated path (only the direct-bypass main.py path has been tried
  live, twice, for `wrong_dns_policy_social_network`).

## Per-problem status table

(One row per real SREGym problem ID. Status vocabulary: `UNATTEMPTED` /
`ATTEMPTED:BLOCKED:<reason>` / `ATTEMPTED:CONFIRMED` /
`ATTEMPTED:DISPUTED` / `ATTEMPTED:UNCONFIRMED`. Never write CONFIRMED without
a quoted real run this session.)

| problem_id | status | last real evidence |
|---|---|---|
| wrong_dns_policy_social_network | ATTEMPTED:BLOCKED:VENDORED_DRIVER_MODULE_MISSING (direct-bypass main.py path only; runner-mediated path not yet attempted) | `/tmp/real_trial_output3.log`: full env+fault+app deploy succeeded for real (23:48-00:01, ~13min), but `.venv/bin/python: No module named clients.autofde_lab_planner.driver` — the vendored SREGym client for `--agent autofde_lab_planner` has no driver.py at all. `results={}`, exit code 1, empty CSV. This is a genuine absence, not a logic bug -- confirms the direct-bypass path is broken independent of this session's work, and is further reason to complete the gymact-mediated `gymact_diagnosis_driver.py` path instead of repairing this dead vendored file. |

### Cycle 0 addendum (2026-08-10, still pre-loop)
Node-affinity fix (real, `kubectl label node colima node-role.kubernetes.io/control-plane=""`)
fully confirmed working end-to-end this cycle: a full second trial attempt cleared every
deploy stage that failed twice before. The remaining blocker is unrelated to that fix --
it's the vendored `clients/autofde_lab_planner/driver.py` being absent, on the OLD
bypass path this session's redesign was already moving away from.

(Grows as cycles attempt more problems.)
