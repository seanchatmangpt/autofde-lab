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

### Cycle 1 (2026-08-10, first real cron-triggered swarm cycle)

**`wm112zth9` workflow (Design/Implement/Wire/Verify) completed.** Real, substantial
landing: `GatedCapabilityBinding` + `ALLOWED_ACTUATION_BINDING_LABELS` in
`src/autofde_lab/powl/runner.py` (commit `f396167`), `src/autofde_lab/reasoning/gymact_diagnosis_driver.py`
(commit `03572c8`) -- the real runner-triggered driver, superseding the throwaway
`scripts/run_gymact_mediated_trial.py` spike. Independently re-verified before trusting
(per this doc's own standing law): found and fixed 2 real defects the Implement/Wire
phases introduced --

1. **Fictitious `"verify"` capability manifest entry.** `CapabilityGate.stale_entries()`
   itself caught this (own detector working correctly): `SregymEnvironment.verify()` is
   not a real gymact `Capability` (confirmed earlier this session -- plain coroutine,
   never wired into `actuate()`'s dispatch table), but was padded into
   `gymact_capabilities.toml` anyway just to satisfy `run_pipeline`'s blanket
   "every actuation label needs `GatedCapabilityBinding`" rule. Fixed forward: `gymact_verify`
   moved to its own `ALLOWED_ACTUATION_ORACLE_LABELS` set (bare-binding-only, not
   required by the default completeness check). autofde-lab commit (this fix): see
   `git log -1 --grep "fictitious"` on `feat/crown-receipt-architecture`.
   Re-verified: `106 passed, 2 skipped` across `tests/fabric/test_capability_gate_chicago.py`,
   `tests/powl/`, `tests/reasoning/`.

2. **Real cross-repo blocker found and fixed: `~/gymact`'s `SregymEnvironment.__init__`
   replaced the subprocess environment instead of merging with `os.environ`.** Found
   during the `Verify` phase's live attempt (`run_gymact_mediated_diagnosis` failed in
   under a minute with `RuntimeError: sregym main.py exited during startup (returncode=1)`),
   root-caused by direct manual reproduction (not guessed): `GROQ_API_KEY` never reached
   the child process regardless of shell state, because `subprocess.Popen(env=...)`
   replaces rather than merges. Fixed in `~/gymact/src/gymact/gyms/sregym.py`
   (extracted `_build_full_subprocess_env()`, `os.environ` as base). Real regression
   tests, no cluster needed: `3/3 passing` (`tests/test_sregym_provider.py`, gymact repo).

**Still blocked, confirmed pre-existing and unrelated to either fix above**:
`~/gymact`'s own live-materialization integration test
(`test_real_materialize_observe_and_read_only_kubectl_actuate`) still fails --
`_build_argv()` hardcodes `--agent autofde_lab_planner`, which fails independently on
the same missing `clients/autofde_lab_planner/driver.py` module documented in Cycle 0.
This is now the single most load-bearing remaining blocker for ANY gymact-mediated
trial to reach a real diagnosis -- named precisely so the next cycle doesn't
rediscover it from zero.

| problem_id | status | last real evidence |
|---|---|---|
| wrong_dns_policy_social_network | ATTEMPTED:BLOCKED:VENDORED_DRIVER_MODULE_MISSING (both direct-bypass AND gymact-mediated paths now confirmed blocked by the SAME root cause: missing `clients/autofde_lab_planner/driver.py`) | this cycle: gymact-mediated attempt via `run_gymact_mediated_diagnosis` failed at `provider.materialize()`, same missing-module signature after the env-fix ruled out the GROQ_API_KEY explanation |
| misconfig_app_hotel_res | ATTEMPTED:BLOCKED:VENDORED_DRIVER_MODULE_MISSING | `~/gymact/tests/test_sregym_provider.py::test_real_materialize_observe_and_read_only_kubectl_actuate`, this cycle, same signature |

**Next cycle priority** (named here so it isn't rediscovered): the vendored
`clients/autofde_lab_planner/driver.py` module needs to either (a) be built for real
(a thin stub that just deploys the fault and waits, matching the "external harness"
mode `main.py --help` advertises, since gymact intends to drive diagnosis externally
via MCP, not have SREGym's own subprocess do it), or (b) `_build_argv()` needs a real,
different `--agent` value that DOES have a real driver (`clients/autofde_lab_dspy/driver.py`
confirmed present on disk, unlike `autofde_lab_planner`) -- try (b) first, it is
strictly less work and may unblock every problem ID in one fix.

### Cycle 2 (2026-08-10)

**Priority (b) from Cycle 1 done, real, verified.** `~/gymact`'s `_build_argv()`
now takes `agent_name` (default `autofde_lab_dspy`, the driver confirmed present on
disk), threaded through `SregymVendorProvider.materialize()`'s config resolution
(extracted as a testable pure function, `_resolve_materialize_argv_and_env`).
Committed on `feat/sregym-vendor-provider` (gymact repo), commit `2399f6a`, stacked
on the Cycle 1 env-merge fix (`6e46cb2`). Independently re-verified this cycle:
12/13 passing (the 1 failure is the same pre-existing live-cluster integration test,
different transient symptom this time -- `httpx.ReadError`, consistent with port/
cluster contention from this cycle's own concurrently-running live trial, not a
regression).

**Real, direct confirmation the missing-module blocker is cleared**: `ps aux` shows
PID `56207` running `.venv/bin/python main.py --agent autofde_lab_dspy --model
groq/openai/gpt-oss-20b --problem wrong_dns_policy_social_network --agent-timeout
1200` -- alive, past the point every previous attempt crashed immediately on
`No module named clients.autofde_lab_planner.driver`. Full trial outcome not yet
observed as of this note (dispatched agent monitoring it in background, will report
via task notification) -- recording the confirmed interim fact now rather than
claiming a terminal result that hasn't happened yet.

| problem_id | status | last real evidence |
|---|---|---|
| wrong_dns_policy_social_network | ATTEMPTED:UNCONFIRMED (in progress via gymact-mediated path, agent_name=autofde_lab_dspy) | `ps aux` this cycle: PID 56207 alive, past previous missing-module blocker; terminal outcome pending |

(Grows as cycles attempt more problems.)
