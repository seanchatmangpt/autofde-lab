# AFDE-2610: idle-estate consumer seam — honestly thin, no local scheduling surface

- **Status**: Open (scoping only — no implementation in this change)
- **Severity**: Low (informational/boundary-clarification ticket, not a defect)
- **Standing** (scoped per boundary, `.claude/rules/standing-law.md` vocabulary — no
  single blanket claim covers this ticket):
  - AtomVM/idle-estate/host-lease/drain-deadline scheduling code in this repo:
    **`NOT_FOUND`** — real grep run this session, zero matches for any of
    `idle.?estate`, `host.?lease`, `drain.?deadline` (see Local verification).
  - A resource-envelope/lease/host-identity hook on the `Solver` base class that a
    future scheduler could address: **`UNSUPPORTED`** — the capability does not
    exist; this is an architecture gap, not a bug and not something blocked by an
    external dependency.
  - The one real, already-existing, adjacent primitive — a per-call wall-clock
    execution-window ceiling on the OpenClaw actuation boundary
    (`openclaw_runtime.py::run_bounded`, `MAX_TIMEOUT_SECONDS = 600.0`):
    **`ALIVE`** — real falsifier constructed and run this session (see below),
    not a memory of a prior run or a claim from the rules file that names it.
- **Owning repo(s)**: **This repo (`autofde-lab`) is NOT a primary owner of
  AtomVM/idle-estate scheduling.** Per `.claude/rules/ecosystem-boundary.md`,
  autofde-lab is candidate-plan computation only — "the search graph, nothing
  more" — and carries no admission, broker, or actuation authority. Per the
  source ticket this one is scoped from
  (`A2A-2610-atomvm-enterprise-idle-estate.md`), the AtomVM runtime and the
  missing enterprise-estate controller (scheduling/admission) are owned by
  `seanchatmangpt/unrdf`, with control-plane integration in
  `seanchatmangpt/ash_a2a`. Nothing in this ticket changes that ownership; it
  only asks what, if anything, this repo could honestly contribute as a
  **consumer** of a lease-granting substrate those repos would own, and answers
  that question from real, in-repo evidence rather than from the ecosystem
  narrative alone.

## Problem

A2A-2610 defines an enterprise idle-estate controller: admitted host resource
envelopes (execution window, CPU/memory ceilings, thermal/power, network and
storage ceilings, allowed workload classes, drain deadline, lease/standing) and
a `PRIMARY -> IDLE_CANDIDATE -> ADMITTED -> LEASED -> EXECUTING -> DRAINING ->
PRIMARY` state machine, with CMCA able to select an `UNKNOWN_IDLE_ESTATE` route
through it. That controller does not exist anywhere in this repo, and this repo
has no BEAM/AtomVM runtime of its own to host it on — confirmed directly by
`.claude/rules/ecosystem-boundary.md`'s scope statement and by this session's
own grep (below).

The open question this ticket actually answers is narrower and local: **could
a future `CMCA` `UNKNOWN_IDLE_ESTATE` route even address a solver run in this
repo today** — i.e. is there any existing hook (a resource envelope, a host
identity, a lease acknowledgment, a bounded/cancelable execution handle) that
an external scheduler could attach to — **or would it need to invent new
machinery this repo does not have?**

Read `src/autofde_lab/solvers.py` in full this session: the base `Solver`
class (`solvers.py:27-224`) carries `domain_factory`, `get_domain_requirements()`,
`check_domain()`, `reset()`/`_reset()`, `_initialize()`/`_cleanup()`, and
`__enter__`/`__exit__` context-manager hooks for local resource cleanup. **None
of these carry a resource envelope, a wall-clock budget, a host identity, a
lease object, or any state beyond "does this domain satisfy the solver's
required builder mixins."** A `solve()` call (defined per-solver, not on the
base class) has no way to be told about a permitted execution window, a CPU or
memory ceiling, or a drain deadline, and no way to signal back a lease/standing
state.

The closest existing things in the repo, checked and correctly distinguished
so nobody conflates them with an idle-estate envelope:

1. **`src/autofde_lab/cmca/atomvm_schedule.py`** — a module literally named
   `cmca` that generates deterministic AtomVM Erlang **source text** from a
   `CascadeAllocationPlan` (ticks/memory/concurrency-lane budget for a
   verification-branch cascade). This is a **different `CMCA` than the
   ecosystem-level CMCA** A2A-2610 refers to (which selects among execution
   substrates including `UNKNOWN_IDLE_ESTATE`) — this repo's `cmca` allocates
   *search-branch* budget and projects it as an Erlang module string; per
   `.claude/rules/ecosystem-boundary.md`'s "projection is not execution" law,
   that string is a document, not a running scheduler, and it names no host,
   lease, or drain deadline. The name collision is real and worth flagging so
   a future reader does not assume this repo already has ecosystem-CMCA
   wiring because a module named `cmca` exists.
2. **`src/autofde_lab/sota_factory/portfolio_autopilot.py::PortfolioAutopilotPolicy`**
   — a real "explicit resource envelope" dataclass (`max_rounds`, `max_trials`,
   `max_concurrency`, `max_cost_usd`, `max_wall_time_s`) but it bounds a
   benchmark-trial autopilot loop's own SELECT/DO/INGEST/LEARN rounds, not a
   physical host. No host identity, no CPU/memory/thermal/network/storage
   fields, no lease/drain state machine.
3. **`src/autofde_lab/_cache/quotas.py::QuotaSpec`** — a tenant fairness
   throttle for the shared cache fabric (`requests_per_second`, `burst`,
   `max_concurrent`, `max_inflight_estimated_bytes`). Rate-limits in-process
   cache tenants; says nothing about a host or a solver run.
4. **`src/autofde_lab/openclaw_runtime.py::run_bounded`** (lines 297-317) — the
   one place in this repo that already enforces a real, external-caller-facing
   **wall-clock execution window** on a bridged invocation:
   `timeout = float(arguments.get("timeout_seconds", 120.0))`, rejected outside
   `(0, MAX_TIMEOUT_SECONDS=600.0]` with a typed `BridgeFailure("TIMEOUT_LIMIT",
   ..., status="REFUSED:BOUND_EXCEEDED")`, and a real
   `subprocess.TimeoutExpired` -> `BridgeFailure("EXECUTION_TIMEOUT", ...)` path
   if the bounded subprocess itself overruns. This is genuinely schema-adjacent
   to A2A-2610's "permitted execution window" field — but it is a per-call
   ceiling on one MCP tool invocation, with no host identity, no lease object,
   no CPU/memory/thermal/network/storage ceiling, and no drain-deadline state
   machine. It is real; it is also a small fraction of the required envelope.

**Conclusion, stated plainly**: a future `CMCA` `UNKNOWN_IDLE_ESTATE` route
cannot address a solver run here today without new machinery this repo does
not have. The gap is not one missing field — it is the entire typed envelope
(host identity, admission window, resource ceilings, lease/standing, drain
deadline) and the state machine that owns it. This is an honest
`UNSUPPORTED`, not a `BLOCKED:<external-dependency>` — nothing outside this
repo is preventing the work; the work has simply never been started here, and
per `.claude/rules/ecosystem-boundary.md` it arguably should not be started
here at all, since host/estate admission is explicitly out of this repo's
scope (candidate-plan computation only).

## Required change (scoped to what this repo can honestly contribute)

This repo cannot honestly contribute a scheduler, an admission authority, or a
lease-granting mechanism — those belong to `unrdf`/`ash_a2a` per
`.claude/rules/ecosystem-boundary.md`. What it could honestly contribute, if
and when the portfolio wants a consumer seam here, is narrowly one of:

1. **A typed, content-addressed job-package export** for a `(domain_factory,
   Solver)` pair — an immutable description an external lease-granting
   scheduler could admit and run elsewhere, analogous to how
   `fabric/powl.py` already projects a plan to a POWL document without
   executing it. This is a **producer** seam (autofde-lab emits a package), not
   a consumer of idle-estate resources itself.
2. **Extending the one real existing envelope field** —
   `openclaw_runtime.py`'s `timeout_seconds` ceiling — so an external caller
   (a future idle-estate lease consumer) can pass its own drain deadline as
   that same bounded `timeout_seconds` value and get the same typed
   `REFUSED:BOUND_EXCEEDED` / `EXECUTION_TIMEOUT` refusal it already gets
   today for any other caller. This requires no new machinery — it is already
   general-purpose — but it covers exactly one field (execution window) of the
   seven the A2A-2610 envelope names, and it is a *ceiling*, not a lease: it
   has no host identity and no fail-closed-to-`PRIMARY` semantics.

Neither of these exists today. Neither is implemented by this ticket. This
ticket is scoping only, per the task that produced it.

## Laws that actually apply locally

- **`.claude/rules/ecosystem-boundary.md`** — the governing law for this
  ticket's own existence: this repo may claim candidate-plan computation and
  projection, never receipt/admission/actuation semantics. A future job-package
  export (item 1 above) would still be a projection, not a lease acceptance;
  it could never self-certify that an idle-estate host actually ran it.
- **`.claude/rules/absence-is-not-evidence.md`** — directly binding on this
  ticket's own reasoning: the absence of idle-estate code in this repo is
  evidence of absence *here*, not evidence that the capability is impossible
  or unneeded portfolio-wide. This ticket does not coerce "not found locally"
  into "not needed anywhere," and does not coerce "OpenClaw already has a
  timeout" into "OpenClaw already has a resource envelope."
- **`.claude/rules/standing-law.md`** — the vocabulary this ticket's Standing
  section uses, scoped per boundary rather than as one blanket claim.
- **`.claude/rules/actuation-boundary.md`** — names the exact bounds
  (`MAX_EPISODES`/`MAX_STEPS`/`MAX_TIMEOUT_SECONDS`/`MAX_RESULT_BYTES`) already
  enforced at the one real actuation boundary this repo has; this ticket adds
  a fresh, this-session falsifier for the timeout bound rather than citing
  that file's claim secondhand.

## Chicago falsifiers

No idle-estate falsifier exists locally because no idle-estate code exists
locally — inventing one would test nothing real. One real falsifier does exist
for the one real adjacent primitive (the OpenClaw wall-clock execution-window
ceiling), constructed and run this session against the actual
`run_bounded()` function (no mock, real `BridgeFailure` exception path):

```python
from autofde_lab.openclaw_runtime import run_bounded, BridgeFailure, MAX_TIMEOUT_SECONDS
run_bounded({"timeout_seconds": MAX_TIMEOUT_SECONDS + 1, "tool": "decision_catalog", "arguments": {}})
```

Result: raises `BridgeFailure(code="TIMEOUT_LIMIT", status="REFUSED:BOUND_EXCEEDED")`
— a request for an execution window beyond the admitted ceiling is refused
typed, never silently widened. See Local verification for the exact command
and output. This falsifier covers exactly the one field it can honestly cover
(execution window); it says nothing about host identity, CPU/memory/thermal/
network/storage ceilings, or drain-deadline fail-closed behavior, because none
of those exist locally to falsify.

## Definition of done

Scoped to this ticket (a scoping/boundary ticket, not an implementation one):

- [x] Real grep confirms `NOT_FOUND` for AtomVM-idle-estate scheduling code in
      `src/` (idle-estate/host-lease/drain-deadline patterns; AtomVM-as-codegen-
      target is a separate, real, unrelated fact and is named as such above).
- [x] `src/autofde_lab/solvers.py` read in full and assessed: the `Solver`
      base class has zero resource-envelope/lease/host-identity hooks.
- [x] The closest adjacent local primitives (CMCA-the-module,
      `PortfolioAutopilotPolicy`, `QuotaSpec`, OpenClaw's `timeout_seconds`)
      identified and each explicitly distinguished from an idle-estate
      envelope, so none is mistaken for partial coverage of A2A-2610.
      the ownership boundary is stated plainly, not implied.
- [ ] **Not done, and out of scope for this ticket**: any actual job-package
      export, any extension of `run_bounded`'s `timeout_seconds` semantics, any
      new resource-envelope type on `Solver`. These remain `UNSUPPORTED` until
      a future ticket scopes and implements one of the two `Required change`
      options above, and until `unrdf`/`ash_a2a` have an admitted lease-
      granting interface for this repo to honestly consume. This ticket never
      claims cross-repo closure — only a locally-honest `NOT_FOUND` +
      `UNSUPPORTED` pair with one real, narrowly-scoped `ALIVE` adjacency.

## Local verification (this session)

Repo confirmed at session start: `cd /Users/sac/autofde-lab && pwd` ->
`/Users/sac/autofde-lab`. Branch `feat/semantic-model-manufacturing`, HEAD
`f5727fa970c8fd1060e662bc9e963c484aa5ed14`, date 2026-09-16.

**1. Required grep, run verbatim, real output:**

```console
$ grep -rniE "atomvm|idle.?estate|host.?lease|drain.?deadline" src/
```

Exit code: `0` (matches found). 43 total lines matched, **every single one is
an `atomvm` hit**; zero matches for `idle.?estate`, `host.?lease`, or
`drain.?deadline` (each pattern re-run in isolation this session, each exits
`1` — no match — independently):

```console
$ grep -rniE "idle.?estate" src/ ; echo "exit:$?"
exit:1
$ grep -rniE "host.?lease" src/ ; echo "exit:$?"
exit:1
$ grep -rniE "drain.?deadline" src/ ; echo "exit:$?"
exit:1
```

The 43 `atomvm` hits are all code-generation/projection surfaces:
`src/autofde_lab/cmca/atomvm_schedule.py`,
`src/autofde_lab/sa2a/construct/constructor.py` (`TargetProfile.BEAM_ATOMVM`),
`src/autofde_lab/semantic_models/atomvm_codegen.py`,
`src/autofde_lab/semantic_models/parity_court.py`,
`src/autofde_lab/semantic_models/tiny_operator.py`. None reference a host, a
lease, an admission window, or a drain deadline — confirmed by reading each
file, not inferred from the grep alone.

A broader, unscoped check for the word "lease" was also run, to make sure a
different spelling wasn't hiding a real host-lease concept:

```console
$ grep -rniE "\blease\b" src/ ; echo "exit:$?"
exit:0
src/autofde_lab/_cache/coordinator.py:79:    No background worker is created. Every construction, lease, promotion,
src/autofde_lab/_cache/coordinator.py:486:                        f"timed out waiting for cache lease {key.digest}"
src/autofde_lab/_cache/coordinator.py:491:            # lease acquisition.
src/autofde_lab/_cache/types.py:166:    """Raised when another process holds a compute lease past the wait bound."""
```

Read: this is an in-process compute-memoization lock (dedup a concurrent
recomputation of the same cache key), not a host resource lease. Confirmed
unrelated to A2A-2610's host-lease concept.

**2. `src/autofde_lab/solvers.py` read in full (224 lines) this session.**
Assessment: `Solver.__init__` takes only a `domain_factory`; the class exposes
`domain_factory`, `original_domain_factory`, `get_domain_requirements()`,
`check_domain()`/`_check_domain_additional()`, `reset()`/`_reset()`,
`_initialize()`/`_cleanup()`, `__enter__`/`__exit__`. No field or method
anywhere in the file references a resource ceiling, a wall-clock budget, a
host identity, or a lease/standing state. `DeterministicPolicySolver` (the
only other class in the file) adds no new state, only a builder-mixin
combination. This directly answers the task's assessment question: **a future
`CMCA` `UNKNOWN_IDLE_ESTATE` route cannot address a solver run here today** —
there is no attachment point for a resource envelope on `Solver` at all.

**3. Real Chicago falsifier for the one adjacent primitive that does exist**
(`openclaw_runtime.py::run_bounded`'s `timeout_seconds` ceiling), run this
session, no mock:

```console
$ .venv/bin/python -c "
from autofde_lab.openclaw_runtime import run_bounded, BridgeFailure, MAX_TIMEOUT_SECONDS
try:
    run_bounded({'timeout_seconds': MAX_TIMEOUT_SECONDS + 1, 'tool': 'decision_catalog', 'arguments': {}})
    print('FALSIFIER FAILED: no exception raised for out-of-bounds timeout_seconds')
except BridgeFailure as exc:
    print(f'FALSIFIER HELD: code={exc.code} status={exc.status} message={exc}')
except Exception as exc:
    print(f'FALSIFIER FAILED: wrong exception type {type(exc).__name__}: {exc}')
"
FALSIFIER HELD: code=TIMEOUT_LIMIT status=REFUSED:BOUND_EXCEEDED message=timeout_seconds must be in (0, 600.0]
```

Exit code: `0`. Real function, real exception path, real typed refusal —
`REFUSED:BOUND_EXCEEDED`, matching the vocabulary `.claude/rules/actuation-boundary.md`
names. No pytest file was added for this (out of scope for a scoping ticket);
the command above is the falsifier and its output is the evidence.

## See also

- `A2A-2610-atomvm-enterprise-idle-estate.md` (ash_a2a tickets, scratchpad
  copy read this session) — the source ticket this one is honestly scoped
  down from.
- `.claude/rules/ecosystem-boundary.md` — why this repo is not, and cannot
  self-certify itself as, an idle-estate owner.
- `.claude/rules/absence-is-not-evidence.md`, `.claude/rules/standing-law.md`
  — the admission/vocabulary laws this ticket's own claims are bound by.
- `src/autofde_lab/openclaw_runtime.py`, `.claude/rules/actuation-boundary.md`
  — the one real, already-bounded actuation surface in this repo, and the
  nearest honest attachment point for a future, much narrower, execution-
  window-only seam.
