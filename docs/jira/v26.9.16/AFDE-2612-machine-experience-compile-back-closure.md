# AFDE-2612: this repo's local surface for A2A-2612 (machine-experience compile-back)

- **Status**: Open
- **Severity**: Medium (local scope only — see Standing)
- **Standing**: `PARTIAL_ALIVE`
- **Owning repo(s)**: A2A-2612 itself is owned by
  `seanchatmangpt/ash_a2a`, `seanchatmangpt/ggen`, `seanchatmangpt/bcinr`,
  `seanchatmangpt/affidavit` (per the upstream ticket). **`autofde-lab` is
  explicitly NOT an owner of that cross-repo closure.** Per
  `.claude/rules/ecosystem-boundary.md`, this repo is one typed seam — "the
  search graph" — in a six-repo division of labour; it computes candidate
  plans, it does not admit, broker, actuate, or hold cross-repo control-plane
  authority. This ticket scopes strictly to `src/autofde_lab/sa2a/` — a
  **local, in-repo testbed** of courts, hooks, and an UNKNOWN-resolution
  pipeline — and is explicit throughout about which pieces are real local
  code with real passing tests versus which upstream laws simply have no
  local instantiation. Nothing in `src/autofde_lab/sa2a/` is, or is claimed
  to be, the ecosystem admission/broker authority `mfw` owns, nor the
  ggen/affidavit manufacture-and-receipt chain — it is a same-repo simulacrum
  used to falsify the *shape* of the compile-back law locally.
- **Depends on** (real, local, read in full this session):
  `src/autofde_lab/sa2a/unknown/novelty_ingest.py`,
  `src/autofde_lab/sa2a/unknown/resolution.py`,
  `src/autofde_lab/sa2a/unknown/compilation.py`,
  `src/autofde_lab/sa2a/unknown/allocator.py` (referenced, not re-read in full —
  API confirmed via imports in the files above and in the closed-loop test),
  `src/autofde_lab/sa2a/hooks/synthesis.py`,
  `src/autofde_lab/sa2a/hooks/engine.py`,
  `src/autofde_lab/sa2a/hooks/reactive_loop.py` (referenced via the closed-loop
  test's imports, not re-read in full),
  `src/autofde_lab/sa2a/authority/broker.py`,
  `src/autofde_lab/sa2a/brce/boundary.py`, `src/autofde_lab/sa2a/brce/receipts.py`,
  `tests/sa2a/test_autonomic_closed_loop_lifecycle.py`,
  `tests/sa2a/test_unknown_bridge.py`.

## Problem

The upstream ticket (`A2A-2612`, read in full at
`/private/tmp/claude-501/-Users-sac-autofde-lab/805b2d1b-7d56-456a-b169-7ab879cabf6b/scratchpad/ash_a2a_tickets/A2A-2612-machine-experience-compile-back.md`)
requires an Experience Compiler implementing:

```text
UNKNOWN -> candidate -> admitted -> executed -> receipt evidence ->
generalized candidate pattern -> admission -> manufactured deterministic
capability -> registered KNOWN route
```

as **one** admission-gated, receipted, reversible pipeline, so that a
successful UNKNOWN resolution becomes reusable machinery rather than being
re-purchased as intelligence every time.

**Real local finding, established by reading source this session**: this
repo already contains every individual stage of that state machine as a
separate, independently real and independently tested component —
`NoveltyIngestionGateway` (ingestion), `UnknownResolutionPipeline` (an
admission-court-gated candidate→KNOWN store), `MachineExperienceCompiler` (a
compiled-rule-first, LLM-fallback-second resolver with a measured avoidance
ratio), and `HookSynthesizer` + `KnowledgeHookEngine` +
`AuthorityBroker.register_grant` (manufacture and registration of a
deterministic reflex). All four are exercised by real, currently-passing
tests (see Local execution below).

**But the one demonstrated end-to-end closed loop
(`tests/sa2a/test_autonomic_closed_loop_lifecycle.py`) does not actually wire
these four components together as the state machine requires.** Read in
full: the test's promotion step calls `HookSynthesizer.synthesize_from_resolution()`
directly with hand-constructed keyword arguments (`hook_name`,
`trigger_predicate`, `action_iri`, ...) and then calls
`hook_engine.register_hook(artifact.hook)` /
`prod_broker.register_grant(artifact.suggested_grant)` directly. Neither
`UnknownResolutionPipeline.admit_candidate()` (the only local code that
produces an `AdmissionReceipt` / `EpistemicState.KNOWN` standing) nor
`MachineExperienceCompiler.compile_candidate_experience()` (the only local
code that produces an `ExperienceCompilationReceipt` with a measured
`llm_inference_avoidance_rate`) is called anywhere in that test. The
"Lab exploration & qualification" step between ingestion and synthesis is a
comment and a hardcoded integer (`lab_tokens_spent = 2500`), not a call into
either admission pipeline that already exists in this repo.

So the local gap is precise: **three real, tested pipeline segments exist
in this repo; the one demonstrated closed loop skips the admission-gated
segment and the compiled-rule segment entirely**, going straight from
ingestion to direct hook manufacture and direct registration with no
admission court in between.

## Required change (scoped to what this repo can honestly contribute)

1. Rewire `HookSynthesizer.synthesize_from_resolution()` (or a new call site)
   to consume an `AdmissionReceipt` (from `UnknownResolutionPipeline.admit_candidate`)
   or an `ExperienceCompilationReceipt` (from `MachineExperienceCompiler`) as
   its **input**, rather than raw hand-constructed IRIs — so promotion to a
   registered hook is provably downstream of an admission decision, not a
   sibling of it.
2. Add explicit provenance fields to `SynthesizedHookArtifact` and
   `CompiledDeterministicRule`/`ExperienceCompilationReceipt`: a source
   evidence digest (receipt id / `candidate_hash`), a generator/manufacturer
   identity (e.g. `HookSynthesizer` version string), and the admission
   court's verification result — none of these fields exist today (see Laws,
   #4 below).
3. Fix the silent-overwrite gap in `MachineExperienceCompiler.compile_candidate_experience`
   (`src/autofde_lab/sa2a/unknown/compilation.py:94`,
   `self._rule_registry[pattern] = rule` inside the loop, unconditional) so
   that re-compiling an existing `pattern` with a different
   `deterministic_output` produces a typed conflict/requalification event
   instead of a silent dict overwrite.
4. Add `AuthorityBroker.revoke_grant(...)` — confirmed absent by reading
   `src/autofde_lab/sa2a/authority/broker.py` in full (only `register_grant`,
   `register_policy`, `evaluate` exist; no revoke/deregister method). Today,
   `KnowledgeHookEngine.unregister_hook(hook_iri) -> bool` exists
   (`src/autofde_lab/sa2a/hooks/engine.py:36`) but has **zero test
   coverage anywhere in the repo** (confirmed by grep — the only match for
   `unregister_hook` in `src/` or `tests/` is its own definition), and even a
   full hook removal would leave the registered `AuthorityGrant` live in the
   broker forever, since nothing can revoke it.
5. Replace the hardcoded `runtime_tokens_cycle1 = 0` literal in
   `tests/sa2a/test_autonomic_closed_loop_lifecycle.py:192` with real
   instrumented LLM-call counting, the same pattern
   `MachineExperienceCompiler` already uses for real
   (`_llm_calls_avoided` / `inference_avoidance_ratio`, exercised for real in
   `test_machine_experience_compiler_avoids_llm_inference`) — so the
   closed-loop test's "zero LLM calls" claim is a measurement, not an
   assertion of a literal.

## Laws

Each of the upstream ticket's 7 laws, annotated with **this repo's actual
local standing**, established by reading the cited source this session
(never copied from the upstream ticket text):

1. **"No experience is promoted from model text alone; promotion requires
   execution evidence/receipt."** — `PARTIAL_ALIVE`. `NoveltyIngestionGateway.ingest_refusal_receipt`
   type-checks its input (`receipt.state != TerminalReceiptState.REFUSED`
   raises `ValueError`, `src/autofde_lab/sa2a/unknown/novelty_ingest.py:49-52`)
   — entry into the candidate frontier is receipt-gated. But
   `UnknownResolutionPipeline._default_admission_court`'s evidence check
   (`src/autofde_lab/sa2a/unknown/resolution.py:110-116`) only requires a
   non-empty `evidence_payload` dict with no `"error"`/`"unsupported"` key —
   it does not require that payload be, or derive from, an actual
   `FinalReceipt`; a hand-typed `{"source": "synthetic_bench"}` string passes
   (as it does in `tests/sa2a/test_unknown_bridge.py:170`). And the closed-loop
   test's actual promotion call (`HookSynthesizer.synthesize_from_resolution`)
   takes no receipt object at all — see Problem above.
2. **"Receipt feedback carries no authority."** — `ALIVE` at the code-shape
   level. `HookSynthesizer.synthesize_from_resolution` returns a
   `suggested_grant: AuthorityGrant` that is inert until a caller separately
   calls `AuthorityBroker.register_grant(...)` — the synthesizer never grants
   authority itself (`src/autofde_lab/sa2a/hooks/synthesis.py:80-85`,
   registration is a separate line in the test,
   `tests/sa2a/test_autonomic_closed_loop_lifecycle.py:150`). Confirmed by
   reading both files; not separately falsifier-tested this session.
3. **"Generalization produces a candidate pattern, never an immediately
   trusted rule."** — `PARTIAL_ALIVE`, and inconsistent across modules.
   `UnknownResolutionPipeline` has exactly this shape:
   `CandidateResolution` → `admission_court` → only on success is
   `_known_store` written (`resolution.py:163-172`). But
   `MachineExperienceCompiler.compile_candidate_experience` has no such
   split — a compiled item is written straight into `self._rule_registry`
   in the same call with no intermediate untrusted state
   (`compilation.py:73-105`), and `HookSynthesizer.synthesize_from_resolution`
   likewise returns an already-fully-formed, directly-registerable artifact.
   The law is real in one of three local modules, absent in the other two.
4. **"Promotion must bind source evidence, ontology identity, capability
   identity, generator/manufacturer identity and verification result."** —
   `NOT_FOUND` locally as a typed, explicit binding. `SynthesizedHookArtifact`
   carries `hook`, `graphlaw_rule_ttl`, `suggested_grant`, and an
   `artifact_digest` that hashes `hook.to_turtle()` + rule TTL + grant id
   (`synthesis.py:87-95`) — no field binds back to the source
   `FinalReceipt`/`AdmissionReceipt` that justified promotion, no field
   records which code/version manufactured it, no field carries a
   verification result. `ExperienceCompilationReceipt` has the same gap
   (`compilation.py:34-54`).
5. **"A promoted route must be at least as fenced as the UNKNOWN path it
   replaces."** — `NOT_FOUND`. No code path in
   `authority/broker.py` or `hooks/synthesis.py` compares a synthesized
   `AuthorityGrant`'s scope against any prior exploration budget or envelope.
   No falsifier or test constructed this session; read-confirmed absent.
6. **"On the next matching task, the deterministic KNOWN route is preferred
   over SHLLM/frontier inference."** — `ALIVE`, narrowly, for
   `MachineExperienceCompiler.resolve()` specifically: it checks
   `self._rule_registry` first and only calls `fallback_llm_inference` on a
   miss, incrementing `_llm_calls_avoided` on a hit
   (`compilation.py:107-122`), real and tested this session (see Local
   execution). **Not** demonstrated for the closed-loop hook-reflex path —
   `ReactiveSemanticLoop.run_reflex_cycle` never had a competing LLM call
   site to route away from in the first place, so its "avoidance" is
   structural (BRCE reflexes are deterministic by construction) rather than
   a measured preference between two live options.
7. **"Failed or contradictory evidence cannot silently mutate the canonical
   graph."** — `PARTIAL_ALIVE`, and contradicted in one module by
   read-inspection (not execution) this session. `UnknownResolutionPipeline`'s
   admission court correctly refuses and leaves `_known_store` untouched on
   bad evidence (`resolution.py:118-127`, exercised for real by
   `test_unknown_state_routing_and_admission_pipeline`, see Local execution).
   But `MachineExperienceCompiler.compile_candidate_experience` performs an
   **unconditional** `self._rule_registry[pattern] = rule`
   (`compilation.py:94`) inside its loop — calling it twice with the same
   `pattern` and a different `deterministic_output` silently overwrites the
   first rule with no conflict detection or requalification event. This is a
   structural finding from reading the source, **not verified by running a
   falsifier this session** — a concrete target for the next closure pass
   (see placeholder below).

## Chicago falsifiers

Each of the upstream ticket's 6 falsifiers, annotated with local standing:

1. **"One successful UNKNOWN episode without a promotion admission does not
   change routing."** — `PARTIAL_ALIVE` by code inspection:
   `MachineExperienceCompiler.resolve()` only reads `_rule_registry`; only
   `compile_candidate_experience` writes it (`compilation.py:107-122` vs.
   `73-105`) — a resolve-only call structurally cannot mutate the registry.
   No dedicated falsifier test exists in this repo exercising this
   invariant directly; not executed this session.
2. **"An admitted promotion creates a new deterministic route and the next
   matching episode makes zero LLM calls."** — `ALIVE` for the compiler,
   with real measured evidence, not a hardcoded literal:
   `test_machine_experience_compiler_avoids_llm_inference`
   (`tests/sa2a/test_unknown_bridge.py:199-229`) uses a real Python callable
   counter (`llm_mock_called[0] += 1`, not `unittest.mock`) and asserts
   `llm_mock_called[0] == 0` after a compiled-pattern resolve, and
   `inference_avoidance_ratio == 1.0` — run this session, passed (see Local
   execution). By contrast, the closed-loop test's version of this same
   falsifier (`runtime_tokens_cycle1 = 0` at
   `tests/sa2a/test_autonomic_closed_loop_lifecycle.py:192`) is a **hardcoded
   integer literal asserted less than another hardcoded literal**
   (`lab_tokens_spent = 2500`) — no LLM call site is instrumented or counted
   in that test at all. These are not the same standing despite looking like
   the same falsifier; only the compiler-level one is real measured
   evidence.
3. **"Tampered receipt evidence cannot be promoted."** — `UNKNOWN` locally.
   `NoveltyIngestionGateway` type-checks `receipt.state` but performs no
   cryptographic or replay-based authenticity check on the receipt content
   itself before ingestion (`novelty_ingest.py:39-52`); no such check is
   invoked from this module. Not tested or falsified this session.
4. **"A promoted capability cannot widen authority relative to its admitted
   contract."** — `NOT_FOUND`. No comparison logic exists anywhere in
   `authority/broker.py` or `hooks/synthesis.py`, confirmed by reading both
   files in full.
5. **"Contradictory new evidence produces a new candidate/requalification
   event, not silent overwrite."** — contradicted by the
   `compilation.py:94` unconditional-overwrite finding under Law 7 above.
   Standing: `UNKNOWN` (a real counter-example is named and file:line-cited,
   but no falsifier test was actually run this session to execute it —
   deliberately left as read-inspection evidence, per this repo's
   `absence-is-not-evidence.md`: an unexecuted counter-example is not the
   same claim as an executed one).
6. **"Removing the promoted capability returns the task to UNKNOWN without
   corrupting prior receipts."** — `PARTIAL_ALIVE` / `NOT_FOUND` split.
   `KnowledgeHookEngine.unregister_hook(hook_iri) -> bool` is a real,
   existing primitive (`hooks/engine.py:36`) — confirmed present, but grep
   over `src/` and `tests/` shows it is called from **nowhere** in this
   repo outside its own definition, so it is untested. `AuthorityBroker` has
   **no** revoke/deregister method at all (confirmed by reading
   `authority/broker.py` in full — only `register_grant`, `register_policy`,
   `evaluate`), so even a fully exercised `unregister_hook` would leave the
   corresponding `AuthorityGrant` live forever. The "returns to UNKNOWN"
   half of this falsifier is `NOT_FOUND` locally.

## Local execution (this session)

```text
$ .venv/bin/python -m pytest tests/sa2a/test_autonomic_closed_loop_lifecycle.py \
    tests/sa2a/test_unknown_bridge.py tests/sa2a/test_novelty_ingest.py \
    tests/sa2a/test_hook_synthesis.py -v
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
rootdir: /Users/sac/autofde-lab
configfile: pyproject.toml
collected 15 items

tests/sa2a/test_autonomic_closed_loop_lifecycle.py .                     [  6%]
tests/sa2a/test_unknown_bridge.py ...........                            [ 80%]
tests/sa2a/test_novelty_ingest.py ..                                     [ 93%]
tests/sa2a/test_hook_synthesis.py .                                      [100%]

============================== 15 passed in 1.01s ==============================
```

```text
$ grep -rn "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" \
    tests/sa2a/test_autonomic_closed_loop_lifecycle.py tests/sa2a/test_unknown_bridge.py \
    tests/sa2a/test_novelty_ingest.py tests/sa2a/test_hook_synthesis.py
(no output — zero matches; the closed-loop test's MockClusterActuator/
MockClusterVerifier are real hand-written implementations of an actuator/
verifier interface with real observable state (self.restarted_pods), not
interaction-verifying mocks — Chicago-legitimate per
.claude/rules/testing-chicago-style.md)
```

```text
$ grep -rn "unregister_hook" src/autofde_lab/sa2a/ tests/sa2a/
src/autofde_lab/sa2a/hooks/engine.py:36:    def unregister_hook(self, hook_iri: str) -> bool:
(only its own definition — zero call sites anywhere else)
```

```text
$ grep -n "def \|class " src/autofde_lab/sa2a/authority/broker.py
class AuthorityDecision / class AuthorityGrant / class ConsequenceRequest /
class AuthorityBroker: def __init__ / def register_grant / def register_policy /
def evaluate / def _matches_rule / def _check_constraints
(no revoke/deregister method exists)
```

## Definition of done (scoped to this repo's local surface only)

- The three currently-disjoint local pipelines (ingestion → admission court,
  machine-experience compiler, hook synthesizer/registration) are wired as
  one path where hook/grant promotion consumes an `AdmissionReceipt` or
  `ExperienceCompilationReceipt`, not raw hand-typed kwargs.
- `SynthesizedHookArtifact` and `ExperienceCompilationReceipt` carry explicit
  provenance fields: source evidence digest, generator identity, verification
  result (Law 4 closed locally).
- `MachineExperienceCompiler.compile_candidate_experience` rejects or
  requalifies a conflicting re-compile of an existing pattern instead of
  silently overwriting it (Law 7 / falsifier 5 closed locally), proven by a
  new Chicago test constructing exactly that conflict.
- `AuthorityBroker.revoke_grant(...)` exists and a new Chicago test exercises
  `unregister_hook` + `revoke_grant` together, proving routing returns to
  UNKNOWN while prior receipts remain unmodified (falsifier 6 closed
  locally).
- `tests/sa2a/test_autonomic_closed_loop_lifecycle.py`'s
  `runtime_tokens_cycle1 = 0` literal is replaced with a real instrumented
  count, mirroring `MachineExperienceCompiler`'s existing
  `_llm_calls_avoided` counter.
- None of the above is described as closing A2A-2612 itself, or as this
  repo acquiring admission/broker/actuation authority — only as this
  repo's local `sa2a/` testbed becoming internally consistent with the
  *shape* of the law it is falsifying, per
  `.claude/rules/ecosystem-boundary.md`.

## Local closure work (this session)

*(Placeholder — intentionally left for a second agent to append real
falsifier/test evidence next. Do not overwrite the sections above; append a
dated subsection here with the command run, its real output, and the
resulting standing change for each item under Definition of done.)*

### 2026-09-16 — Chicago falsifier #2, second-episode claim, tested directly

**Scope**: this pass tests exactly one thing — falsifier #2 ("An admitted
promotion creates a new deterministic route and the next matching episode
makes zero LLM calls"), specifically its *second-episode* half, which the
existing `tests/sa2a/test_autonomic_closed_loop_lifecycle.py` (re-read in
full before writing anything) does not exercise: that test runs Cycle 0
(refused) → Lab (ingest/synthesize/promote) → Cycle 1 (one reflex firing)
and stops. It never submits a *further* episode after promotion, and its
own zero-inference assertion (`runtime_tokens_cycle1 = 0`, line 192) is a
hardcoded integer literal compared to another hardcoded integer literal —
no call site is instrumented anywhere in that file. The
compiler-level instance of this falsifier
(`tests/sa2a/test_unknown_bridge.py::test_machine_experience_compiler_avoids_llm_inference`,
already `ALIVE` per the prior session's evidence above) is real and
measured, but is a different local module (`MachineExperienceCompiler`,
not the hook-synthesis/reflex-loop path this ticket scopes to) — it does
not substitute for a measurement on the closed-loop path.

**New test file** (written this session, not editing existing source):
`tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py`, two
tests, both using the real `HookSynthesizer`, `NoveltyIngestionGateway`,
`KnowledgeHookEngine`, `AuthorityBroker`, `ConsequenceBoundary`,
`ReactiveSemanticLoop` from `src/autofde_lab/sa2a/` — the identical
machinery `test_autonomic_closed_loop_lifecycle.py` uses. Counting is done
via two trivial real subclasses (`CountingHookSynthesizer`,
`CountingHookEngine`) that increment an integer and delegate to the real
parent implementation; no `unittest.mock`/`Mock`/`MagicMock`/`patch`/
`monkeypatch` anywhere, and the counters are read as final integer state
(exactly the `MockClusterActuator.restarted_pods` pattern the prior session
already called Chicago-legitimate), never asserted as interaction claims.

```text
$ .venv/bin/python -m pytest \
    tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py -v \
    -o addopts=""
============================= test session starts ==============================
collecting ... collected 2 items

tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py::test_second_matching_episode_via_reflex_loop_makes_zero_further_synthesis_calls PASSED [ 50%]
tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py::test_second_matching_episode_via_original_entry_point_bypasses_hook_entirely PASSED [100%]

============================== 2 passed in 0.90s ===============================
```

```text
$ grep -rn "unittest\.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" \
    tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py
tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py:20:``unittest.mock``/``Mock``/interaction verification; the counters are read as final
(one match, inside a docstring sentence naming the banned tokens to explain
why they are NOT used; zero real import or call of any of them — confirmed
by reading the file back)
```

**What the two tests actually measured**:

1. `test_second_matching_episode_via_reflex_loop_makes_zero_further_synthesis_calls`
   — episode 1 (novel incident → `REFUSED_NO_GRANT` → ingested →
   `CountingHookSynthesizer.synthesize_from_resolution` called once → hook +
   grant registered). Episode 2: a second, matching incident (same
   `action_iri`/`target_cap`, same `ex:status 'CRASH_LOOP'` delta) submitted
   through `ReactiveSemanticLoop.run_reflex_cycle` — the only real local code
   path that consults `KnowledgeHookEngine` at all. Result: hook fires, a
   real `EXECUTED` `FinalReceipt` is produced, `actuator.restarted_pods`
   grows to 1 — and `synthesizer.call_count` stays at **1** (real counted
   value, asserted, passed). `hook_engine.evaluate_call_count` was **2**, not
   1 as first assumed — `run_reflex_cycle`'s cascade loop calls `.evaluate()`
   once to fire the hook (depth 0) and once more on the resulting (empty,
   per `delta_generator=lambda r: ""`) delta to detect quiescence (depth 1);
   corrected in the test after the first run showed the real count (`2 == 1`
   `AssertionError`) rather than assuming the expected value.

2. `test_second_matching_episode_via_original_entry_point_bypasses_hook_entirely`
   — same episode-1 promotion, but episode 2 resubmitted through
   `ConsequenceBoundary.execute` directly (the exact entry point episode 0
   used when it was refused), with a `CountingHookEngine` constructed but
   deliberately **never wired into** `ConsequenceBoundary` or registered
   with the promoted hook. Result: episode 2 still succeeds
   (`EXECUTED`, `replayed=False` — a real second call, not an idempotency
   cache hit), `synthesizer.call_count` stays at 1, and
   `hook_engine.evaluate_call_count` is **0**. Confirmed by reading
   `src/autofde_lab/sa2a/brce/boundary.py` in full: `ConsequenceBoundary.execute`
   never references a hook engine anywhere in its pipeline (`boundary.py:154-322`)
   — episode 2 is authorized purely by `AuthorityBroker.evaluate` finding the
   registered `AuthorityGrant` by exact `(subject_id, action_iri,
   target_resource_iri)` tuple match (`authority/broker.py:206-214`).

**A third, exploratory, non-committed check** (real code run this session,
ad hoc via `.venv/bin/python -c ...`, not added as a pytest test — kept out
of the committed file because it targets a different, adjacent question
than the one this ticket assigned): does the reflex-loop path actually
discriminate a *matching* episode from a non-matching one? Submitting an
event delta with **no relation at all** to the promoted hook's
`trigger_predicate`/`trigger_value` (`ex:otherthing ex:unrelated 'X'`
instead of `ex:status 'CRASH_LOOP'`) through the same promoted hook/loop
still produced `quiescence_reached=True`, one step, and
`triggered_hooks=('probe_hook',)` — the hook fired anyway. Read-confirmed
why: `KnowledgeHookEngine.evaluate` (`hooks/engine.py:44-133`) only uses a
verdict from the real `GraphLawBridge.run_hooks` WASM call
(`admission/graphlaw_bridge.py:171-192`) when that call returns an entry
keyed by the exact hook IRI; a hook synthesized by `HookSynthesizer` has
`condition_query=""` (`synthesis.py:54-66` never sets it) and is never
registered into the WASM engine itself, so the WASM verdict lookup misses
and the code falls to the local Python fallback
(`hooks/engine.py:87-94`): `elif event_ttl.strip(): verdict = HookVerdict.FIRED`
— *any* non-empty event delta fires *every* registered `ASSERT` hook,
regardless of its content. This is real-execution evidence (a command run
this session with output observed, not source-inspection-only), so per
`.claude/rules/absence-is-not-evidence.md` it is admitted as observed, not
merely inferred.

**law_held = false**, with this precise gap_finding: the literal numeric
claim under test — "the next matching episode makes zero LLM calls" — DID
hold, with real counted evidence, on both real local entry points (0
additional `HookSynthesizer.synthesize_from_resolution` calls in both
tests). But the falsifier's stronger implied claim — that promotion
creates a **matching-episode-detecting deterministic route** that the next
similar episode is recognized by and dispatched through — is `NOT_FOUND`
locally, for two independent, named reasons:

1. **No matching-episode detection exists.** The reflex path
   (`KnowledgeHookEngine.evaluate` via its local Python fallback) fires a
   registered hook on *any* non-empty event delta, not selectively on deltas
   matching the hook's own `trigger_predicate`/`trigger_value` — confirmed
   by real execution with an unrelated delta, above. The zero-inference
   property holds, but not *because* the system recognized episode 2 as
   matching episode 1's pattern; it holds because nothing on this path was
   ever going to call the synthesizer regardless of match.
2. **No unified route registry exists.** Resubmitting the same kind of
   request through the *same entry point* the original episode used
   (`ConsequenceBoundary.execute`) never touches the promoted hook at all
   (`hook_engine.evaluate_call_count == 0`, real counted). Its zero-inference
   property comes from a structurally separate mechanism — exact
   `AuthorityGrant` tuple equality — with no code path that inspects "was
   this pattern promoted" before dispatching. A caller must already know to
   invoke `ReactiveSemanticLoop.run_reflex_cycle` specifically to exercise
   the hook at all; there is no single episode-submission surface that
   consults both mechanisms, still less one that keys on pattern identity.

Neither gap is a defect in the two passing tests — both pass, for real,
against real code. The gap is that "the next matching episode routes
through the newly promoted deterministic hook" describes a capability
(selective, pattern-matched dispatch through one registry) that this
repo's local `sa2a/` testbed does not implement; what it implements is two
separately-correct, non-selective mechanisms that happen to both avoid
calling the synthesizer again. Scoped per
`.claude/rules/ecosystem-boundary.md`: this is a finding about this
repo's local testbed only, not a claim about `ash_a2a`/`ggen`/`bcinr`/
`affidavit`'s upstream design for A2A-2612.

**Local standing for falsifier #2, corrected**: `PARTIAL_ALIVE`
(numeric zero-inference claim: `ALIVE`, real counted evidence, two routes;
matching-episode-detection / unified route registry: `NOT_FOUND`) —
replacing the prior session's `ALIVE` verdict, which was scoped to the
compiler module only (`MachineExperienceCompiler`, still accurately
`ALIVE`) and did not test the hook-synthesis/reflex-loop path this new
evidence covers.

## Local closure work (fix implemented)

### 2026-09-16 — content-blind local fallback fixed; falsifier converted to a real, committed test

**Scope**: this pass closes exactly one of the two named gaps under falsifier #2 above
(gap 1, "no matching-episode detection exists") — the `KnowledgeHookEngine.evaluate`
local Python fallback that fired *any* registered `ASSERT` hook on *any* non-empty
event delta, confirmed by the prior session's ad hoc, non-committed
`.venv/bin/python -c ...` check but never converted into a pytest falsifier. Gap 2
("no unified route registry exists" — `ConsequenceBoundary.execute` never consults a
hook engine at all) is unchanged and out of scope for this pass; it remains
`NOT_FOUND` per the prior session's finding.

**Root cause, confirmed by reading source before writing any fix** (matches the
`hooks/engine.py:87-94` finding above exactly): `KnowledgeHookDefinition`
(`hooks/model.py`) had no field capable of carrying a hook's own trigger
predicate/value — `HookSynthesizer.synthesize_from_resolution` (`hooks/synthesis.py`)
received `trigger_predicate`/`trigger_value` as parameters but only interpolated them
into the separate `graphlaw_rule_ttl` string it returns; it never stored them on the
`KnowledgeHookDefinition` it constructs. Since every synthesized hook's `condition_query`
is also always `""` and its `graphlaw_rule_ttl` is never merged into the graph
`GraphLawBridge.run_hooks` evaluates, the WASM verdict lookup misses every synthesized
hook's IRI unconditionally, so 100% of real evaluate() calls in this repo hit the local
Python fallback — which had no field left to check content against, so it fired on
delta non-emptiness alone.

**Fix** (three files, `src/autofde_lab/sa2a/hooks/`):

1. `model.py` — added `trigger_predicate: str | None = None` and
   `trigger_value: str | None = None` fields to `KnowledgeHookDefinition` (frozen
   dataclass with `slots=True`; additive, keyword-only at every existing construction
   site in this repo — confirmed by grepping every `KnowledgeHookDefinition(` call site
   in `src/` and `tests/` before editing, none use positional args).
2. `synthesis.py` — `synthesize_from_resolution` now passes
   `trigger_predicate=trigger_predicate, trigger_value=trigger_value` into the
   `KnowledgeHookDefinition` it constructs, so every hook manufactured by the real
   promotion path (`HookSynthesizer`) is self-describing about its own trigger
   condition, independent of the still-unfixed WASM-registration gap.
3. `engine.py` — `KnowledgeHookEngine.evaluate`'s local fallback branch (used only when
   the WASM verdict lookup misses a hook's IRI; the WASM path itself,
   `verdicts_by_iri.get(hook.iri)` hit branch, is **unchanged**) now calls a new
   `_local_fallback_condition_matches(hook, event_ttl)` static method before setting
   `HookVerdict.FIRED`: if the hook has both `trigger_predicate` and `trigger_value` set,
   it requires a real regex match (`predicate\s+['"]value['"]`) against the event
   delta's actual text; a hook with neither field set (every hand-constructed
   hook in this repo's existing CLI/benchmark/court call sites, which never passed
   these fields) preserves the pre-fix "fire on any non-empty delta" behavior, so no
   existing unconditioned-hook test needed to change.

**Test changes** (`tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py`,
the only test file touched):

- Updated the module docstring and
  `test_second_matching_episode_via_reflex_loop_makes_zero_further_synthesis_calls`'s
  docstring to state the corrected reason its "zero further synthesis calls" assertion
  holds: episode 2's delta (`ex:pod ex:status 'CRASH_LOOP'`) genuinely matches the
  promoted hook's own `trigger_predicate`/`trigger_value`, not because the fallback is
  content-blind. No assertions in this test changed — the real, counted outcome
  (`synthesizer.call_count == 1`, `hook_engine.evaluate_call_count == 2`) is identical
  before and after the fix, because episode 2 in that test was already a genuine content
  match; only the *mechanism* producing that outcome changed, and the docstring now says
  so honestly instead of leaving the old content-blind explanation standing.
- Added `test_unrelated_event_does_not_fire_promoted_hook` — the exact falsifier the
  prior session named as missing. Reuses the real `_run_first_episode_and_promote`
  helper (real `ConsequenceBoundary`, `NoveltyIngestionGateway`,
  `CountingHookSynthesizer`) to promote a hook with `trigger_predicate="ex:status"`,
  `trigger_value="CRASH_LOOP"`, then submits a second, real episode through the real
  `ReactiveSemanticLoop.run_reflex_cycle` with a delta asserting a genuinely unrelated
  predicate/value pair (`ex:otherthing ex:unrelated 'UNRELATED_SIGNAL'`). Asserts, all on
  real counted/observed state: `trace.quiescence_reached is True`,
  `len(trace.steps) == 0` (zero cascade steps — the hook never fired),
  `hook_engine.evaluate_call_count == 1` (one evaluate call, immediate quiescence, no
  second cascade-depth call), `synthesizer.call_count == 1` (no further synthesis), and
  `len(actuator.restarted_pods) == 0` (no unwarranted consequence). Zero
  `unittest.mock`/`Mock`/`MagicMock`/`patch`/`monkeypatch` — same real-collaborator
  pattern as the other two tests in this file.

**Local execution (this session)**:

```text
$ grep -rn "unittest\.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" \
    tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py
tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py:20:``unittest.mock``/``Mock``/interaction verification; the counters are read as final
(one match, inside a docstring sentence naming the banned tokens to explain why they
are NOT used -- zero real import or call of any of them)
```

```text
$ .venv/bin/python -m pytest \
    tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py -v -o addopts=""
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
rootdir: /Users/sac/autofde-lab
configfile: pyproject.toml
collecting ... collected 3 items

tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py::test_second_matching_episode_via_reflex_loop_makes_zero_further_synthesis_calls PASSED [ 33%]
tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py::test_second_matching_episode_via_original_entry_point_bypasses_hook_entirely PASSED [ 66%]
tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py::test_unrelated_event_does_not_fire_promoted_hook PASSED [100%]

============================== 3 passed in 0.95s ===============================
```

```text
$ .venv/bin/python -m pytest tests/sa2a/ -v --basetemp=/tmp/afl_fix_taskB \
    -k "hook or synthesis or novelty or autonomic or afde_2612"
collected 285 items / 238 deselected / 47 selected
tests/sa2a/conformance/test_court_logic_hook.py ........................ [ 51%]
......                                                                   [ 63%]
tests/sa2a/conformance/test_mutation_logic_hook.py ..                    [ 68%]
tests/sa2a/conformance/test_ocel_queries.py ..                           [ 72%]
tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py ...   [ 78%]
tests/sa2a/test_autonomic_closed_loop_lifecycle.py .                     [ 80%]
tests/sa2a/test_hook_synthesis.py .                                      [ 82%]
tests/sa2a/test_knowledge_hooks.py .....                                 [ 93%]
tests/sa2a/test_novelty_ingest.py ..                                     [ 97%]
tests/sa2a/test_v26_9_16_falsification_court.py .                        [100%]
====================== 47 passed, 238 deselected in 3.83s ======================
```

```text
$ .venv/bin/python -m pytest tests/sa2a/ -v --basetemp=/tmp/afl_fix_taskB_full
collected 285 items
... (29 files, all passed)
============================= 285 passed in 9.48s ==============================
```

The full `tests/sa2a/` run (285 items — every hook-consuming test in the repo; confirmed
by grep that no test outside `tests/sa2a/` imports `hooks.engine`, `hooks.model`,
`hooks.synthesis`, `KnowledgeHookEngine`, `HookSynthesizer`, or
`KnowledgeHookDefinition`) is a real regression check, not a targeted re-run: every
existing hook consumer that constructs a `KnowledgeHookDefinition` without
`trigger_predicate`/`trigger_value` (the CLI `hook evaluate`/`hook reflex` commands,
`conformance/benchmarks/harness.py`'s B3/cascade benchmarks,
`tests/sa2a/test_knowledge_hooks.py`, `tests/sa2a/conformance/test_court_logic_hook.py`
and `test_mutation_logic_hook.py`'s `_make_hook` helpers) was individually read and
confirmed, before running, to rely only on the preserved "no trigger condition ->
fire on any non-empty delta" backward-compatible branch, or to never assert on
`HookVerdict.FIRED` specifically (`test_court_logic_hook.py`/`test_mutation_logic_hook.py`
accept any of `{FIRED, NOT_FIRED, GATED}`) — the real 285/285 pass confirms that reading
was correct, not merely that it was plausible.

**Standing, this pass**: `ALIVE` for the specific claim "an unrelated event delta does
not fire a promoted hook via `KnowledgeHookEngine.evaluate`'s local Python fallback" —
real command run this session, real output above, real falsifier test passing against
the real fix. Gap 2 from the falsifier #2 finding above (no unified route registry
across `ReactiveSemanticLoop`/`ConsequenceBoundary`) is unchanged and remains
`NOT_FOUND`; nothing in this pass touched `ConsequenceBoundary.execute` or claims that
gap is closed. The WASM-path registration gap (synthesized hooks never actually get
their `graphlaw_rule_ttl` admitted into the real Praxis GraphLaw engine, so the WASM
verdict path is still, in practice, never hit for any hook this repo synthesizes) is
also unchanged — this fix hardens the local fallback that already carries 100% of real
traffic; it does not wire the WASM path itself, which was explicitly out of scope
("Preserve the existing WASM path unchanged; only harden the local fallback").

## Local closure work (WASM-path registration gap investigated, `BLOCKED`)

### 2026-09-16 — WASM hook-admission gap investigated end to end; found to be an upstream, out-of-scope defect, not a local wiring gap

**Scope**: this pass was assigned to wire `HookSynthesizer`/`KnowledgeHookEngine.register_hook`
so a synthesized hook's `graphlaw_rule_ttl`/`kh:Hook` definition is actually merged into the
graph `GraphLawBridge.run_hooks` evaluates, so the WASM verdict branch
(`KnowledgeHookEngine.evaluate`'s `if v_data:` arm, `hooks/engine.py:104-118`) can genuinely
hit for a matching hook instead of always missing and falling to the local fallback.

**Read in full before writing anything**: `src/autofde_lab/sa2a/hooks/{engine,synthesis,model}.py`
(re-confirmed current state, including the prior pass's `trigger_predicate`/`trigger_value`
fallback fix) and `src/autofde_lab/sa2a/admission/graphlaw_bridge.py`
(`GraphLawBridge.run_hooks`, the real Node.js/WASM bridge — no mock, real subprocess against
the real pinned `praxis_graphlaw_wasm_bg.wasm`,
`EXPECTED_ARTIFACT_SHA256 = 187688d9e7e33a575713d6911d75687adb38713ed37412e211af263dfcbe0c28`).

**Real-execution investigation, this session** (not source-inspection-only — every claim below
is backed by a command actually run and its output observed):

1. Read `~/praxis/crates/praxis-graphlaw-wasm/src/core.rs::run_hooks_core_impl`: it constructs
   `TripleStore::from(&preprocessed_base)` and later calls
   `hooks::evaluate_hooks(&post_store.hooks, &post_store, &delta, &[])` — so `post_store.hooks`
   (extracted from `kh:Hook`-shaped triples present in `base_ttl` at construction time,
   `~/praxis/crates/praxis-graphlaw/src/lib.rs:257-259`) is the ONLY way a hook can ever appear
   in `HookRunResult.verdicts`/`.schedule`. A separate N3 inference rule shaped like
   `HookSynthesizer`'s `graphlaw_rule_ttl` (an `{ ?s p 'v' } => { ... }` N3 rule, not a
   `kh:Hook a`-typed individual) does not by itself register as a hook at all — it would only
   ever assert a `kh:TriggeredHook` fact into the graph via `load_rules`/materialize, which
   `evaluate_hooks` never reads. The artifact that must be admitted is `hook.to_turtle()`
   (a real `kh:Hook`-shaped individual), not `graphlaw_rule_ttl`.
2. Read `~/praxis/crates/praxis-graphlaw/src/hooks/parsing.rs::validate_and_extract_hooks`
   and its `SHACL_LAW_PACK` (`~/praxis/crates/praxis-graphlaw/src/hooks/mod.rs:13-128`):
   `condition_kind="delta"` (this repo's only condition kind — `HookSynthesizer` never sets
   any other) requires `kh:var` (`parsing.rs:292-294`, `HookCondition::Delta { var }`), a field
   `KnowledgeHookDefinition.to_turtle()` never emits today (confirmed by re-reading
   `hooks/model.py::to_turtle` in full this session — no `kh:var` line exists). This alone
   would make any `to_turtle()` output fail admission with `"missing kh:var"`.
3. **Real execution against the real pinned WASM artifact**, via this repo's own
   `GraphLawBridge.run_hooks(base_ttl, event_ttl)` (`.venv/bin/python -c ...`, no mock, a real
   Node.js subprocess each call): even after hand-adding `kh:var` (fixing gap #2) and testing
   6 independent Turtle format variants (curie subject/prefixed predicates, full absolute IRIs
   with zero prefixes, single-line, multi-line, `a` vs explicit `rdf:type`, byte-identical
   reproduction of the upstream WASM crate's OWN reference fixture for a firing hook —
   `~/praxis/crates/praxis-graphlaw-wasm/tests/core.rs::test_run_hooks_core_fires_expected_hook`),
   `run_hooks` returned `{"status": "ADMITTED", "verdicts": [], "receipts": [], "schedule": []}`
   in **every single case** — the hook is never extracted into the engine's hook registry at
   all, regardless of exact Turtle serialization.
4. That upstream reference test's own assertion is deliberately weakened to tolerate this
   exact outcome (confirmed by reading `~/praxis/crates/praxis-graphlaw-wasm/tests/core.rs:283-288`
   verbatim): `assert!(hook_result.verdicts.is_empty() || !hook_result.schedule.is_empty(), "Result
   should have either no verdicts or populated schedule")`, with the comment "schedule may be
   empty depending on hook parsing/loading" — i.e. this is a known, pre-existing, upstream gap,
   not something this session's investigation introduced or could have avoided by better Turtle.
5. **Root cause isolated** via a real, temporary `cargo test` probe added directly to
   `~/praxis/crates/praxis-graphlaw/tests/zz_probe_afde2612.rs` this session (run once via
   `cargo test -p praxis-graphlaw --test zz_probe_afde2612 -- --nocapture`, then the file was
   deleted and `~/praxis`'s `Cargo.lock` churn reverted with `git checkout -- Cargo.lock` —
   `git status` in `~/praxis` is clean, confirmed, no tracked change was left in that repo):
   `TripleStore::from` decodes every plain string literal WITH its RDF 1.1 datatype suffix
   baked into the decoded text — e.g. `"assert"^^<http://www.w3.org/2001/XMLSchema#string>`
   instead of bare `assert`. Real probe output, verbatim:
   ```text
   PROBE triple_index.len() = 6
   PROBE hooks.len() = 0
   PROBE validate_and_extract_hooks ERR: hook:on must be assert, retract, or any, got: "assert"^^<http://www.w3.org/2001/XMLSchema#string>
   ```
   `hooks::parsing::clean_term` (`~/praxis/crates/praxis-graphlaw/src/hooks/parsing.rs:16-24`)
   only strips a surrounding bare `<...>` or bare `"..."` wrapper — it has no case for the
   compound `"value"^^<datatype>` form, so `HookProps::one_str` (`parsing.rs:88-94`) returns the
   literal WITH its datatype suffix still attached, and every exact-string match in
   `validate_and_extract_hooks` (`kh:on` at `parsing.rs:279`, `kh:kind` at `parsing.rs:286`)
   fails for every real hook, silently swallowed by `TripleStore::from`'s
   `.unwrap_or_default()` (`~/praxis/crates/praxis-graphlaw/src/lib.rs:257-259`) — which is
   exactly why `run_hooks` reports `ADMITTED` with an empty `schedule` instead of a visible
   error. Separately and independently confirmed (real execution, `validate_shacl` against
   `SHACL_LAW_PACK` via `bridge.validate_all(..., shacl_shapes=...)`): the underlying triple
   parsing itself is NOT the problem — a deliberately-invalid hook (missing `kh:name`, an extra
   disallowed `kh:bogus` property) correctly produces 2 real SHACL violations, proving `a` is
   correctly expanded to `rdf:type` and the hook's `kh:Hook` typing is correctly recognized at
   the triple level. The break is specifically in `hooks::parsing::clean_term`'s literal
   handling, downstream of correct triple parsing.

**Conclusion**: no Turtle serialization this repo could construct or merge into `base_ttl` —
via `HookSynthesizer`, hand-built, or copied verbatim from the upstream engine's own passing
fixture — can make `KnowledgeHookEngine.evaluate`'s WASM verdict branch fire, because the
defect is in hook *extraction* inside the vendored, pinned, content-addressed
`praxis-graphlaw`/`praxis-graphlaw-wasm` engine itself (`~/praxis`), a different repository this
project must not modify (`admission/graphlaw_bridge.py`'s own artifact-identity-discipline
docstring; `.claude/rules/ecosystem-boundary.md`). Per this repo's
`.claude/rules/absence-is-not-evidence.md`, forcing a Python-side "merge the hook's Turtle into
base_ttl" wiring change anyway — knowing it cannot make the WASM branch fire — would be exactly
the "fragile fix" this ticket's own instructions named as the thing not to do; it was not made.

**What was changed instead** (fix-forward, no functional/behavioral change, zero existing test
weakened):

1. `src/autofde_lab/sa2a/hooks/engine.py` — `_local_fallback_condition_matches`'s docstring
   corrected: it previously implied merging `graphlaw_rule_ttl` into the graph would suffice to
   make the WASM branch fire; it now states the fuller, real-execution-confirmed finding above,
   with file:line citations into `~/praxis`, so a future session does not re-attempt the same
   now-known-infeasible wiring from a stale comment. No behavior changed.
2. `tests/sa2a/test_afde_2612_wasm_admission_blocked.py` — **new file**, two real-execution
   falsifiers converting this finding into a permanent, executable regression fixture (per
   `.claude/rules/absence-is-not-evidence.md`: "an unexecuted counter-example is not the same
   claim as an executed one") rather than leaving it as prose only:
   - `test_real_wasm_engine_never_schedules_a_wellformed_matching_hook` — black-box: a real
     `GraphLawBridge()`, a hand-built WASM-format-correct `kh:Hook` Turtle (bypassing
     `to_turtle()`'s own separate, independently-confirmed gaps — no `kh:var`, and
     `kh:effect` value casing mismatch against the Rust engine's kebab-case vocabulary — to
     isolate the one decisive, unfixable-locally blocker), and a genuinely matching event.
     Asserts the real observed `schedule == []` / `verdicts == []`, with a comment telling a
     future reader exactly what a non-empty result there would mean (the upstream bug got
     fixed and repinned; AFDE-2612's WASM wiring may then be feasible).
   - `test_engine_evaluate_uses_local_fallback_not_wasm_even_when_hook_ttl_is_merged_into_base`
     — integration-level: a real `HookSynthesizer`-produced hook, a real `KnowledgeHookEngine`,
     the hook's Turtle deliberately merged into `base_ttl` (simulating the exact wiring this
     ticket asked for), for both a matching and a non-matching event. Proves the verdict that
     fires (correctly, per the prior pass's fix) comes from the LOCAL fallback, not WASM, via
     real observable state: `condition_hash == sha256("")` (the local fallback's own hash of
     the hook's always-empty `condition_query`) rather than a WASM-computed digest.

   Zero `unittest.mock`/`Mock`/`MagicMock`/`patch`/`monkeypatch` (grep output below).

**Local execution (this session)**:

```text
$ grep -rn "unittest\.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" \
    tests/sa2a/test_afde_2612_wasm_admission_blocked.py
tests/sa2a/test_afde_2612_wasm_admission_blocked.py:69:Zero ``unittest.mock``/``Mock``/``MagicMock``/``patch``/``monkeypatch``: both
(one match, inside the docstring sentence naming the banned tokens to explain why they are NOT
used -- zero real import or call of any of them)
```

```text
$ .venv/bin/python -m pytest tests/sa2a/ -k "hook or synthesis or novelty or autonomic or afde_2612 or graphlaw" -v --basetemp=/tmp/afl_finishE
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
rootdir: /Users/sac/autofde-lab
configfile: pyproject.toml
collected 301 items / 248 deselected / 53 selected

tests/sa2a/conformance/test_court_logic_hook.py ........................ [ 45%]
......                                                                   [ 56%]
tests/sa2a/conformance/test_mutation_logic_hook.py ..                    [ 60%]
tests/sa2a/conformance/test_ocel_queries.py ..                           [ 64%]
tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py ...   [ 69%]
tests/sa2a/test_afde_2612_wasm_admission_blocked.py ..                   [ 73%]
tests/sa2a/test_autonomic_closed_loop_lifecycle.py .                     [ 75%]
tests/sa2a/test_graphlaw_bridge.py ....                                  [ 83%]
tests/sa2a/test_hook_synthesis.py .                                      [ 84%]
tests/sa2a/test_knowledge_hooks.py .....                                 [ 94%]
tests/sa2a/test_novelty_ingest.py ..                                     [ 98%]
tests/sa2a/test_v26_9_16_falsification_court.py .                        [100%]

====================== 53 passed, 248 deselected in 5.13s ======================
```

```text
$ .venv/bin/python -m pytest tests/sa2a/ -v --basetemp=/tmp/afl_finishE_full
... (34 files)
============================= 301 passed in 13.13s ==============================
```

301/301 real, currently-passing — a genuine whole-`tests/sa2a/` regression check, not a
targeted re-run: the new file and the docstring-only edit to `engine.py` introduced zero
behavior change, confirmed by this identical-outcome full run.

**Standing, this pass**: `BLOCKED:UPSTREAM_PRAXIS_GRAPHLAW_LITERAL_DECODE` (per
`.claude/rules/standing-law.md`'s vocabulary) for "wire a synthesized hook's Turtle into the
graph `GraphLawBridge.run_hooks` evaluates so the WASM verdict branch can genuinely hit." The
precise, real-execution-confirmed blocker: `~/praxis`'s `hooks::parsing::clean_term` does not
strip the RDF 1.1 `^^<datatype>` suffix `TripleStore::from`'s own parse path bakes into every
decoded string literal, so `validate_and_extract_hooks`'s exact-string matches on `kh:on`/
`kh:kind` fail for every hook, for every caller, regardless of Turtle serialization — a defect
in a separate, pinned, content-addressed dependency this repo must not modify, not a wiring gap
local to `HookSynthesizer`/`KnowledgeHookEngine`. The local-fallback-only behavior (100% of real
hook verdicts in this repo come from `KnowledgeHookEngine.evaluate`'s local Python fallback,
never its WASM branch) remains the current, honestly-stated standing, now backed by two
permanent real-execution falsifiers (`tests/sa2a/test_afde_2612_wasm_admission_blocked.py`)
instead of prose alone, per `.claude/rules/absence-is-not-evidence.md` and
`.claude/rules/no-dual-bookkeeping.md`. Falsifier: if `~/praxis` fixes `clean_term`'s literal
handling and this repo's pinned `EXPECTED_ARTIFACT_SHA256` is updated to a rebuilt artifact,
`test_real_wasm_engine_never_schedules_a_wellformed_matching_hook`'s `schedule == []` assertion
would start failing — that failure is the signal AFDE-2612's WASM-path wiring has become
feasible and should be revisited, not a regression to silently patch around.
