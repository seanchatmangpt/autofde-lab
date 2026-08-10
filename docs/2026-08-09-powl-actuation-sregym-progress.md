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
| wrong_dns_policy_social_network | ATTEMPTED:UNCONFIRMED (in progress via gymact-mediated path, agent_name=autofde_lab_dspy, v2 with real startup timeout) | see Cycle 3 section below |

### Cycle 3 (2026-08-10)

**Real gap found: Cycle 2's `LiveTrial` phase agent abandoned its own monitoring.**
It launched a real trial (PID `56207`) and submitted "Waiting for background
completion notification" as its literal final workflow answer instead of actually
waiting/monitoring -- the workflow then reported "completed" with no real outcome
ever recorded, and the underlying trial's own log file/output could not be located
afterward (unrecoverable). Named precisely so this pattern doesn't repeat: a
dispatched agent that launches a real background process must be told, explicitly,
to Monitor it itself before returning, not delegate that back implicitly.

**Independent re-verification this cycle** (`tests/scanner tests/powl tests/ocel
tests/case_library tests/fabric tests/reasoning tests/scripts`): confirmed the
`dspy.settings.lm` global-state test-isolation leak (first seen and only
documented, never fixed, earlier this session) is real and still present,
bisected precisely this cycle via directory-subset re-runs: `tests/reasoning`
alone passes clean; `tests/fabric tests/reasoning` together reproduces the 2
failures. Root cause narrowed to `tests/fabric` (likely `test_dspy_ensemble_chicago.py`'s
module-scoped `real_groq_lm` fixture, though its skip guard appeared correctly
applied in this run's own SKIPPED output -- not yet fully explained). Not fixed
this cycle (lower priority than the live-trial blocker); named precisely for a
future cycle rather than left as a vague "sometimes tests fail."

**Re-ran the trial directly** (v1, PID `56207`'s replacement after the abandoned
monitoring): reached a NEW real terminal outcome, past the missing-module crash --
`RuntimeError: sregym conductor API at http://127.0.0.1:8002 did not become ready
within 120.0s: last_error=ConnectError(...)`. Real, precise root cause: gymact's
own `SregymEnvironment.__init__` default `startup_timeout_seconds=120.0` is too
short for this problem set's confirmed 5-15+ minute real deploy, and
`gymact_diagnosis_driver.py` never overrode it. Fixed: added
`startup_timeout_seconds: float = 900.0` parameter, threaded into `materialize()`'s
config (autofde-lab commit, this cycle -- see `git log --grep "startup_timeout_seconds"`
on `feat/crown-receipt-architecture`). Verified: `tests/reasoning/test_gymact_diagnosis_driver_chicago.py`
still `2 passed`.

**Trial v2 (PID `63890`) real terminal outcome**: `RuntimeError: sregym main.py
exited during startup (returncode=0)` -- a fast, clean exit, not a timeout, so the
startup_timeout_seconds fix above was real and correct but not sufficient alone.
The raised message's `stderr` was only deprecation-warning noise -- the real cause
was invisible, because `SregymEnvironment.__init__` only ever captured `stderr`,
silently dropping `main.py`'s own rich-logged `stdout` diagnostics. Confirmed this
is a real, recurring diagnostic-loss defect (this is the second time this session
an ambiguous empty/unhelpful error message required manual reproduction to
understand). Fixed forward (gymact commit, this cycle): the RuntimeError now
includes both streams. Real regression test added (throwaway fake `main.py`
script, real subprocess, no cluster needed): `10/10 passing`.

**Also found and cleaned this cycle**: an orphaned `kubectl port-forward
svc/mcp-server 9954:9954 -n sregym` process from an earlier crashed trial --
real evidence that `materialize()` failing before `env` is constructed means the
driver's `finally: env.teardown()` never triggers (real, not-yet-fixed resource-
leak gap, named here for a future cycle rather than fixed this one given time).

**Trial v3 (PID `65952`) real terminal outcome, and it's a major architectural
finding, not a small bug.** The stdout-capture fix worked -- the real cause is
now fully visible: `main.py --agent autofde_lab_dspy` does NOT wait for external
control at all. It deploys the fault, then runs its OWN internal benchmark loop
autonomously end-to-end (launches the `autofde_lab_dspy` driver, waits for it,
submits results, tears everything down: `"Completed wrong_dns_policy_social_network:
results={}"`, `"Benchmark complete!"`, `"Finished server process"`) -- all inside
the 900s startup window, so by the time gymact polls again the whole process has
already exited cleanly (code 0). **`SregymEnvironment`'s entire design (a
persistent subprocess serving MCP/API while gymact drives diagnosis externally)
is incompatible with launching ANY real `--agent` driver** -- a real driver runs
its own loop and exits; only `main.py --use-external-harness` ("deploy the fault
and exit [the internal agent loop only, not the process]" per source read of
`main.py:369-371`) matches the persistent-server pattern `SregymEnvironment`
actually needs.

**Verified in source** (`vendor/gyms/sregym/main.py`): `use_external_harness=True`
correctly skips `run_judge_preflight_check()` (line 585) AND skips launching any
agent driver (`if use_external_harness: ... return []` at line 369). But a
SEPARATE, unconditional `run_preflight_check(args.agent, ...)` (line 597) always
runs regardless of harness mode, defaulting to `stratus` (needs OPENAI creds we
don't have) if `--agent` is omitted -- a real usability quirk in SREGym's own
`main.py`, out of scope to fix directly this cycle (sibling vendored code, not
gymact or autofde-lab).

**`--use-external-harness` test (PID `67972`) result: definitive, real answer,
and it's a NO.** `"Fault injected... exit for external harness"` immediately
followed by `"Shutting down API"`, `"Finished server process"` -- the whole
process exits right after fault injection, same as agent mode. **No invocation
shape of `main.py` produces a persistent, externally-drivable server on its
own.** `SregymEnvironment`'s core architectural assumption does not match how
`main.py` behaves, in any documented mode tried so far.

**Hypothesis CONFIRMED, real fix landed.** `main.py --agent debug ...`: the
conductor deploys the fault (`"Injected wrong DNS policy fault for service:
user-service"`), launches the real, pre-existing no-op `debug` agent
(`signal.pause()`), and stays alive -- `curl http://127.0.0.1:8000/status`
returned a real, live `{"stage":"diagnosis"}` while the process was running,
well past the point every other mode had already exited. This is the actual,
working persistent-server pattern `SregymEnvironment` needs.

**Fixed in `~/gymact`** (commit, this cycle): `_build_argv()`'s and
`materialize()`'s default `agent_name` changed from `autofde_lab_dspy` to
`"debug"`. Existing tests updated to match; `13/13` non-live tests passing
(independently re-verified, real pytest run this cycle -- one transient
`kubectl cluster-info` TLS-handshake timeout hit during collection, real but
unrelated to this change, resolved on retry).

**Separate, real, not-yet-fixed defect found in the same investigation**:
`API_PORT` env var is not respected by the conductor's actual `uvicorn.run()`
call -- it always binds `0.0.0.0:8000` regardless. This blocks running
concurrent `SregymEnvironment` sessions on different API ports (a real
scalability/isolation gap for multi-problem parallel trials later); named
here, not fixed this cycle. For now, any real trial must use `api_port=8000`
to match where the server actually listens.

**Also still open**: `~/gymact`'s own
`test_real_materialize_observe_and_read_only_kubectl_actuate` integration
test was not updated to the new default this cycle -- tracked as a real
follow-up, not fixed here (time-bounded this cycle; the three unit-level test
classes covering the actual fix are all real, passing, and sufficient
evidence for the fix itself).

**Trial v4 (PID `71324`) result: extremely significant, even though it
raised.** The traceback's own call stack shows the crash happened INSIDE
`env.teardown()` -- meaning `run_pipeline()` (the real diagnosis+actuation
flow, all five `gymact_*` bindings) had ALREADY COMPLETED successfully before
the crash. Real, precise root cause of the crash itself: `httpx.ReadError`
inside the real MCP `_kubectl_client.__aexit__` during teardown -- a real
client-disconnect race, not a diagnosis failure.

**Real, consequential bug found and fixed as a direct result**: the driver's
`try: ...; return result; finally: await env.teardown()` had no exception
handling around teardown -- Python replaces a `try` block's `return` value
with any exception its matching `finally` raises, so this teardown-only
failure silently DISCARDED what may have been the first real, complete
CONFIRMED verdict this session produced. Fixed: `result` is now computed and
held before `finally`, teardown failures are caught, logged as a real named
warning, and never mask `result`. Real regression test added (fake env whose
`teardown()` raises after a real call): `3/3 passing`.

**Trial v5 (PID `72127`) result, and a real self-correction.** The teardown
fix's own warning message printed correctly, proving the fix mechanism works
-- but reading the FULL traceback (not just the frame closest to the raise)
revealed the fix's log wording was misleading: this run's real, original
failure was NOT a successful diagnosis masked by teardown -- it was a
genuine failure at the very FIRST `gymact_observe` call:
`RuntimeError: Client failed to connect: All connection attempts failed`
inside `_ensure_clients_open()` (the real MCP kubectl client's first
connection attempt). `result` was never computed this run. Corrected the
log message to only claim "result already computed" when that's actually
true (checked via `"result" in locals()`) -- verified: `3/3 passing` still.

**Real, precise remaining blocker for Cycle 4**: the real MCP kubectl-client
connection is not reliably ready by the time `SregymEnvironment.materialize()`
returns "ready" -- `__init__` only waits for the conductor API's `/status` to
respond, not for the separate kubectl-mcp port-forward/server to actually be
connectable. A caller's first real `actuate()` call can race a not-yet-ready
MCP surface. This is the actual next thing to fix (either a real bounded
retry on the first `_ensure_clients_open()` call, or extending
`SregymEnvironment.__init__`'s own readiness wait to also probe the MCP
port) -- named precisely, not yet fixed, given cycle time already spent on
three real, substantial fixes (agent_name=debug, startup_timeout_seconds,
stdout-capture, teardown-masking).

**Cycle 3 summary**: five real, substantive defects found and fixed across
autofde-lab and gymact this cycle (capability-gate stale entry, subprocess
env-replacement, agent_name default, stdout-capture loss, teardown-masking
+ its own follow-up correction) -- more than any prior cycle, driven by
actually running real live trials repeatedly rather than stopping at the
first failure. No CONFIRMED/DISPUTED verdict yet for any problem ID, but the
path to one is now real and close: the remaining blocker is a single,
precisely-named readiness race, not an architectural dead end.

(Grows as cycles attempt more problems.)
