# AFDE-2611: this repo's local UNKNOWN-tier LLM seam for A2A-2611 (SHLLM)

- **Status**: Open
- **Severity**: Medium (no actuation risk — this repo never actuates, per
  `.claude/rules/ecosystem-boundary.md` — but real, partially-wired local
  scaffolding for exactly this concern already exists and is at risk of being
  read as "SHLLM is basically done here" when the pieces are in fact unwired
  to each other; that false-completeness risk is what this ticket exists to
  name precisely, per this repo's own `no-dual-bookkeeping.md` /
  `absence-is-not-evidence.md`)
- **Standing**: `PARTIAL_ALIVE`
- **Owning repo(s)**: `seanchatmangpt/ash_a2a` (and local-provider adapters
  such as `seanchatmangpt/ollama-ai-provider-v2`) own A2A-2611 itself — the
  canonical SHLLM role/profile, CMCA routing, and CommandBus. **`autofde-lab`
  is explicitly NOT a primary owner.** `.claude/rules/ecosystem-boundary.md`
  frames this repo as one typed seam — "the search graph" — in a six-repo
  division of labour, never the admission/broker/actuation control plane.
  This repo's own `docs/rfcs/RFC-SA2A-002-v26.9.16.md` states the same
  division in its own words (§112): `autofde-lab` "owns EXPLORE and
  qualification science: falsifier generation, counterexample search,
  benchmark design, planner/policy experimentation, **UNKNOWN resolution,
  machine-experience compilation**... It MUST NOT convert the process
  observer into production authority," while §111 places "CommandBus /
  consequence routing" under `ash_a2a`'s own SUT responsibilities, not this
  repo's.
- **Depends on**: A2A-2611 (`seanchatmangpt/ash_a2a`) for the canonical
  SHLLM role/profile, `CANDIDATE_SEMANTIC_ARTIFACT`/`NO_CANDIDATE`/
  `RESOURCE_EXHAUSTED`/`UNSUPPORTED`/`REFUSED` result vocabulary, and
  CommandBus. This ticket cannot itself define any of those — it can only
  report what a bounded local UNKNOWN-tier LLM seam would sit on top of
  *in this repo*, and how much of that substrate is real today.

## Problem

A2A-2611 (`/private/tmp/claude-501/-Users-sac-autofde-lab/805b2d1b-7d56-456a-b169-7ab879cabf6b/scratchpad/ash_a2a_tickets/A2A-2611-shllm-bounded-local-unknown-tier.md`)
asks `ash_a2a` to define a canonical SHLLM capability: local inference bounded
to admitted UNKNOWN residue, candidate-only standing, finite budgets, no
silent frontier fallback.

This repo is not `ash_a2a` and does not own that role. What this repo
independently has, discovered this session by reading real source (not
copied from the remote ticket text), is a **local UNKNOWN-tier substrate**
that is structurally close to what a local SHLLM seam would sit on:

1. A real CMCA-shaped candidate-frontier allocator and admission pipeline —
   `src/autofde_lab/sa2a/unknown/allocator.py`
   (`ExplorationBudget`, `CMCACandidateAllocator`, `AllocationStanding`) and
   `src/autofde_lab/sa2a/unknown/resolution.py`
   (`UnknownResolutionPipeline`, `EpistemicState.{UNKNOWN,CANDIDATE,KNOWN,REFUSED}`,
   `AdmissionReceipt`) — a UNKNOWN → candidate frontier → admission-court →
   KNOWN lifecycle, with a fail-closed default admission court
   (`resolution.py:103-135`).
2. A real novelty-ingestion boundary —
   `src/autofde_lab/sa2a/unknown/novelty_ingest.py`
   (`NoveltyIngestionGateway.ingest_refusal_receipt`) — converts a
   `REFUSED` production `FinalReceipt` into an `UnknownCandidate` for bounded
   Lab exploration, and refuses (raises `ValueError`) on any receipt that is
   not `TerminalReceiptState.REFUSED` (`novelty_ingest.py:49-52`).
3. A real, separately-enforced authority/consequence boundary —
   `src/autofde_lab/sa2a/authority/broker.py` (`AuthorityBroker`, the four
   Authority Non-Implications: Agent/Capability/Plan/Proof != Authority) and
   `src/autofde_lab/sa2a/brce/boundary.py` (`ConsequenceBoundary`, Zero
   Unreceipted Actuation, `REFUSED_NO_GRANT` default when no explicit grant
   exists).
4. A real, already-documented "LLM only at the novelty frontier" boundary in
   the fabric layer — `src/autofde_lab/fabric/dspy.py:27-30`:
   > "DSPy and its LM are only used at the novelty frontier. JSON requests,
   > exact cache hits, registry matching, planning, and rollout remain
   > outside the language-model path."
   with provider identity (`DEFAULT_LM_MODEL = "openai/gemma-4-26b-a4b-it"`,
   `src/autofde_lab/hub/solver/dspy_policy/dspy_policy.py:51`, an
   OpenAI-API-compatible alias pointed at a **local** `TurboFieldfareServer`
   process, per `tests/conftest.py:133`) structurally separate from the
   `DecisionCompiler` capability protocol (`fabric/dspy.py:20-23`).
5. A real admission falsifier specifically for LLM-originated candidates —
   `src/autofde_lab/sa2a/admission/falsifiers.py`'s
   `FALSIFIER_LLM_DIRECT_ADMITTED` (lines 195-232), wired into
   `src/autofde_lab/sa2a/conformance/courts/admission_court.py:864-890` as
   attack `"SPARQL Invariant LLM Direct ADMITTED"`.

**What is missing, verified by grep this session (real command, zero
matches both directions):**

```bash
grep -rn "sa2a\.unknown\|from autofde_lab\.sa2a" src/autofde_lab/fabric/
grep -rln "fabric\.dspy\|fabric\.mcp\|fastmcp\|DSPyDecisionCompiler" src/autofde_lab/sa2a/
```

Both commands returned **zero matches**. `fabric/dspy.py`'s real LLM call
(`DSPyDecisionCompiler`, driven by `dspy.Predict(JobToDecision)`) and
`sa2a/unknown/`'s real candidate-frontier/admission machinery
(`UnknownResolutionPipeline`, `CMCACandidateAllocator`) are two live,
independently-tested local subsystems that **do not import or call each
other**. Nothing today routes a real DSPy/local-model call through
`ExplorationBudget`/`CMCACandidateAllocator`, and nothing wraps a
`DSPyDecisionCompiler.compile()` result in a `CandidateResolution` for
`UnknownResolutionPipeline.admit_candidate()`. This is the exact gap A2A-2611
names ("what is missing is a canonical SHLLM role with a bounded contract"),
restated in this repo's own vocabulary: the bound (budget/admission/
candidate-standing) and the thing it would bound (a real local LLM call) both
exist here, unconnected.

Two further gaps found by direct inspection, not present in the remote
ticket text and worth naming precisely:

- `AllocationStanding.EXHAUSTED` and `AllocationStanding.DEFERRED` are
  declared (`allocator.py:19-23`) but **never constructed anywhere** —
  `grep -rn "AllocationStanding\.EXHAUSTED\|AllocationStanding\.DEFERRED" src/ tests/`
  returned zero matches. `CMCACandidateAllocator.allocate()` only ever emits
  `ADMITTED` or `PRUNED` (`allocator.py:184-229`). A2A-2611's Law 4
  ("exhausted local budget yields an explicit result... no implicit
  escalation") and falsifier 3 ("budget exhaustion produces
  `RESOURCE_EXHAUSTED`, not a remote model call") have **no live code path**
  to exercise locally today — the enum member exists, the transition that
  would produce it does not.
- Neither `CandidateResolution` nor `AdmissionReceipt`
  (`sa2a/unknown/resolution.py`) carries an `authority` field of any kind —
  `grep -n "authority" src/autofde_lab/sa2a/unknown/resolution.py` returned
  zero matches. The only `authority`-adjacent text anywhere in
  `sa2a/unknown/` is `allocator.py`'s `caller_authority` parameter on
  `enforce_no_autonomous_expansion` (lines 240-269), which enforces a
  narrower, different invariant — that a model/candidate/planner cannot
  self-grant more *budget* — not that a candidate artifact carries an
  explicit `authority: :none` tag the way A2A-2611's Law 2 requires.

## Required change (local)

No code change is made by this ticket (report/design-tracking pass, per task
instructions — no commit, no push). If this repo later decides to
manufacture a local SHLLM-equivalent seam, the concrete, minimal wiring this
session's evidence points to is:

1. A typed result enum for `sa2a/unknown/` local-LLM candidate production,
   local analog of A2A-2611's five-way vocabulary
   (`CANDIDATE_SEMANTIC_ARTIFACT` / `NO_CANDIDATE` / `RESOURCE_EXHAUSTED` /
   `UNSUPPORTED` / `REFUSED`), distinct from `EpistemicState` (which encodes
   admission standing, not production outcome) and from `AllocationStanding`
   (which encodes budget allocation, not LLM output).
2. Wire `DSPyDecisionCompiler.compile()` (or a new UNKNOWN-frontier-scoped
   caller) to run only inside a `CMCACandidateAllocator`-granted
   `CandidateAllocation` (consume `allocated_tokens`/`allocated_ticks`,
   raise/return the new `RESOURCE_EXHAUSTED`-equivalent when the allocation
   is spent — currently nothing decrements an allocation at call time either).
3. Actually construct `AllocationStanding.EXHAUSTED` on the real exhaustion
   path once (2) exists, so the dead enum member stops being decoration.
4. Add an explicit `authority: Literal["none"]` (or equivalent typed
   constant) field to `CandidateResolution`, and a falsifier proving no code
   path can set it to anything else for an `sa2a.unknown`-sourced candidate.
5. Route the resulting `CandidateResolution` through the existing
   `UnknownResolutionPipeline.admit_candidate()` → `_default_admission_court`
   unchanged — this part does not need new code; §6 below is evidence it
   already treats LLM-sourced content no differently from any other
   candidate.

## Laws — local instantiation status

Each of A2A-2611's six laws, checked against this repo's real source this
session:

1. **"SHLLM is reached only for UNKNOWN work selected by CMCA."**
   `PARTIAL_ALIVE`. `fabric/dspy.py:27-30`'s docstring states the LM is used
   "only... at the novelty frontier," and `sa2a/unknown/resolution.py`'s
   `route_unknown_to_frontier` (lines 137-161) implements real CMCA-shaped
   selection over `UnknownCandidate` items via
   `CMCACandidateAllocator.allocate`. But the two are unwired (verified
   above) — no code path today actually gates a `DSPyDecisionCompiler` call
   behind a CMCA allocation decision. The *intent* is documented and the
   *mechanism* exists; the *connection* does not.
2. **"SHLLM output has `authority: :none` and candidate standing."**
   `PARTIAL_ALIVE` for candidate standing (`EpistemicState.CANDIDATE` is a
   real, used enum member, `resolution.py:27-33`); `NOT_FOUND` for an
   explicit `authority: :none` field — verified absent from
   `CandidateResolution`/`AdmissionReceipt` by grep, above. The broader
   `AuthorityBroker`/`ConsequenceBoundary` machinery (`sa2a/authority/`,
   `sa2a/brce/`) enforces "no implicit authority" for **actuation**
   requests, but no `sa2a.unknown` object is ever passed into
   `AuthorityBroker.evaluate()` or `ConsequenceBoundary.execute()` — grep for
   cross-imports between `sa2a/unknown/` and `sa2a/authority/`+`sa2a/brce/`
   found none. Candidate-standing-implies-no-authority is true only by the
   *absence* of any authority-granting call in that subtree, not by an
   explicit assertion on the object — exactly the "absence is not evidence"
   pattern this repo's own `.claude/rules/absence-is-not-evidence.md` warns
   against generalizing from.
3. **"Provider/model identity is not part of capability identity."**
   `PARTIAL_ALIVE`. Structurally real: `DEFAULT_LM_MODEL`
   (`dspy_policy.py:51`) is a plain module constant, and `tests/conftest.py`
   defines two independent fixtures — `real_dspy_lm` (local
   `TurboFieldfareServer`, `conftest.py:127-135`) and `real_groq_dspy_lm`
   (hosted Groq, `conftest.py:162-168`) — against the same
   `DecisionCompiler`/`JobToDecision` capability surface, so the pattern
   "swap provider, keep capability" is real in this repo's test
   infrastructure. Not `ALIVE`: no test *executed this session* actually ran
   the same request through both providers and compared identity/authority —
   `test_dspy_mcp_planner_loop_chicago.py` (the one test that would exercise
   this) **skipped** this session (`dspy` not importable in `.venv`, see
   Local closure work section below for the exact command/output). The
   separation is a property of the code; it is not yet a property observed
   in a run.
4. **"Exhausted local budget yields an explicit result for CMCA; no
   implicit escalation."** `UNSUPPORTED` locally, precisely: the
   `AllocationStanding.EXHAUSTED` code path does not exist (verified by
   grep, above) — there is no budget-exhaustion transition to observe
   escalating or not escalating. `CMCACandidateAllocator.allocate` prunes
   low-salience candidates (`AllocationStanding.PRUNED`) but that is a
   *selection* decision made before any consumption, not an *exhaustion*
   decision made after tokens/ticks run out mid-flight. No silent-escalation
   risk was found (there is no frontier-fallback code anywhere in
   `sa2a/unknown/` — grep confirms `real_groq_dspy_lm` is a separate,
   explicit test fixture, never an automatic fallback target reached from
   `real_dspy_lm`'s failure path), but the law's actual subject
   (exhaustion → explicit typed result) has no local implementation to
   evaluate at all.
5. **"Local tool access is capability-scoped and cannot bypass
   CommandBus."** `NOT_FOUND` for "CommandBus" as a named local component —
   `grep -rln "CommandBus" . --include="*.py"` returned zero matches
   anywhere in `src/` or `tests/`; the only occurrence in this repo is prose,
   `docs/rfcs/RFC-SA2A-002-v26.9.16.md:2065`, which places "CommandBus /
   consequence routing" under `ash_a2a`'s own SUT responsibilities (§111),
   not this repo's. The closest real local analog of "capability-scoped tool
   access, fail-closed" is `src/autofde_lab/fabric/gymact_capability_gate.py`
   (`CapabilityGate`, `CapabilityRefused` — lines 33-80), but it gates
   gymact-diagnosis TOML-manifest bindings, not LLM-triggered tool calls, and
   is not imported by anything under `sa2a/unknown/`. This law has no
   real local instantiation and should not be force-fit onto
   `gymact_capability_gate.py` — naming that absence is more honest than
   claiming a match.
6. **"A successful candidate must pass the same semantic admission as any
   frontier-model candidate."** `ALIVE`, with real evidence. Two
   independent facts, verified this session:
   - `UnknownResolutionPipeline._default_admission_court`
     (`resolution.py:103-135`) is provider-agnostic by construction — it
     inspects only `proposed_assertion`/`evidence_payload`, never
     `source_identity`, so a candidate cannot get preferential admission
     for being locally- vs. frontier-sourced.
   - `admission/falsifiers.py`'s `FALSIFIER_LLM_DIRECT_ADMITTED`
     (lines 195-232) is a SPARQL ASK query specifically designed to catch a
     triple that reached `ADMITTED` standing while
     `prov:wasAttributedTo` an `afl:LLM`/`sa2a:LLMAgent` agent without
     passing the court — i.e., the admission layer explicitly treats
     LLM-originated assertions as requiring the *same* court pass as any
     other, and has a standing falsifier watching for the bypass. Run this
     session (`.venv/bin/python -m pytest
     tests/sa2a/conformance/test_court_admission.py
     tests/sa2a/conformance/test_mutation_admission.py -v`):
     `27 passed in 1.89s`, exact output pasted below in "Local closure work."

## Chicago falsifiers — local instantiation status

Each of A2A-2611's five falsifiers, checked against real local tests this
session (per `.claude/rules/testing-chicago-style.md` — real collaborators,
state-based assertions, verification requirement: grep + real pytest output,
not a memory of a prior run):

1. **"A KNOWN deterministic request cannot invoke SHLLM."** `UNSUPPORTED`
   locally, precisely: there is no local SHLLM entry point to attempt to
   invoke — nothing to falsify yet. The closest real analog,
   `fabric/dspy.py:27-30`'s claim that JSON/exact-cache/registry-match/
   planning/rollout paths never touch the LM, has **no dedicated Chicago
   test asserting it this session** — `tests/fabric/test_dspy_mcp_planner_loop_chicago.py`
   only tests the *positive* path (a job that legitimately reaches DSPy) and
   was itself skipped this session (dspy not importable). No falsifier
   currently proves a KNOWN/deterministic job never reaches
   `DSPyDecisionCompiler.compile()`.
2. **"Switching local model provider leaves capability identity and
   authority unchanged."** `PARTIAL_ALIVE`. The fixtures exist
   (`real_dspy_lm` vs. `real_groq_dspy_lm`, `tests/conftest.py`) and target
   the identical `DecisionCompiler` protocol, but no test in this session's
   run swapped providers against the same request and diffed the result —
   would require running `test_dspy_mcp_planner_loop_chicago.py`'s scenario
   twice, once per fixture, which was not done here (and could not be, since
   `dspy` itself is not importable in this `.venv` this session — see below).
3. **"Budget exhaustion produces `RESOURCE_EXHAUSTED`, not a remote model
   call."** `UNSUPPORTED` locally — no `RESOURCE_EXHAUSTED`-equivalent
   exists to falsify (see Law 4 above). `CMCACandidateAllocator`'s pruning
   path was **not** exercised by a falsifier this session (no dedicated test
   found for `AllocationStanding.PRUNED` under
   `tests/sa2a/test_unknown_bridge.py`; the 11 passing tests in that file
   were run this session but their individual assertions were not
   enumerated here — a precise PRUNED-path claim would need a follow-up
   read of that file, not asserted from the aggregate pass count alone).
4. **"A local model tool call cannot execute a consequence outside
   CommandBus."** `NOT_FOUND` — no CommandBus exists locally (Law 5,
   above), so no falsifier for bypassing it can be constructed here. The
   nearest real local analog — that `sa2a/brce/boundary.py`'s
   `ConsequenceBoundary.execute()` refuses any envelope without an explicit
   `AuthorityBroker` grant (`REFUSED_NO_GRANT` default,
   `authority/broker.py:37`, `304-309`) — is real and tested
   (`tests/sa2a/test_authority.py`, `tests/sa2a/test_brce_replay.py`, part
   of the 31-test run below), but no `sa2a/unknown/`-sourced candidate is
   ever passed into that boundary, so this falsifier cannot presently be
   run *against an LLM-triggered call* — only against the actuation
   boundary in isolation, which is a different (real, but narrower) claim.
5. **"Malformed/ungrounded output is refused by admission even when
   generated locally."** `ALIVE`. This is the one falsifier with direct,
   real, run-this-session evidence: `_default_admission_court` refuses on
   `EMPTY_ASSERTION` / `MISSING_EVIDENCE` / `UNSUPPORTED_OR_ERROR_EVIDENCE`
   regardless of `source_identity` (`resolution.py:110-116`), and
   `FALSIFIER_LLM_DIRECT_ADMITTED` (Law 6, above) is a standing, currently
   green, falsifier specifically for the LLM-origin bypass case. Real
   command and real output for this exact claim, pasted below.

## Definition of done (local)

Restated from A2A-2611's DoD, scoped to what this repo alone could ever
close (never the cross-repo items — those stay `ash_a2a`'s):

- [ ] A local, typed result vocabulary for `sa2a/unknown/`-produced LLM
      candidates exists (currently: `NOT_FOUND`).
- [ ] `DSPyDecisionCompiler` (or an UNKNOWN-frontier-scoped equivalent) is
      wired to run under a `CMCACandidateAllocator`-granted budget and to
      decrement it, with a real exhaustion path constructing
      `AllocationStanding.EXHAUSTED` (currently: `NOT_FOUND` — dead enum
      member, no call site).
- [x] `CandidateResolution` carries an explicit `authority: "none"` field,
      falsified by a test that no local code path can set it otherwise
      (`ALIVE` as of the 2026-09-16 "authority field" closure pass, evidence
      below — was `NOT_FOUND`).
- [x] A candidate produced locally (regardless of provider) passes the same
      admission court as any other candidate — no LLM-origin special-case
      admission path exists, and a standing falsifier watches for one
      (`ALIVE`, evidence below).
- [ ] Telemetry distinguishing local UNKNOWN inference from deterministic
      and frontier routes — not found; `fabric/dspy.py`'s "novelty frontier
      only" claim is a docstring assertion with no dedicated Chicago
      falsifier proving it this session (see falsifier 1, above).
- [ ] Explicit `provider != capability` behavior observed in an actual run
      (not just structurally present in fixtures) — not done this session;
      blocked on `dspy` being importable in `.venv` (see below).

## Local closure work (this session)

Placeholder — a second agent appends real falsifier/test evidence for the
unchecked Definition-of-done items above here next; this section is left
deliberately empty of new claims beyond the verification runs already cited
inline above, so the next stage knows exactly where to write.

### Verification runs actually executed this session (raw evidence)

All commands run from `/Users/sac/autofde-lab`, confirmed via `pwd` before
any other action.

```
$ .venv/bin/python -m pytest tests/fabric/test_dspy_mcp_planner_loop_chicago.py tests/fabric/test_mcp_ocel_instrumentation_chicago.py -v
collected 4 items / 1 skipped
tests/fabric/test_mcp_ocel_instrumentation_chicago.py ....               [100%]
SKIPPED [1] tests/fabric/test_dspy_mcp_planner_loop_chicago.py:57: could not import 'dspy': No module named 'dspy'
4 passed, 1 skipped in 7.21s
```

```
$ .venv/bin/python -c "import dspy"
ModuleNotFoundError: No module named 'dspy'
```
`dspy` is not installed in this `.venv` this session — `UNSUPPORTED`
(environment gate, not incomplete work, per `.claude/rules/standing-law.md`)
for every claim above that would require an actual DSPy LM call
(`fabric/dspy.py`'s real behavior, the `real_dspy_lm`/`real_groq_dspy_lm`
provider-swap falsifier). `TurboFieldfareServer` binary/model were also
independently confirmed absent
(`~/turbo-fieldfare/.build/release/TurboFieldfareServer`,
`~/turbo-fieldfare/scratch/gemma4.gturbo` — both `MISSING`, checked via
`test -f`), and `GROQ_API_KEY` **is** set in this environment (value not
recorded in this document), so `real_groq_dspy_lm` alone would be runnable
if `dspy` were installed — the blocker is the `dspy` import, not the
provider credential.

```
$ .venv/bin/python -m pytest tests/sa2a/test_novelty_ingest.py tests/sa2a/test_unknown_bridge.py -v
collected 13 items
tests/sa2a/test_novelty_ingest.py ..                                     [ 15%]
tests/sa2a/test_unknown_bridge.py ...........                            [100%]
13 passed in 0.43s
```

```
$ .venv/bin/python -m pytest tests/sa2a/test_admission_pipeline.py tests/sa2a/test_authority.py tests/sa2a/test_brce_replay.py -v
collected 31 items
tests/sa2a/test_admission_pipeline.py ...........                        [ 35%]
tests/sa2a/test_authority.py ............                                [ 74%]
tests/sa2a/test_brce_replay.py ........                                  [100%]
31 passed in 0.93s
```

```
$ .venv/bin/python -m pytest tests/sa2a/conformance/test_court_admission.py tests/sa2a/conformance/test_mutation_admission.py -v
collected 27 items
27 passed in 1.89s
```
(This run also emitted unrelated `PytestWarning: (rm_rf) ...` teardown
warnings about a stale, permission-denied `/Users/sac/.cache/tmp/pytest-of-sac/garbage-*`
directory tree left over from other tests' fixtures in this shared cache —
confirmed unrelated to `sa2a`/admission-court code by inspecting the warned
paths, which name unrelated test functions from other suites
(`test_inspect_marketplace_admit0`, `test_pack_source_fingerprint_s0`, etc.),
not anything in `tests/sa2a/`. Not investigated further — out of scope for
this ticket.)

```bash
grep -rn "sa2a\.unknown\|from autofde_lab\.sa2a" src/autofde_lab/fabric/
grep -rln "fabric\.dspy\|fabric\.mcp\|fastmcp\|DSPyDecisionCompiler" src/autofde_lab/sa2a/
```
Both: zero matches.

```bash
grep -rn "AllocationStanding\.EXHAUSTED\|AllocationStanding\.DEFERRED" src/ tests/
grep -n "authority" src/autofde_lab/sa2a/unknown/resolution.py src/autofde_lab/sa2a/unknown/allocator.py src/autofde_lab/sa2a/unknown/novelty_ingest.py
grep -rln "CommandBus" . --include="*.py"
```
All three: zero matches.

### 2026-09-16 closure pass — Law 2 / Law 4 falsifier test

Confirmed `pwd` = `/Users/sac/autofde-lab` first (repeated per task
instruction, not assumed carried over from the prior pass). Read
`.claude/rules/ecosystem-boundary.md` again (unconditional pre-read per this
session's task, not skipped as "already covered" by the prior pass — this
repo remains the search graph only; nothing below claims cross-repo
closure). Re-read this ticket in full and re-read the remote ticket at
`/private/tmp/claude-501/-Users-sac-autofde-lab/805b2d1b-7d56-456a-b169-7ab879cabf6b/scratchpad/ash_a2a_tickets/A2A-2611-shllm-bounded-local-unknown-tier.md`
for the exact six laws before writing anything.

**New test file**:
`tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py`, following the
same `_TURBO_FIELDFARE_DIR`/`_SERVER_BINARY`/`_MODEL_PATH`/
`requires_real_turbo_fieldfare_binary_and_model` skip-gate pattern as
`tests/fabric/test_dspy_mcp_planner_loop_chicago.py`, with a module-level
`pytest.importorskip("dspy")` before the gated test. One test function,
`test_afde_2611_law2_no_authority_marker_law4_no_budget_bound`, exercises a
real `DSPyDecisionCompiler.compile()` call against `real_dspy_lm`
(`tests/conftest.py`), feeds the real compiled `DecisionRequest` through a
real `DecisionFabric.solve()`, and asserts real dataclass/state facts (no
`authority` field on either dataclass, all four identity digests still the
real `UNBOUND_*` sentinels, `has_exact_reuse_identity() is False`,
`claim_ceiling` unchanged, no `autofde_lab.sa2a` reference in
`fabric/dspy.py`/`fabric/service.py`), then re-verifies Law 4's call-site
and `AllocationStanding.EXHAUSTED` grep facts via a real `subprocess.run`
against the real source tree and `inspect.getsource` of the real,
currently-imported `compile_request_text` function.

**Real command, run this session**:

```
$ .venv/bin/python -m pytest tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py -v
collected 0 items / 1 skipped
SKIPPED [1] tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py:98: could not import 'dspy': No module named 'dspy'
1 skipped in 0.11s
```

Also run alongside the two existing DSPy/MCP Chicago tests to confirm no
regression and identical skip behavior:

```
$ .venv/bin/python -m pytest tests/fabric/test_dspy_mcp_planner_loop_chicago.py tests/fabric/test_mcp_ocel_instrumentation_chicago.py tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py -v
collected 4 items / 2 skipped
tests/fabric/test_mcp_ocel_instrumentation_chicago.py ....               [100%]
SKIPPED [1] tests/fabric/test_dspy_mcp_planner_loop_chicago.py:57: could not import 'dspy': No module named 'dspy'
SKIPPED [1] tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py:98: could not import 'dspy': No module named 'dspy'
4 passed, 2 skipped in 6.87s
```

`dspy` remains not importable in this `.venv` this session (`.venv/bin/python -c "import dspy"` →
`ModuleNotFoundError: No module named 'dspy'`, re-confirmed), and
`~/turbo-fieldfare/.build/release/TurboFieldfareServer` /
`~/turbo-fieldfare/scratch/gemma4.gturbo` are both re-confirmed `MISSING`
(`test -f`, both). **The new test honestly SKIPPED — it did not execute,
and this document does not claim it did.** No new falsifier evidence for
Law 2's live-model-call behavior (the request/result state assertions) was
produced by an executed run this session; that portion of Law 2 remains
exactly where the prior pass left it: `PARTIAL_ALIVE`, structurally present
in code, not yet observed in a run — `UNSUPPORTED` (environment gate: `dspy`
absent), not `BLOCKED` and not upgraded to `ALIVE`.

**What *is* new evidence this session, independent of the skipped test** —
gathered by real commands run directly this session (not requiring `dspy`),
re-verifying AFDE-2611's prior-session grep facts rather than citing them
from memory:

```
$ grep -rn "compiler.compile(" src/autofde_lab/fabric/
src/autofde_lab/fabric/dspy.py:142:    return compiler.compile(stripped, catalog)
```

One real call site, unchanged from the prior pass's finding.

```
$ grep -n "autofde_lab.sa2a\|sa2a\." src/autofde_lab/fabric/dspy.py src/autofde_lab/fabric/service.py
(no output, exit 1)
```

```
$ grep -rn "AllocationStanding\.EXHAUSTED" src/ tests/
(no output, exit 1)
```

Both zero matches, unchanged from the prior pass.

**Law 4 verdict: `law_held = false`.** Precise gap finding: the one real
local-compile call site in this repo's fabric layer,
`src/autofde_lab/fabric/dspy.py:142` (`return compiler.compile(stripped,
catalog)`, inside `compile_request_text`), has no retry loop, no timeout,
and no budget/allocation consumption of any kind wrapped around it —
confirmed both by the real grep above and by `inspect.getsource` of the
real `compile_request_text` function inside the (skipped) test, which
asserts none of `retry`/`budget`/`Allocation`/`EXHAUSTED`/`timeout` appear
in its source. `AllocationStanding.EXHAUSTED`
(`src/autofde_lab/sa2a/unknown/allocator.py:23`) is declared but
constructed nowhere reachable from that call site, or anywhere else in
`src/` or `tests/`. Consequently there is no local budget bound whose
exhaustion could be observed producing an explicit typed result versus a
silent escalation — Law 4, as stated ("exhausted local budget yields an
explicit result... no implicit escalation"), has **no live local
implementation to hold or fail against**. This is the same `UNSUPPORTED`
classification the prior pass already gave Law 4 and falsifier 3; this
session's contribution is re-verifying the exact call site and enum-usage
facts underneath that classification for real, this session, rather than
carrying it forward from the prior pass's grep alone (per
`.claude/rules/no-dual-bookkeeping.md` — a status is a query over evidence,
not a field copied from an earlier document). **Do not read `law_held =
false` here as "Law 4 was violated" — no escalation was observed because no
escalation code exists; the honest reading is `UNSUPPORTED`, not
`REFUSED`/`BLOCKED`.**

**Law 2 verdict: structural component re-verified `PARTIAL_ALIVE`/`NOT_FOUND`
(unchanged); live-behavior component `UNSUPPORTED` this session (unable to
execute, `dspy` absent).** The static facts the written test asserts (no
`authority` field on `DecisionRequest`/`DecisionResult`, zero `sa2a`
references in `fabric/dspy.py`/`fabric/service.py`) are re-confirmed live by
the greps above and match the prior pass's finding exactly; the dynamic
facts (actual `UNBOUND_*` digests and `claim_ceiling` on a real compiled
request, `has_exact_reuse_identity() is False` observed rather than
inferred) remain asserted in the test but not executed this session — filed
as `UNSUPPORTED`, not `ALIVE`, per `.claude/rules/absence-is-not-evidence.md`
("not observed to be inapplicable ≠ known applicable"; the same
absence-of-execution discipline applies symmetrically to the positive
claim).

**Local closure standing, this pass**: `PARTIAL_ALIVE`. A real,
skip-honest test now exists that would close Law 2's live-behavior gap and
would re-observe Law 4's structural gap the moment `dspy` +
`TurboFieldfareServer` (or `real_groq_dspy_lm` — note the test as written
uses `real_dspy_lm` only; a `real_groq_dspy_lm` variant is a straightforward
follow-up, not done this pass) become available in this environment. No
DoD checkbox in the "Definition of done (local)" section above is flipped
by this pass: closing those requires the code changes listed under
"Required change (local)," which remain undone (this is a test-authoring
and re-verification pass only, per task instructions — no production code
was written or modified).

## Local closure work (fix implemented)

**Status update**: `Standing` above is updated from `PARTIAL_ALIVE` to
`PARTIAL_ALIVE` still (unchanged label -- see "What remains open" below),
but the specific Law 4 / Required-change-(local) items #2 and #3 that were
`NOT_FOUND` are now real. This section is a code-change pass, not a
report-only pass, confirmed `pwd` = `/Users/sac/autofde-lab` first per task
instruction.

### What changed

`src/autofde_lab/fabric/dspy.py`:

- Added `bounded_compile(compile_fn, job, catalog, *, max_attempts,
  timeout_seconds) -> BoundedCompileResult` -- wraps any
  `compile_fn(job, catalog)` callable (the `DecisionCompiler` protocol
  shape) in an explicit attempt ceiling and an explicit wall-clock ceiling.
  On success: `BoundedCompileResult(standing=AllocationStanding.ADMITTED,
  request=<real DecisionRequest>, attempts_used=N, ...)`. On exhaustion
  (every attempt raised, or the time ceiling was reached first):
  `BoundedCompileResult(standing=AllocationStanding.EXHAUSTED, request=None,
  attempts_used=N, last_error=<str of the last real exception>, ...)` --
  never an unbounded exception propagating, never an unbounded retry loop,
  never a fallback to a different callable (`compile_fn` is the only thing
  ever invoked).
- `compile_request_text`'s sole local-compile call site
  (previously `return compiler.compile(stripped, catalog)`, no bound of any
  kind) now calls `bounded_compile(compiler.compile, stripped, catalog,
  max_attempts=max_attempts, timeout_seconds=timeout_seconds)` and, on
  `AllocationStanding.EXHAUSTED`, raises a typed
  `DecisionRefusal(RefusalCode.NATURAL_LANGUAGE_COMPILATION_EXHAUSTED, ...,
  details={"standing": "EXHAUSTED", "attempts_used": ..., "elapsed_seconds":
  ..., "max_attempts": ..., "timeout_seconds": ..., "last_error": ...})` --
  the return-type contract (`compile_request_text -> DecisionRequest`) is
  preserved; exhaustion surfaces as this repo's existing typed-refusal
  mechanism, not as a new return shape.
- `DEFAULT_COMPILE_MAX_ATTEMPTS = 3`, `DEFAULT_COMPILE_TIMEOUT_SECONDS =
  30.0` -- named module constants, not re-derived per call site; both
  `bounded_compile` and `compile_request_text` accept `max_attempts` /
  `timeout_seconds` overrides as keyword-only parameters (so every existing
  positional call site -- `fabric/a2a.py`, `fabric/mcp.py`, `tests/fabric/
  test_dspy.py` -- is unaffected).
- Added `from autofde_lab.sa2a.unknown.allocator import AllocationStanding`
  at module level -- the one deliberate, narrow bridge between
  `fabric/dspy.py` and `sa2a/unknown/`, explained in a header comment at the
  import site. Only `AllocationStanding` (a dependency-free `str, Enum`) is
  imported; `fabric/dspy.py` still never imports
  `sa2a.authority`/`AuthorityBroker`, `sa2a.brce`/`ConsequenceBoundary`, or
  `sa2a.unknown.resolution`/`novelty_ingest` -- no locally-produced
  candidate is routed into any admission/authority/consequence-boundary
  call anywhere in this module. `fabric/service.py` is untouched and still
  carries zero `sa2a` references of any kind.

`src/autofde_lab/fabric/models.py`:

- Added `RefusalCode.NATURAL_LANGUAGE_COMPILATION_EXHAUSTED = "SKD-FABRIC-013"`.

`tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py`:

- Replaced the module-level `pytest.importorskip("dspy")` (which skipped
  the entire file, including any future dspy-free test) with a
  function-scoped `requires_dspy = pytest.mark.skipif(not
  importlib.util.find_spec("dspy"), ...)` marker, applied only to the
  original end-to-end test (stacked with the existing
  `requires_real_turbo_fieldfare_binary_and_model`).
- Updated the original end-to-end test
  (`test_afde_2611_law2_no_authority_marker_law4_no_budget_bound`) for the
  new, correct behavior it was previously pinning as a gap: it now compiles
  through `compile_request_text()` itself (the real, fixed call site, not a
  bypass via `compiler.compile()` directly); its Law 2 sa2a-reference check
  now allows exactly the one narrow `AllocationStanding` import while still
  refusing `AuthorityBroker`/`ConsequenceBoundary`/`sa2a.authority`/
  `sa2a.brce`/`sa2a.unknown.resolution`/`sa2a.unknown.novelty_ingest`
  references; its Law 4 section re-verifies (by real grep and
  `inspect.getsource` on the live, currently-imported functions) that the
  real call site now routes through `bounded_compile()`, that
  `AllocationStanding.EXHAUSTED` is now constructed at exactly one real,
  reachable line (`fabric/dspy.py:222`), and directly exercises
  `bounded_compile()` against the real, already-successful DSPy compiler
  from the same run, asserting `standing is AllocationStanding.ADMITTED`
  and `attempts_used == 1`.
- Added two new tests that require neither dspy nor a model:
  - `test_afde_2611_bounded_compile_returns_typed_exhausted_never_raises` --
    calls `bounded_compile()` directly against a real, deterministic,
    always-raising stand-in function (`max_attempts=4`), asserts
    `standing is AllocationStanding.EXHAUSTED`, `request is None`,
    `attempts_used == 4`, the stand-in was called exactly 4 times, and
    `last_error` carries the real exception text. This is the task's
    explicitly required test.
  - `test_afde_2611_compile_request_text_converts_exhaustion_to_typed_refusal`
    -- calls `compile_request_text()` itself (the real call site) against a
    real, hand-written `AlwaysExhaustingCompiler` stand-in (structurally
    implementing `DecisionCompiler`'s `.compile(job, catalog)`, not a
    mock), asserts the resulting `DecisionRefusal.code is
    RefusalCode.NATURAL_LANGUAGE_COMPILATION_EXHAUSTED` and that its
    `details["standing"] == "EXHAUSTED"`.

### Real verification run, this session

```
$ .venv/bin/python -m pytest tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py tests/fabric/test_dspy_mcp_planner_loop_chicago.py -v
collected 3 items / 1 skipped
tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py s..            [100%]
SKIPPED [1] tests/fabric/test_dspy_mcp_planner_loop_chicago.py:57: could not import 'dspy': No module named 'dspy'
SKIPPED [1] tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py:140: Real TurboFieldfareServer binary (...) or real model weights (...) not present -- build/install them per turbo-fieldfare's README before running this real end-to-end test.
2 passed, 2 skipped in 0.67s
```

The two new, dspy-free tests **PASSED** (not skipped): the always-exhausting
stand-in produced a real `AllocationStanding.EXHAUSTED`-carrying
`BoundedCompileResult` without raising, and the real call site converted
that into the real typed `DecisionRefusal`. The original end-to-end test
still honestly SKIPPED (dspy still not importable in this `.venv`;
`~/turbo-fieldfare`'s binary/model still `MISSING`, both re-confirmed) --
this session did not newly execute the live-model path, same environment
gate as every prior pass.

Chicago-style grep, this session, over the one test file touched:

```
$ grep -n "unittest\.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py
88:for the two dspy-free tests, never `unittest.mock`/`Mock`/`patch`/
89:`monkeypatch`, per `.claude/rules/testing-chicago-style.md`.
454:    `unittest.mock`/`Mock`/`MagicMock`/`patch`/`monkeypatch`, per
```

Both matches are inside docstring prose describing the discipline, zero
matches in executable code -- no test double of any kind is used; the two
new tests use a real, hand-written always-raising function and a real,
hand-written `AlwaysExhaustingCompiler` class, each a genuine, if simple,
implementation of the relevant call signature, per
`.claude/rules/testing-chicago-style.md`'s "the distinction is not
'is it hand-written' but 'does it fake an interaction.'"

Regression check, this session (real command, real output, not delegated
to CI): `.venv/bin/python -m pytest tests/fabric -v` (full directory) ->
`3 failed, 260 passed, 227 skipped, 3 warnings in 127.59s`. The 3 failures
(`test_mcp.py::test_mcp_projects_one_fabric`,
`test_platform_console_capability_plan_chicago.py::test_ocel_diff_cli_matches_real_plan_step_effect_against_fixture_snapshots`,
`...::test_ocel_diff_cli_catches_a_deliberately_mismatched_effect`) are
**pre-existing, not introduced by this fix** -- verified by `git stash push
-- src/autofde_lab/fabric/dspy.py src/autofde_lab/fabric/models.py`,
re-running exactly those 3 tests (`3 failed in 1.94s`, identical failure
set), then `git stash pop` to restore this fix. The MCP failure is an
unrelated tool-registration drift (`issue_reasoning_catalog`/
`issue_reason` tools registered in `fabric/mcp.py` that predate this
session and are not covered by `test_mcp.py`'s expected tool set); the two
`ocel_diff_cli` failures invoke a real, unrelated compiled Rust binary for
a different capability (platform-console capability planning). Neither
touches `fabric/dspy.py`, `fabric/models.py`, or this ticket's test file.
All directly-relevant suites pass clean:
`.venv/bin/python -m pytest tests/fabric/test_dspy.py
tests/fabric/test_optional_dependencies.py tests/fabric/test_a2a_protocol.py
tests/fabric/test_cli.py tests/fabric/test_dspy_ensemble_chicago.py -v` ->
`10 passed, 3 skipped in 0.88s` (skips are the same pre-existing
`a2a`/`dspy` environment gates, unrelated to this fix).

### What remains open (unchanged by this pass)

This pass closes exactly Required-change-(local) items #2 and #3 from the
"Required change (local)" section above (wire the compile call to a bounded
allocation, and actually construct `AllocationStanding.EXHAUSTED`), scoped
narrowly: it does **not** wire through `CMCACandidateAllocator`'s actual
`ExplorationBudget`/`CandidateAllocation` machinery (item #2's fuller form
-- "consume `allocated_tokens`/`allocated_ticks`" from a real allocator
plan), it invents a local, simpler attempt/time ceiling instead and reuses
only the `AllocationStanding` enum's vocabulary. Items #1 (a five-way
result enum matching A2A-2611's `CANDIDATE_SEMANTIC_ARTIFACT`/`NO_CANDIDATE`/
`RESOURCE_EXHAUSTED`/`UNSUPPORTED`/`REFUSED`), #4 (an explicit
`authority: Literal["none"]` field + falsifier), and the live-model-call
portions of Laws 1-3/5 and falsifiers 1-2 remain exactly where the prior
pass left them -- `NOT_FOUND` / `PARTIAL_ALIVE` / `UNSUPPORTED`
respectively, not addressed by this pass, which was scoped to Law 4 only.
No `Definition of done (local)` checkbox above is flipped to `[x]` by this
pass except in spirit for the budget-bound item, which remains unchecked
above because it names the fuller `CMCACandidateAllocator`-plan-consuming
form this pass does not implement.

## Local closure work (authority field fix, 2026-09-16)

Confirmed `pwd` = `/Users/sac/autofde-lab` first (per task instruction, not
assumed carried over from prior passes). Re-read this ticket in full, and
read `src/autofde_lab/sa2a/unknown/resolution.py`,
`src/autofde_lab/sa2a/admission/falsifiers.py` (the
`FALSIFIER_LLM_DIRECT_ADMITTED` SPARQL ASK pattern), and
`tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py` in full before
writing anything, per task instruction. Scope for this pass: exactly
Required-change-(local) item #4 (the `authority: Literal["none"]` field +
falsifier) and Definition-of-done item 3. Not touched:
`src/autofde_lab/sa2a/brce/boundary.py`, `sa2a/hooks/reactive_loop.py`,
`sa2a/cli.py`, `sa2a/brce/receipts.py` — confirmed by `git diff --stat`
against those four paths before finishing this pass, matching task
instruction exactly.

### What changed

`src/autofde_lab/sa2a/unknown/resolution.py`:

- Added `Literal` to the module's `typing` import.
- Added `authority: Literal["none"] = "none"` as a new, final field on the
  frozen `CandidateResolution` dataclass, with an inline comment explaining
  the AFDE-2611 Law 2 rationale (the field replaces an absence-based
  inference — "no `authority` field exists" — with an explicit,
  always-present, always-`"none"` marker) and stating explicitly that
  `_default_admission_court`/`admit_candidate` must never be changed to read
  it. Backward compatible by construction: every existing real construction
  site (`src/autofde_lab/sa2a/cli.py:100`,
  `tests/sa2a/test_unknown_bridge.py:166,181`) already used keyword
  arguments and omitted `authority=` entirely, so all three land on the new
  default without any call-site change, matching this task's fix-forward,
  no-existing-test-weakened instruction (no existing test needed
  modification; the field is purely additive). `AdmissionReceipt` was left
  unchanged — the task scoped the fix to `CandidateResolution` only, per
  Required-change item #4's exact wording.

`tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py`:

- Added three new tests, none requiring `dspy` (real, ordinary Python
  objects only, same discipline as the file's existing `bounded_compile`
  tests):
  1. `test_afde_2611_candidate_resolution_authority_field_is_none_by_construction`
     — constructs a real `CandidateResolution` without passing `authority=`,
     asserts `.authority == "none"`, confirms it is a genuine dataclass
     field (`dataclasses.fields`), confirms the live type hint resolves to
     `Literal["none"]` via `typing.get_type_hints`/`typing.get_args`, and
     confirms the frozen dataclass refuses mutation
     (`dataclasses.FrozenInstanceError`).
  2. `test_afde_2611_no_local_model_code_path_constructs_non_none_authority`
     — the falsifier proper, in three parts: (a) real `subprocess.run` grep
     confirms `src/autofde_lab/fabric/` (this repo's local-model integration
     layer) constructs zero `CandidateResolution` objects at all today — the
     strongest form of "cannot construct one with a bad authority value"
     there is no call site to go wrong; (b) real grep + real file-window
     inspection over every actual `CandidateResolution(` construction site
     in `src/` and `tests/` confirms none ever assigns `authority` to
     anything but the literal string `"none"`; (c) real
     `inspect.getsource(UnknownResolutionPipeline._default_admission_court)`
     confirms the live admission-court function never references
     `"authority"` at all — mirroring `FALSIFIER_LLM_DIRECT_ADMITTED`'s
     intent that standing must come from the real court, never a side
     marker on the candidate.
  3. `test_afde_2611_authority_field_never_bypasses_real_admission_court` —
     the "must never become a shortcut" half: admits a real well-formed
     candidate (KNOWN) and a real malformed one (REFUSED,
     `EMPTY_ASSERTION`), then uses `dataclasses.replace()` (a real stdlib
     constructor path, not a mock — `Literal["none"]` is not runtime-enforced
     by the dataclass, so this is the one way to exercise a tampered value)
     to produce variants with `authority="ADMITTED"` /
     `authority="GRANTED_BY_MODEL"` on each, and asserts the admission
     court's verdict, `epistemic_standing`, `admitted_assertion`, and
     `reasons` are all byte-identical regardless of the tampered field —
     i.e. `admit_candidate()` is a pure function of
     `proposed_assertion`/`evidence_payload`, never of `authority`, in
     both the granting and refusing direction.
- One iteration fix during development: the falsifier's own `subprocess.run`
  grep calls initially used plain `grep -rn` over `src/` and `tests/`, which
  matched a stray `Binary file .../__pycache__/....pyc matches` line once
  this test file itself had been bytecode-compiled by a prior pytest run
  (the compiled `.pyc` embeds the literal source text). Fixed by adding
  `-I --exclude-dir=__pycache__` to both grep invocations — a real, observed
  failure (`IndexError: list index out of range` from parsing that
  non-`file:line:text`-shaped grep line), fixed at the root cause, not
  papered over.

No existing test's assertions were weakened, reverted, or made to assert
old/wrong behavior — this was a purely additive field with a default that
every existing real call site already satisfies.

### Real verification run, this session

```
$ .venv/bin/python -m pytest tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py -v -o addopts=""
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0 -- /Users/sac/autofde-lab/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/sac/autofde-lab
configfile: pyproject.toml
plugins: langsmith-0.12.1, anyio-4.14.0, nbmake-1.5.5, cov-7.1.0, xdist-3.8.0, timeout-2.4.0, Faker-40.36.0, cases-3.10.1
collecting ... collected 6 items

tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py::test_afde_2611_law2_no_authority_marker_law4_no_budget_bound SKIPPED [ 16%]
tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py::test_afde_2611_bounded_compile_returns_typed_exhausted_never_raises PASSED [ 33%]
tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py::test_afde_2611_compile_request_text_converts_exhaustion_to_typed_refusal PASSED [ 50%]
tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py::test_afde_2611_candidate_resolution_authority_field_is_none_by_construction PASSED [ 66%]
tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py::test_afde_2611_no_local_model_code_path_constructs_non_none_authority PASSED [ 83%]
tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py::test_afde_2611_authority_field_never_bypasses_real_admission_court PASSED [100%]

========================= 5 passed, 1 skipped in 0.74s =========================
```

All three new tests **PASSED** (not skipped) -- no dspy required for any of
them. The pre-existing end-to-end test still honestly SKIPPED (dspy/
TurboFieldfareServer still absent this session, unchanged environment gate
from every prior pass).

Chicago-style grep, this session, over both touched files:

```
$ grep -n "unittest\.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py src/autofde_lab/sa2a/unknown/resolution.py
tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py:88:for the two dspy-free tests, never `unittest.mock`/`Mock`/`patch`/
tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py:89:`monkeypatch`, per `.claude/rules/testing-chicago-style.md`.
tests/fabric/test_afde_2611_shllm_bounded_tier_closure.py:454:    `unittest.mock`/`Mock`/`MagicMock`/`patch`/`monkeypatch`, per
```

All three matches are inside docstring prose describing the discipline
(unchanged from before this pass), zero matches in executable code —
`dataclasses.replace()` (real stdlib constructor path) is the only mechanism
used to vary the `authority` field for the falsifier, never a test double.

Regression checks, this session (real commands, real output):

```
$ .venv/bin/python -m pytest tests/sa2a/test_unknown_bridge.py tests/sa2a/test_novelty_ingest.py tests/sa2a/conformance/test_court_admission.py tests/sa2a/conformance/test_mutation_admission.py -v -o addopts=""
...
============================== 40 passed in 1.50s ==============================
```

40 passed, 0 failed — identical count to the prior pass's own three separate
runs of these same suites (11 + 2 + 27 = 40), confirming the new
`CandidateResolution.authority` field caused no regression in the
candidate-frontier/admission/novelty-ingest/conformance-court subsystems
that construct or consume `CandidateResolution` objects.

```
$ .venv/bin/python -m pytest tests/fabric/test_dspy.py tests/fabric/test_optional_dependencies.py tests/fabric/test_a2a_protocol.py tests/fabric/test_cli.py tests/fabric/test_dspy_ensemble_chicago.py -v -o addopts=""
...
======================== 18 passed, 1 skipped in 3.84s =========================
```

18 passed, 1 skipped (the 1 skip is `test_a2a_application_constructs_with_real_sdk`,
an unrelated pre-existing environment-gated skip, not caused by this
change) — the fabric-layer suites nearest to `fabric/dspy.py` (which shares
the `AllocationStanding` enum with `resolution.py`'s new field, though it
never imports `CandidateResolution` itself, per the falsifier above) show no
regression either.

One honestly-reported, **not chased down**, out-of-scope observation: a full
`.venv/bin/python -m pytest tests/fabric -q` (the entire directory, not
scoped to this ticket's files) exited with code 139 (SIGSEGV) partway
through, on an unrelated portion of that directory's collection (this
directory also carries native/compiled-extension and RL-heavy tests per
`CLAUDE.md`'s own `just test` exclusion list — the exact class of test this
repo's own Build section already documents as excluded from the fast loop
for being native/RL-heavy, not as a property of this session's change). This
was **not investigated further** — it is outside the scope of this task
(the task's own required verification command is the single closure test
file, run and pasted above; the two scoped regression runs above are this
session's own additional, narrower, targeted checks, not a claim that the
whole `tests/fabric` directory is green). Recorded here per
`.claude/rules/standing-law.md`'s discipline of naming an exact blocker
rather than eliding it, not because it is attributed to this pass's change
— no evidence either way was gathered to attribute it, and none is claimed.

### Standing classification (this pass)

Per `.claude/rules/standing-law.md`:

- **The delivered scope of this pass** (the `authority: Literal["none"]`
  field on `CandidateResolution`, and the falsifier test proving no local
  code path constructs a non-`"none"` value and that real admission never
  reads the field) is **`ALIVE`** — a command was run this session, real
  output observed, three new tests PASSED (not skipped), zero
  `unittest.mock`/`Mock`/`patch`/`monkeypatch` in executable code (grep
  output pasted above), and 58 additional pre-existing tests across the
  admission/novelty-ingest/conformance-court and fabric-dspy-adjacent
  suites re-run this session with zero regressions.
- **AFDE-2611's overall local standing remains `PARTIAL_ALIVE`**, unchanged
  by this pass's label (only Definition-of-done item 3 flips to `[x]`) —
  Required-change items #1 (five-way result vocabulary) and the live-model
  portions of Laws 1/2/3/5 and falsifiers 1/2 remain exactly where the
  prior pass left them: `NOT_FOUND` / `PARTIAL_ALIVE` / `UNSUPPORTED`
  respectively (`dspy` still not importable in this `.venv` this session,
  re-confirmed implicitly by the same skip in the run above).
- The full-`tests/fabric`-directory segfault observation above is
  **`UNKNOWN`** — not investigated, not attributed, named precisely rather
  than elided, per `.claude/rules/absence-is-not-evidence.md`.

### What remains open (unchanged by this pass except item 3)

Item #4 from "Required change (local)" (now delivered) and Definition-of-done
item 3 (now `[x]`) are the only items this pass closes. Item #1 (a five-way
result enum matching A2A-2611's `CANDIDATE_SEMANTIC_ARTIFACT`/`NO_CANDIDATE`/
`RESOURCE_EXHAUSTED`/`UNSUPPORTED`/`REFUSED`) and the live-model-call
portions of Laws 1-3/5 and falsifiers 1-2 remain exactly where the prior
pass left them, untouched by this pass, which was scoped to the `authority`
field only, per task instruction.

## See also

- `A2A-2611-shllm-bounded-local-unknown-tier.md` (remote ticket this
  document responds to; not owned by this repo — read in full before writing
  any claim above, never copied verbatim into a local standing claim).
- `.claude/rules/ecosystem-boundary.md` — the boundary this ticket is scoped
  inside; §"What this repo may claim."
- `docs/rfcs/RFC-SA2A-002-v26.9.16.md` §§111-113 — this repo's own written
  statement of the EXPLORE/qualification-science role, and that CommandBus
  belongs to `ash_a2a`.
- `.claude/rules/standing-law.md` — the status vocabulary used in this
  document (`ALIVE`/`PARTIAL_ALIVE`/`BLOCKED:<reason>`/`BUILD_BROKEN`/
  `UNKNOWN`/`UNSUPPORTED`/`NOT_FOUND`).
- `.claude/rules/absence-is-not-evidence.md` — the discipline behind marking
  Law 2's "no code path grants authority" as `PARTIAL_ALIVE`/absence-based,
  not `ALIVE`.
- `.claude/rules/no-dual-bookkeeping.md` — why this document treats each
  local module's real behavior as the source of standing, never a summary
  claim about the subsystem as a whole.
- `src/autofde_lab/sa2a/unknown/{allocator,resolution,compilation,novelty_ingest}.py`,
  `src/autofde_lab/sa2a/authority/broker.py`, `src/autofde_lab/sa2a/brce/boundary.py`,
  `src/autofde_lab/sa2a/admission/falsifiers.py`,
  `src/autofde_lab/sa2a/conformance/courts/admission_court.py`,
  `src/autofde_lab/fabric/dspy.py`,
  `src/autofde_lab/fabric/gymact_capability_gate.py`,
  `src/autofde_lab/hub/solver/dspy_policy/dspy_policy.py`, `tests/conftest.py`
  — every source file read in full or in relevant part this session to
  ground the claims above.
