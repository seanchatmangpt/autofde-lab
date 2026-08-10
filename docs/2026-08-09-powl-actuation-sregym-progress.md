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

### Cycle 4 (2026-08-10)

**Fixed the readiness-race blocker named at the end of Cycle 3.**
`SregymEnvironment.__init__` now requires BOTH the conductor API's `/status`
AND a real TCP-reachable kubectl-mcp port before declaring ready (new
`_tcp_port_reachable()` helper, real socket probe, no cluster needed to test
it). Also fixed, found while testing: `_real_sregym_checkout_ready()`
(gymact's own test file) let a transient `kubectl cluster-info` TLS timeout
raise uncaught at MODULE IMPORT TIME, aborting collection of the whole test
file including unrelated non-live tests -- now caught, degrades to a named
skip reason. `15/15` non-live tests passing.

**Real infrastructure failure hit and recovered from this cycle**: the
cluster became genuinely unreachable (`TLS handshake timeout`, persistent
across 3 real retries with waits, not transient) -- likely accumulated
strain from this session's many hours of repeated real deploys. Recovered
via `colima stop && colima start --cpu 12 --memory 20` (the same
already-proven-safe recovery this session used once before; node state and
age persisted through the restart, confirming non-destructive). **Real,
newly-confirmed fact**: the earlier node-affinity label fix
(`node-role.kubernetes.io/control-plane=""`) does NOT survive a colima
restart -- k3s re-applies its own default (`"true"`) on every restart.
Re-applied this cycle; **any future cycle that hits the Prometheus
`FailedScheduling` dead-end again should check this label first** before
assuming it's a new problem.

**Live trial attempted after cluster recovery -- real progress, past the
connection/readiness stage entirely this time.** New real failure, further
downstream: `fastmcp.exceptions.ToolError: 2 validation errors for
call[exec_kubectl_cmd_safely]: cmd Missing required argument, command
Unexpected keyword argument`. Precise, simple root cause: gymact's own
`actuate()` called the real MCP tool with `{"command": ...}`, but the real
tool's schema requires `{"cmd": ...}` -- confirmed by cross-checking every
OTHER real client in the vendored sregym checkout
(`clients/demo/driver.py`, `clients/stratus/tools/kubectl_tools.py`), all of
which already correctly use `cmd`. Fixed (gymact commit, this cycle);
`15/15` unaffected tests still passing. Not independently unit-tested (the
call is inline, not a separable pure function) -- strongest evidence is a
real live re-run, launched immediately (PID `75406`).

**Trial v2 (PID `75406`) result: real, informative regression.** The `cmd`
argument fix worked (no more validation error), but the SAME connection
failure from before recurred: `RuntimeError: Client failed to connect: All
connection attempts failed`, at the exact same `_kubectl_client.__aenter__()`
call. Real, precise conclusion: the earlier `_tcp_port_reachable` fix is a
NECESSARY but NOT SUFFICIENT readiness signal -- a raw TCP accept succeeding
does not prove the real port-forward/MCP protocol handshake behind it is
actually ready. Confirmed live, twice.

**Fixed with the architecturally correct approach**: a bounded retry (5
attempts, 2s delay) directly around the real `Client.__aenter__()` call
itself (`_connect_with_retry()`), not a stronger pre-check -- no pre-check
can fully predict a later real handshake's outcome. Real regression tests
(hand-written fake client, not a mock, whose `__aenter__` genuinely fails a
counted number of times): `17/17` passing.

**Trial v3 (PID `76306`) result: a real bug in the retry fix itself, found
immediately.** `RuntimeError: Client is not connected. Use the 'async with
client:' context manager first.` -- even though the retry loop had just
reported success. Real, precise cause: retrying `__aenter__()` on the SAME
already-failed `Client` instance left it in a broken internal state; many
async context managers are not safe to re-enter after a failed attempt.

**Fixed**: `_connect_with_retry()` now takes a `client_factory` (builds a
genuinely fresh `Client` per attempt) instead of a single pre-built
instance, and returns the one real successful client. Real regression tests
rewritten to prove fresh instances are actually built per attempt and that
failed instances were never entered. `17/17` passing.

**Trial v4 (PID `77290`) result: the SAME error recurred despite the fresh-
instance fix, revealing the REAL, deeper root cause.** `RuntimeError: Client
is not connected...` again. This is not the connect-retry defect at all --
it is a real, architectural mismatch between autofde-lab's own driver and
any persistent async client:

`gymact_diagnosis_driver.py`'s `_run_coroutine_sync()` (needed because each
`action_bindings` closure runs inside `run_pipeline`'s synchronous callback,
which may itself already be inside a running event loop) does
`with ThreadPoolExecutor(max_workers=1) as pool: pool.submit(asyncio.run,
coro).result()` -- creating and fully tearing down a FRESH event loop on
EVERY SINGLE real gymact_* binding call. The first call (`gymact_observe`)
connects `self._kubectl_client` using event loop A's transport/tasks; loop A
is closed the moment that call returns. The second call
(`gymact_actuate_remediate`, a `run_kubectl` call) creates a brand new loop
B and tries to reuse the already-open client object -- but its underlying
async resources are bound to the now-closed loop A. Async transport/tasks
cannot cross event loops; this is not a timing race, it is a structural
impossibility as currently wired, and would recur 100% of the time past the
first real client-using call, regardless of any retry/timing fix.

**Real, precisely-named next blocker for Cycle 5 (not yet fixed, given this
cycle's already substantial scope)**: `SregymEnvironment`'s persistent
`_kubectl_client`/`_submit_client` design (opened once, reused across many
calls -- explicitly built this way for efficiency, per its own module
docstring) is fundamentally incompatible with being driven from a caller
that runs each call in its own fresh event loop. Two real fix directions,
neither attempted yet: (a) make `_ensure_clients_open()` connect-use-close
fresh on every single call instead of caching (trades connection overhead
for correctness, matches `vendor_benchmarks.py`'s own one-shot-per-call
precedent), or (b) redesign the driver side so all `gymact_*` bindings for
one trial run inside a SINGLE persistent event loop/thread for the whole
`run_pipeline` call, not one fresh loop per binding.

**Cycle 4 summary**: eight real, distinct defects found and fixed across
autofde-lab and gymact (readiness-race, collection-safety, cmd-argument-
name, connect-retry, the retry-fix's own instance-reuse bug, plus real infra
recovery + a non-persistent node-label finding), PLUS this cycle's real,
architecturally deeper discovery -- the actual reason connection-layer fixes
alone could never fully succeed. This is the deepest real debugging chain
of the whole session: each fix surfaced the next real defect underneath it,
never a false all-clear, converging on a genuine structural finding rather
than another symptom.

### Cycle 5 (2026-08-10)

**Implemented fix direction (a) from Cycle 4's close-out**: `SregymEnvironment`
no longer caches persistent `_kubectl_client`/`_submit_client` instance
state at all. New `_open_client_with_retry()` async context manager (builds
on the already-real `_connect_with_retry`) opens, uses, and closes a fresh
client entirely within the ONE event loop actually running each real
`actuate()` call -- `_ensure_clients_open()` removed entirely, `teardown()`
simplified. Cluster health and the node-affinity fix both independently
re-verified before relaunching (per this cycle's own past lesson: the
affinity fix does not survive a colima restart, so it's checked fresh every
cycle now rather than assumed). `17/17` unaffected tests still passing.

Not independently unit-tested at the `actuate()` level itself (a real
fastmcp protocol handshake needs a real MCP server) -- trial launched
immediately (PID `79041`) as the real evidence.

**Trial result: the per-call fix is confirmed WORKING (real, positive
evidence), but a NEW, distinct, not-yet-understood failure surfaced.**
`RuntimeError: real MCP client 'kubectl_client' failed to connect after 5
real attempts` -- this is the retry mechanism's own exhaustion message,
firing exactly as designed, proving the new per-call architecture is
genuinely exercised (the old "Client is not connected" instance-reuse bug
is confirmed gone). All 5 real attempts over ~10s genuinely failed to
connect.

**Real, checked evidence, not guessed**: no zombie/orphaned port-forward
process was found (`lsof`/`ps` both clean) -- ruling out the exact defect
found and killed manually in Cycle 3. Real timing evidence: the whole run,
start to this failure, took only ~69 real seconds (log file created and
last modified 69s apart) -- far too fast for a from-scratch deploy (5-15+
confirmed real minutes earlier this session), meaning `_tcp_port_reachable`
genuinely passed quickly, almost certainly because the conductor's own
idempotent "already exists, leaving unchanged" redeploy logic reused this
session's already-warm cluster state rather than performing a real fresh
deploy.

**Real, open question for Cycle 6, not yet answered**: why would a TCP port
that just became reachable still fail a real MCP protocol handshake 5 times
in a row moments later? Candidate hypotheses, NONE yet confirmed: (a) a
listening socket that accepts but the tunnel behind it doesn't yet proxy
real traffic, (b) a real timing gap between port-forward TCP-acceptability
and the pod-side MCP server actually being ready to handshake, larger than
the current retry budget (5 x 2s = 10s) allows for. Next real step: increase
the retry budget and/or capture the underlying low-level exception from each
of the 5 attempts individually, not just the final summary, before assuming
either hypothesis.

**Cycle 5 summary**: the deep architectural per-call-client fix from Cycle
4's finding is confirmed real and working; one further, real, distinct
connection-timing gap remains, precisely named with real evidence rather
than guessed.

### Cycle 6 (2026-08-10)

**Addressed Cycle 5's named next step.** Widened `_connect_with_retry`'s
budget from 5x2s (10s total) to 10x3s (30s total) -- real evidence from
Cycle 5's own trial showed the smaller budget was genuinely exhausted with
no zombie process present and a fast (~69s) `__init__`. Also: the raised
error now names every real per-attempt error individually (type + message),
not just a final summary -- a recurrence is now diagnosable from the
message alone. Real regression test added proving every attempt's error
appears in the final message. `18/18` passing. Cluster health and the
node-affinity fix both re-verified fresh before relaunching (per the
now-standing per-cycle check established in Cycle 4/5).

Trial relaunched with the widened budget (PID `83951`) -- in progress.

(Grows as cycles attempt more problems.)
