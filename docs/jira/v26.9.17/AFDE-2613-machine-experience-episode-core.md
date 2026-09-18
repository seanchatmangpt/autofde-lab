# AFDE-2613 — v26.9.17 MachineExperience / Episode core (local closure)

**Status:** real, local, Chicago-tested closure of the single most load-bearing gap
against the pasted `AutoFDE Lab v26.9.17` PRD + Architecture Requirements Document
(ultracode session, 2026-09-17). Scoped narrowly and honestly — see §7 "Explicitly
NOT done" before citing this as broader coverage than it is.

## 1. What this closes

The user pasted a 64-section PRD and a matching Architecture Requirements Document
for `autofde-lab v26.9.17`, whose product thesis is:

```text
UNKNOWN --Episode1--> MachineExperience --Episode2--> KNOWN
ExploratoryInference(Episode_2) = 0
```

Before measuring, this session ran a 6-agent parallel gap-audit workflow
(`wf_30a3d307-c20`, `1,515,341` tokens, `219` tool calls, all 6 agents completed with
zero errors) that read the real `src/autofde_lab/sa2a/` subsystem (~15,784 lines
before this pass) against all ~90 numbered PRD/ARD requirements, citing exact
`file:line` evidence for every finding. Full transcript:
`/Users/sac/.claude/projects/-Users-sac-autofde-lab/805b2d1b-7d56-456a-b169-7ab879cabf6b/subagents/workflows/wf_30a3d307-c20/journal.jsonl`.

The audit's own synthesis, independently repeated across every one of its 6 clusters:

> "No `MachineExperience`/`CandidateMachineExperience` object exists anywhere... every
> other requirement in this cluster is blocked on this object existing first."
> "No `Episode1Runner`/`Episode2Runner` (or any composed orchestrator) exists anywhere
> in the codebase... This single gap is the root cause of ARD-16/20 being only
> `PARTIAL_ALIVE` and PRD-6.11/6.13/ARD-5.9 being `MISSING`."

This ticket closes exactly that one gap, for real, reusing the extensive existing
machinery the audit found (`AdmissionPipeline`, `CMCACandidateAllocator`,
`UnknownResolutionPipeline`, `ConsequenceBoundary`, `AuthorityBroker`, the disk
actuator/verifier/receipt-store already built for the Chicago conformance courts) —
per this repo's own "Architectural Rule: Reuse Before Construction" (ARD §4), nothing
in `experience/` or `episode/` reimplements admission, allocation, authority, or BRCE.

## 2. New code

```text
src/autofde_lab/sa2a/experience/
    types.py          ExperienceState enum + lawful transitions; MachineExperience (ARD §5.7)
    known_route.py     KnownRoute (ARD §5.8) + KnownRouteRegistry (real semantic-class +
                        equivalence-predicate lookup, PRD §6.9)
    compiler.py         ExperienceCompiler.compile() -> CANDIDATE MachineExperience (ARD §17),
                        decoupled ArtifactRegistry (fixes the "compiler self-admits" bug)
    admission.py         ExperienceAdmissionGate -> ADMITTED/REFUSED (ARD §18)
    qualification.py     ExperienceQualifier -> QUALIFIED -> ACTIVE + registers KnownRoute (ARD §19)
    invalidation.py      check_and_invalidate(): ARD §12 dependency-digest invalidation

src/autofde_lab/sa2a/episode/
    types.py          Episode (ARD §5.9), IntelligenceUsage (ARD §5.10), ExplorationMeter
                        (ARD §21), compute_frontier_clean + guarded_frontier_clean (ARD §22-23)
    equivalence.py       build_topic_equivalence_predicate(): real structural equivalence,
                        never string/digest identity (PRD §6.10)
    episode1.py          Episode1Runner (ARD §16): explore -> discover -> admit candidate ->
                        compile/admit/qualify experience -> authority -> BRCE -> receipt ->
                        OCEL, with a real per-stage JSON checkpoint
    episode2.py          Episode2Runner (ARD §20): fresh candidate -> admit -> classify via
                        KnownRouteRegistry.lookup() only (no discovery router call) -> SELECT
                        (real artifact.evaluate() probe) -> fresh authority -> fresh BRCE with a
                        FRESH idempotency_token -> receipt -> frontier_clean

src/autofde_lab/sa2a/cli.py   +episode1, +crown commands (crown runs the full Episode1->Episode2
                                loop and emits a PRD §63-shaped standing receipt)

tests/sa2a/experience/test_experience_lifecycle_chicago.py   7 tests
tests/sa2a/episode/test_episode_two_step_chicago.py          5 tests
```

## 3. Real, run-this-session evidence

End-to-end smoke proof (the exact commands run, not a description):

```text
$ .venv/bin/python -c "... Episode1Runner.run(...) then Episode2Runner.run(...) ..."
EPISODE 1: KNOWN EXECUTED ExperienceState.ACTIVE
EPISODE 2: KNOWN EXECUTED route_executed= True
frontier_clean: True
EPISODE 3 (non-equivalent): UNKNOWN
ALL EPISODE-LAYER SMOKE CHECKS PASSED
```

Chicago pytest suites, both real collaborators / zero mocks (`grep -rn
"unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" src/autofde_lab/sa2a/experience/
src/autofde_lab/sa2a/episode/ tests/sa2a/experience/ tests/sa2a/episode/` → 0 matches):

```text
$ .venv/bin/python -m pytest tests/sa2a/experience/ -v
7 passed in 2.38s

$ .venv/bin/python -m pytest tests/sa2a/episode/ -v
5 passed  [.....  100%, 0 F, 0 E]
```

Full regression, everything this pass touched plus everything pre-existing in the
same subsystem (`tests/sa2a/` + `tests/agent/`, clean `--basetemp` to sidestep an
unrelated, pre-existing `~/.cache/tmp` permission issue in this environment):

```text
$ .venv/bin/python -m pytest tests/sa2a/ tests/agent/ --basetemp=<scratch>/pytest-basetemp -q
439 dots, 0 F, 0 E, exit code 0
```

CLI surface, invoked the way this repo's own tests invoke Typer commands
(`typer.testing.CliRunner`, since `sa2a/cli.py` has no `__main__` guard —
pre-existing, unrelated to this pass, confirmed via `grep -n "__main__"` returning
zero matches before this pass touched the file):

```text
result = CliRunner().invoke(app, ["crown", "--work-dir", "<tmp>"])
result.exit_code == 0
episode_2.frontier_clean == true
```

## 4. What each falsifier actually proves

| Falsifier | PRD/ARD clause | Result |
|---|---|---|
| `test_compile_produces_candidate_state_never_auto_known` | §6.8: no auto-KNOWN | CANDIDATE state, empty `known_route_id` |
| `test_compile_refuses_unadmitted_candidate` | §6.7 provenance | `ValueError`, no experience constructed |
| `test_qualification_before_admission_is_refused` | §19 admission != KNOWN | REFUSED, no route registered |
| `test_known_route_lookup_is_semantic_class_not_prompt_similarity` | §6.9 | different-text-same-topic → found; different-topic → `None` |
| `test_invalidation_deactivates_route_when_dependency_digest_changes` | ARD §12 | ACTIVE → INVALIDATED, route deactivated |
| `test_experience_admission_refuses_when_artifact_missing_from_registry` | §18 meta-admission | REFUSED, `REFUSED_EXPERIENCE_ARTIFACT_NOT_FOUND` |
| `test_episode2_fresh_equivalent_request_resolves_known_with_zero_exploration` | §6.11-6.13, §22 | fresh identities, `frontier_clean=True` |
| `test_episode2_non_equivalent_candidate_is_unknown_not_a_false_known` | §6.9/6.10 | classification `UNKNOWN`, zero consequence |
| `test_episode2_before_any_episode1_is_unknown_not_a_crash` | §20 (no fallback to discovery) | `UNKNOWN`, no boundary call |
| `test_episode1_checkpoints_intermediate_state_for_crash_recovery` | ARD §16 | real JSON snapshot on disk, `last_completed_stage` |

## 5. Design decisions worth recording (so they aren't re-derived)

- **`ExperienceState` is its own enum**, not a reuse of `algebra.Standing` — QUALIFIED/
  ACTIVE/INVALIDATED/SUPERSEDED have no analogue in the generic envelope lifecycle.
  Mirrors `algebra.py`'s pattern (frozen enum + lawful-transitions table +
  `validate_*_transition`) rather than inventing a new shape.
- **`ExperienceCompiler` reuses `CompiledDeterministicRule`** (the real, good artifact
  type from `unknown/compilation.py`) but stores it in a *private*
  `ArtifactRegistry` the compiler owns, never the shared `_rule_registry` that class's
  own `resolve()` reads from — that decoupling is the actual fix for the audit's
  flagged PRD §6.8 violation ("compiling and becoming resolvable were the same
  event").
- **`Episode2Runner` requires an externally-supplied `experience_store`** (`dict[str,
  MachineExperience]`) to resolve `route.experience_id -> compiled_artifact_ids`,
  because `KnownRoute` (ARD §5.8) does not itself carry artifact ids. Documented as a
  deliberate, named narrowing in `episode2.py`'s docstring, not a silent one.
- **`RealDiskJournalActuator` / `IndependentDiskJournalVerifier` /
  `DurableDiskReceiptStore` are imported from
  `conformance.courts.consequence_court`**, not reimplemented a fourth time — the
  audit's own falsifiers-chicago-court-crown-cli cluster found **three** competing
  implementations of "the 12 Chicago gates" already exist in this repo
  (`ChicagoCrownQualificationRunner`, `scripts/verify_v26_9_16_chicago.py`, and the
  courts' own inline logic); this pass deliberately reuses one of them rather than
  adding a fourth.
- **`frontier_provider_requests`** (named only in ARD §22's formula, not in ARD §5.10's
  field list) is folded into `frontier_model_calls` in this implementation, with a
  docstring note in `episode/types.py` explaining why, rather than adding an unused
  field or silently dropping the clause.

## 6. Real regression numbers, honestly distinguished from pre-existing state

- `tests/sa2a/experience/` — new, 7/7 passed.
- `tests/sa2a/episode/` — new, 5/5 passed.
- `tests/sa2a/` + `tests/agent/` combined — 439 passed, 0 failed (up from the 425
  baseline recorded at this session's earlier AFDE-2604 fail-secure-closure pass;
  the delta includes both this ticket's 12 new tests and 2 tests added by the
  `feat/v26.9.17-cmca-dogfood-crown` branch merged into this branch earlier the same
  turn, unrelated to this ticket).
- `ruff` is **`UNSUPPORTED`** in this environment (`.venv/bin/ruff` and `uv run ruff`
  both report "No module named ruff" / "Failed to spawn: ruff") — an environment gate,
  not incomplete work; `py_compile` was run instead as a syntax sanity floor and
  passed for every new/modified file.
- `sa2a/cli.py`'s pre-existing lack of a `__main__` guard (`python -m
  autofde_lab.sa2a.cli ...` silently does nothing) predates this pass — confirmed via
  `grep -n "__main__" src/autofde_lab/sa2a/cli.py` returning zero matches both before
  and after this change (this pass only appended new commands, never touched the
  file's head). Not fixed here; named so it isn't rediscovered as a "new" bug.

## 7. Explicitly NOT done (named per this repo's standing-law, not silently implied closed)

The gap-audit workflow found ~90 requirements across 6 clusters; this ticket closes
the one root-blocking gap and everything structurally downstream of it for ONE
demonstrated semantic class. The following remain exactly as the audit found them —
`MISSING` or `PARTIAL_ALIVE`, not touched by this pass:

- ~~**`ExactSubject`/`SubjectResolver`/composition digest** (PRD §6.1-6.2, ARD §5.1,
  §6-7) — no multi-repo/artifact composition identity fence exists. `crown` in this
  pass runs a hardcoded, honestly-scoped single-class demonstration, not an arbitrary
  composition.~~ **CLOSED, same-session continuation (§8 below):**
  `sa2a/composition/` (`ExactSubject`, `SubjectResolver`) now real and wired into
  `crown` via `ReleaseRun`. Still scoped: structural/format validation of a declared
  manifest only, never a cross-repo fetch (per `.claude/rules/ecosystem-boundary.md`).
- ~~**`DiscoveryRouter`/Formal Machinery Router** (PRD §6.6, ARD §14-15) — `Episode1Runner`
  takes a caller-supplied `discover` callable; it does not itself select among formal
  search/local model/frontier model/DSPy/TPOT2/RL/GymAct.~~ **CLOSED, same-session
  continuation (§8 below):** `sa2a/unknown/router.py`'s `DiscoveryRouter` is real,
  precedence-ordered, and wired into `Episode1Runner` as an alternative to `discover`.
  Still scoped: does not itself wrap `fabric.pddl_engine`/`match_solvers` — a caller
  registers real engines.
- **`CompositionCourt`/transport-failure taxonomy/cross-repo standing** (ARD §42-44) —
  zero executable machinery; unrelated to this pass. **Still open.**
- **`ash_a2a` Integration Boundary** (ARD §27) — no real dispatch adapter into that
  runtime exists. **Still open.**
- **Consolidating the 3 duplicate Chicago-gate implementations** (ARD §50) — this pass
  reuses one of them (`consequence_court.py`'s real disk actuator/verifier/store) but
  does not collapse `ChicagoCrownQualificationRunner` /
  `scripts/verify_v26_9_16_chicago.py` / the courts' own inline gate logic into one.
  **Still open** — `ReleaseRun`'s own `CHICAGO_RUNNING` stage (§8 below) adds a
  *fourth*, narrower real-replay-and-fresh-consumer check rather than collapsing the
  existing three; named explicitly, not silently implied as a consolidation.
  **Update, 2026-09-17 tag-readiness closure pass (§10 below):** `ReleaseRun`
  now also invokes 14 real gate methods across `ConsequenceCourt`/`AuthorityCourt`
  directly (`CHICAGO_COURT_GATES_WIRED`) — the previously-named gap ("the
  pre-existing 12-gate Chicago court was never wired into `ReleaseRun`") is closed,
  but this is still a **fifth** real invocation path, not a consolidation of the
  existing three/four. Consolidation itself **remains open.**
- ~~**Release-level state machine** (PRD §12: `CREATED -> SUBJECT_FENCED -> ... ->
  CROWNED`) — `Episode`/`MachineExperience` each carry their own lifecycle; no
  release-scoped wrapper state machine was built.~~ **CLOSED, same-session
  continuation (§8 below):** `sa2a/release/state_machine.py`'s `ReleaseState` +
  `ReleaseRun` implement the exact PRD §12 sequence with typed exits, real transition
  validation (no skipped predecessor).
- ~~**Additional `Receipt` subtypes** (`AllocationReceipt`, `ManufacturingReceipt`,
  `QualificationReceipt`, `CompositionReceipt`, `VerificationReceipt` — ARD §30) — this
  pass's `qualification_receipt`/`receipt_id` fields are plain strings, not distinct
  typed receipt classes.~~ **PARTIALLY CLOSED, 2026-09-17 tag-readiness closure pass
  (§10 below):** `CompositionReceipt` is now a real standalone dataclass
  (`sa2a/composition/receipt.py`), independently digest-sensitive to both episodes'
  final-receipt and OCEL digests. `AllocationReceipt`/`ManufacturingReceipt`/
  `QualificationReceipt`/`VerificationReceipt` remain plain fields, not distinct
  typed classes. **Still open for the other 4.**
- **Mutation-vacuousness tooling** for the falsifier corpus (PRD §6.25's own meta-check)
  — not built. **Still open.**
- **A general-purpose `DiscoveryRouter`-selectable CLI** for arbitrary semantic classes
  — `episode1`/`crown` CLI commands are scoped to the one demonstrated class
  (`requires-port`), documented as such in their own docstrings/scope_note field.
  **Still open** — `DiscoveryRouter` (§8 below) is real and wired into
  `Episode1Runner`, but no CLI surface lets an operator register engines or pick a
  different semantic class at the command line.
- **ARD §45's exact `verify_standing(exact_subject, receipts, ocel, manifests,
  postcondition_evidence) -> PASS|FAIL|INCOMPLETE` function signature** — **PARTIALLY
  CLOSED, same-session continuation (§8 below):** a real, subprocess-isolated
  fresh-consumer verifier now exists (`sa2a/release/fresh_consumer.py`), the single
  strongest gap the original audit named ("ReplayCourt.verify_fresh_consumer_isolation
  only does in-process `del`... not a subprocess boundary"). Its function/verdict
  vocabulary (`CONFORMANT_EVIDENCE_RECONSTRUCTED` / `UNKNOWN:...`) differs from the
  ARD's literal `verify_standing(...)`/`PASS|FAIL|INCOMPLETE` naming — a deliberate,
  named divergence (this repo's own `standing-law.md` vocabulary), not an oversight.

## 8. 2026-09-17 continuation ("ultracode finish") — composition, release state
machine, real subprocess fresh-consumer verifier, DiscoveryRouter

Same session, same branch, following the "ultracode finish" instruction to continue
closing the §7 list above. Reuses everything §1-7 built without modification except
one real bug found and fixed while building this continuation (see below).

### New code

```text
src/autofde_lab/sa2a/composition/
    exact_subject.py    ExactSubject (ARD §5.1) + composition_digest
    resolver.py           SubjectResolver.resolve() (ARD §6), fail-closed on floating
                          branch refs / missing digests / conflicting or ambiguous
                          repository identity; resolve_self_identity() for this repo's
                          own real, local git identity

src/autofde_lab/sa2a/release/
    state_machine.py     ReleaseState (PRD §12's exact 11-state sequence + 6 typed
                          exits), validate_release_transition() enforced for real
    fresh_consumer.py     A REAL, SEPARATE-PROCESS fresh-consumer verifier (ARD §45),
                          porting hub/domain/gym_procedure/standalone_verifier.py's
                          exact discipline (explicit typed O2O edges only, an
                          assert_no_runtime_imports() self-check) to the Episode1/
                          Episode2 checkpoint+OCEL evidence. frontier_clean is
                          RE-DERIVED from raw counters and compared against the
                          producer's stored value, never trusted.
    run.py                 ReleaseRun: subject_fence -> preflight -> episode1 ->
                          experience_admitted -> episode2 -> CHICAGO_RUNNING (real
                          ReplayEngine.verify_chain() + a real subprocess call to
                          fresh_consumer.py) -> EVIDENCE_VALIDATED -> CROWNED, or a
                          typed exit at any stage. ARD §50-conformant: every stage
                          calls an already-real component, computes no verdict itself.

src/autofde_lab/sa2a/unknown/router.py   DiscoveryRouter (ARD §14-15): precedence-
                          ordered engine selection (exact machinery -> composition ->
                          formal planner/solver -> bounded local synthesis -> general
                          exploratory intelligence), candidate-only by construction.

src/autofde_lab/sa2a/episode/episode1.py   Episode1Runner.run() now accepts EITHER
                          discover= OR discovery_router= (exactly one); a router with
                          no matching engine ends the episode UNKNOWN, never crashes.
src/autofde_lab/sa2a/episode/episode2.py   Real bug fixed: Episode2Runner never
                          persisted a checkpoint JSON or OCEL evidence (only Episode1
                          did) -- the fresh-consumer verifier needs both episodes'
                          durable evidence, so this was a real, load-bearing gap this
                          continuation found and closed, not a pre-existing known item.

src/autofde_lab/sa2a/cli.py   `crown` upgraded to run the real ReleaseRun state
                          machine (was: ad hoc Episode1Runner+Episode2Runner wiring
                          with no subject fence, no replay check, no fresh-consumer
                          check) -- a strict superset of the prior behavior.

tests/sa2a/composition/test_subject_resolver_chicago.py    9 tests
tests/sa2a/release/test_release_run_chicago.py               6 tests
tests/sa2a/test_discovery_router_chicago.py                   5 tests [CORRECTED 2026-09-17: real count
                                                               is 8 -- 3 more tests were added to this
                                                               file during the later §9 QUALIFICATION
                                                               pass without this line being updated;
                                                               caught by the tag-readiness audit's own
                                                               `pytest --collect-only`, not self-reported]
tests/sa2a/episode/test_episode_two_step_chicago.py           +3 tests (DiscoveryRouter integration)
```

### A real bug found and fixed while building this continuation

`release/__init__.py`'s first draft re-exported `ReleaseRun` at package scope. Since
`python -m autofde_lab.sa2a.release.fresh_consumer` executes `release/__init__.py`
*before* the `fresh_consumer` submodule itself, that import transitively pulled in
`episode1`/`episode2` — so the "independent, separate-process" fresh-consumer
verifier's own `assert_no_runtime_imports()` self-check correctly caught that it was
NOT independent, even running as a genuine subprocess. Confirmed via direct
reproduction (`RuntimeError: VERIFIER_NOT_INDEPENDENT: ... ['autofde_lab.sa2a.episode.
episode1', ...]`) before fixing. Fix: `release/__init__.py` re-exports only
`ReleaseState` (zero episode/experience imports); callers import `ReleaseRun` directly
from `autofde_lab.sa2a.release.run`. `test_fresh_consumer_is_a_genuinely_separate_
process_not_an_in_process_call` pins this regression.

### Real, run-this-session evidence

Full crown via the real CLI invocation path (`typer.testing.CliRunner`, matching this
repo's existing test convention — `sa2a/cli.py` still has no `__main__` guard,
pre-existing and unrelated):

```text
EXIT CODE: 0
standing: CROWNED
history: ['CREATED', 'SUBJECT_FENCED', 'PREFLIGHTED', 'EPISODE_1_RUNNING',
  'EPISODE_1_VERIFIED', 'EXPERIENCE_ADMITTED', 'EPISODE_2_RUNNING',
  'EPISODE_2_VERIFIED', 'CHICAGO_RUNNING', 'EVIDENCE_VALIDATED', 'CROWNED']
composition_digest: 2103d014eb8c48c124a578f2bf9a218041d72b9a71c6bfe78716b5e787556b04
episode_2 frontier_clean: True
```

Falsifiers, all real and passing: a manifest with a floating branch ref (`exact_sha:
"main"`) REFUSES before `SUBJECT_FENCED`; a manifest pinning this repo at
`dirty:<sha>` reaches `SUBJECT_FENCED` then BLOCKs at `PREFLIGHTED`, before Episode 1
ever runs (ARD §61); `CROWNED` itself is verified terminal (cannot transition to
`REFUSED`/`NONCONFORMANT` after the fact); `DiscoveryRouter` prefers
`EXACT_REUSABLE_MACHINERY` over `GENERAL_EXPLORATORY_INTELLIGENCE` even when both are
registered and both would answer, confirmed by asserting the general-exploratory
callable is never invoked.

`.venv/bin/python -m pytest tests/sa2a/composition/ tests/sa2a/release/
tests/sa2a/test_discovery_router_chicago.py tests/sa2a/episode/ tests/sa2a/experience/`
-> **37 passed, 0 failed**. Full regression `tests/sa2a/ tests/agent/` -> **462
passed, 0 failed** (up from 439 at the start of this continuation; delta is exactly
this section's 23 new tests). Mock-grep over every file touched this continuation ->
zero matches. `py_compile` sanity pass -> clean (`ruff` remains `UNSUPPORTED` in this
environment, unchanged from §6).

## 9. 2026-09-17 QUALIFICATION pass ("ultracode harden, benchmark, stress test")

Per `~/.claude/rules/local-dfcm-manufacturing-engine.md`'s QUALIFICATION mode: "try
aggressively to falsify/break the manufactured claims before they're reported as
done." Two rounds, same session:

**Round A (direct, before dispatching agents)** — close reading of the §8 code
surfaced 5 real crash bugs, fixed directly: `SubjectResolver.resolve()` raised a raw
`AttributeError`/`TypeError` on a malformed manifest shape (a string where
`repositories` should be a list, non-dict entries, or `candidate_manifest` itself not
Mapping-like) instead of its own promised typed refusal — now
`SubjectResolutionError(REFUSED_MALFORMED_MANIFEST, ...)`.
`release/fresh_consumer.py` — the trust-anchor verifier — raised
`json.JSONDecodeError` on a truncated/corrupt checkpoint file instead of degrading to
a typed verdict — now a `_Corrupt` sentinel + `IndependentStanding.artifacts_corrupt`
(distinguished from genuine absence, never conflated). `KnownRouteRegistry.lookup()`
and `DiscoveryRouter.route()` both propagated an exception raised by a
caller-registered predicate/engine instead of degrading to "this one rejects, try the
next" — both now catch and continue.  `Episode1Runner.run()` propagated an exception
from a caller-supplied `discover` callable instead of a clean UNKNOWN episode — now
routed through a shared `_no_candidate_result()` helper
(`REFUSED_DISCOVER_CALLABLE_RAISED`). Pinned by
`tests/sa2a/test_v26_9_17_hardening_chicago.py` (8 tests).

**Round B (6-agent parallel workflow, `wf_a24a0fed-45f`, 1,579,152 tokens, 281 tool
calls, 6/6 completed, 0 errors)** — 4 agents in a `Harden` phase (disjoint file
ownership: composition/, release/state_machine.py+run.py,
release/fresh_consumer.py, unknown/router.py+experience/), then 2 agents in a
`StressAndBenchmark` phase (concurrency stress, real benchmarking). Every finding
below was independently re-verified by the orchestrator after the workflow completed
— real commands re-run, real output re-observed, not taken on the agents' self-report
alone (per this repo's own `.claude/rules/no-dual-bookkeeping.md`).

### Real bugs found and fixed (Round B)

- `SubjectResolver._resolve_artifacts` had no conflict check for two entries
  sharing one `artifact_id` with two different `digest` values — both were silently
  admitted into `ExactSubject.artifacts`, defeating the entire point of an *exact*
  composition identity. Now `REFUSED_CONFLICTING_ARTIFACT_DIGEST`, mirroring the
  repository-SHA conflict check.
- `ReleaseRun.run()` called a second time on the same instance raised an uncaught
  `ValueError` from `validate_release_transition` ("cannot go from CROWNED to
  SUBJECT_FENCED"). Now returns a clean `REFUSED:ALREADY_RUN` result — `ReleaseRun`
  is explicitly single-use by design, and a caller attempting a second run now gets a
  typed answer instead of a crash.
- `ReleaseRun._run_fresh_consumer`'s `subprocess.run(...)` call had no `timeout=` —
  a pathological input could hang the fresh-consumer subprocess and hang the entire
  crown forever. Now bounded.
- `fresh_consumer.py`'s `_ocel_event_objects()` crashed with `AttributeError` on
  several malformed-but-VALID-JSON OCEL shapes (`events` not a list, an event not a
  dict, `relationships` not a list or containing non-dict entries) — confirmed live
  pre-fix. Now every non-conforming shape degrades to "this edge cannot be
  established" in place, never an exception escaping `verify()` — reconfirmed via
  real **mutation testing of all 7 required chain edges** (per
  `.claude/rules/level4-completion-law.md`'s Mutation law: construct a real,
  complete, conformant Episode1→Episode2 evidence pair via the real runners, mutate
  exactly one edge's identity, require the verifier to report exactly that edge
  broken) — `tests/sa2a/release/test_fresh_consumer_mutation_chicago.py`, 15 tests,
  independently re-run by the orchestrator: **15 passed**.
- `DiscoveryRouter.route()` accepted ANY non-`None` return from a misbehaving
  engine at face value — an engine returning a bare string or int instead of a real
  `CandidateResolution` was passed downstream as if it were one, crashing
  `Episode1Runner.run()`'s first real-attribute read (`candidate.consumed_tokens`)
  with `AttributeError` — confirmed live pre-fix. Now `isinstance(candidate,
  CandidateResolution)` validated at the boundary; a violation is recorded in a new
  `errored_engine_ids` field (same treatment as a raising engine) and routing falls
  through.
- `ArtifactRegistry.store()` silently overwrote on a genuine `rule_id` collision.
  Now refuses a true collision (different content, same id) while remaining
  idempotent for a byte-identical re-store.
- **`KnownRouteRegistry` had no synchronization at all** — a plain `dict`/`list`
  read/written by `register_route()`/`lookup()`/`deactivate()` with zero locking.
  Fixed with a `threading.RLock` guarding every method that touches
  `_routes_by_class`/`_predicates`; `lookup()` snapshots under the lock and releases
  it before invoking any caller-supplied predicate (foreign code never runs while
  holding this registry's lock).

### Real bugs found and left deliberately open (named, not silently absorbed)

- **A confirmed, live, reproducible lost-update race in
  `RealDiskJournalActuator.actuate()`** (`conformance/courts/consequence_court.py`):
  an unsynchronized read-json→append→atomic-`os.replace()` sequence on a journal
  file shared across concurrent `Episode1Runner`/`Episode2Runner` instances — the
  exact sharing pattern `ReleaseRun.run()` itself uses across its own two episodes,
  and that multiple concurrent crown runs against one `work_dir` would share too.
  Real 8-thread × 5-trial stress test: the agent's run showed **42 of 67** attempted
  actuations' journal records lost; the orchestrator's own independent re-run of the
  same test immediately after showed **42 of 67** lost again. Individual file writes
  stay torn-write-safe (`os.replace()` is atomic; zero JSON parse errors in any
  trial) — the compound read-modify-write is not. **Fails closed, not silently
  wrong**: the losing thread's own `IndependentDiskJournalVerifier` correctly reads
  a different thread's entry and reports `success=False`/`UNKNOWN_OUTCOME` rather
  than a false `EXECUTED` — zero silent wrong-answers observed across all trials.
  **Deliberately not fixed**: `RealDiskJournalActuator`/`DurableDiskReceiptStore`
  are constructed at call sites across 5 `src/` modules and imported by 20+18 test
  files respectively; a correct fix needs a lock keyed by the resolved
  `journal_path`/`store_dir` (today's instances share no Python-level state), which
  is exactly the shared-infrastructure-internals change this pass's own scoping
  excluded. This is the same class of finding, against the same root cause, that
  `docs/jira/v26.9.16/AFDE-2604-admission-fencing-local-closure.md` names as Lens
  4's R1/R2/R3 (TOCTOU/concurrency) — deliberately left `SURVIVED`/open there for
  the identical reason. This pass reproduces it fresh against the v26.9.17 crown
  path specifically and records it as the same still-open gap, not a new one.
- **`DiscoveryRouter.route()`'s O(5·N) worst-case scan** — each of the 5 precedence
  tiers re-walks the *entire* `self._engines` list rather than using a
  kind-indexed structure (unlike `KnownRouteRegistry`'s own class-indexed design one
  file over). Not a correctness bug (still returns the right, precedence-ordered
  answer every time) — a confirmed real inefficiency: **0.0064ms→0.34ms** measured
  across 10→1000 registered engines (worst case). Left open: fixing it means
  editing `unknown/router.py`, outside the benchmark phase's read-only-of-source
  scope.
- **`DurableDiskReceiptStore.__init__()`'s O(N) construction cost**, confirmed by
  real measurement (not just theorized as it was when the audit first predicted it
  in §7 above): `_sync_from_disk()` re-reads and `json.loads()`s *every* existing
  `prep_*.json`/`final_*.json` file on every construction, and `Episode1Runner`/
  `Episode2Runner` each construct a fresh store per `run()` call against a
  potentially long-lived shared `receipt_store_dir`. Real numbers: **0.06ms @ 0
  files → 0.72ms @ 10 → 8.04ms @ 100 → 91.2ms @ 1000** (≈0.09ms/file, roughly
  linear). The orchestrator's own quick re-run of the benchmark script confirmed the
  same shape (0.09/1.4/6.2ms @ 0/10/100). This is the single largest confirmed
  performance liability in the whole v26.9.17 crown for any workload that runs many
  episodes against one long-lived `receipt_store_dir` (e.g. a production crown loop)
  — named precisely, left open for the same shared-infrastructure reason as the race
  above.

### Confirmed already-correct (real adversarial tests, no fix needed — also real information)

Unicode/control-character/10000+-char strings in manifest fields (safe, no crash, no
truncation); uppercase-hex SHAs correctly `REFUSED_FLOATING_REPOSITORY_REF` (matches
real, verified `git rev-parse` output, which is always lowercase); 3000+ repository
entries resolve without quadratic blowup; `resolve_self_identity()` against a
non-git directory raises a real, typed `subprocess.CalledProcessError` (judged
acceptable, not wrapped); no `shell=True` anywhere in `composition/`, confirmed via a
real injection probe using a directory name containing shell metacharacters;
`composition_digest` is stable across dict-key-order and JSON-round-trip variation;
whitespace-only artifact digests correctly refused; `KnownRouteRegistry.lookup()` is
O(routes-in-target-class), not O(all-routes-ever-registered) — confirmed via real
timing at 1050 routes across 50 classes (1.19µs/lookup); `MachineExperience.
is_invalidated_by()` correctly treats an *absent* current digest as "changed"
(fail-closed, matching `.claude/rules/absence-is-not-evidence.md`) rather than
silently passing; `ReleaseState`'s `BUILD_BROKEN`/`UNSUPPORTED` exits are declared,
lawful, but currently **unreachable dead states** — `ReleaseRun.run()` never actually
transitions to either (named explicitly, not fixed — out of this pass's scope to add
new triggering logic).

### Real, measured benchmark numbers (never estimated)

| Metric | Value |
|---|---|
| Full crown (`ReleaseRun.run()`), mean | 449.4ms |
| — of which: `fresh_consumer` subprocess spawn | 413.6ms (**92%** of total) |
| `Episode1Runner.run()`, end to end, mean | 4.77ms |
| `Episode2Runner.run()`, isolated, mean | 3.32ms |
| `KnownRouteRegistry.lookup()`, worst case @ 10 / 10,000 routes | 0.0003ms / 0.0309ms |
| `DiscoveryRouter.route()`, worst case @ 10 / 1,000 engines | 0.0064ms / 0.34ms |
| `DurableDiskReceiptStore()` construction @ 0 / 1,000 files | 0.06ms / 91.2ms |

Full tables and exact reproduction commands: `docs/jira/v26.9.17/benchmarks/
latency-and-scaling.md` and `docs/jira/v26.9.17/benchmarks/
concurrency-stress-findings.md`. Benchmark script:
`tests/sa2a/benchmarks/bench_v26_9_17_crown.py` (supports `--full` for the larger
scale tiers). Both re-run independently by the orchestrator after the workflow
completed, producing the same shape of numbers (not identical — different machine
load — but the same confirmed scaling behavior).

### Verification

Mock-grep across every file touched in both rounds (`composition/`, `release/`,
`unknown/router.py`, `episode/episode1.py`, `experience/*`, every new test file) →
**zero matches**, independently re-run by the orchestrator. Full regression
`tests/sa2a/ tests/agent/`, independently re-run by the orchestrator with a clean
`--basetemp` → **531 passed, 0 failed** (up from 470 at the start of this
QUALIFICATION pass — 470 itself already included the earlier Round A fixes' 8
tests; delta of 61 real new tests from Round B alone). `py_compile` unaffected;
`ruff` remains `UNSUPPORTED` in this environment.

## 10. 2026-09-17 tag-readiness closure pass ("ultracode implement all then validate ALIVE using act and kind")

Continuation of the tag-readiness audit committed at `36eb50da` (that commit closed
2 undocumented bugs found by the audit; this pass closes the audit's remaining
5 PRD §14 + 3 ARD §64 `PARTIAL_ALIVE` items, all pre-scoped and named — never
`MISSING`, always "mechanism real, demonstrated release candidate doesn't fully
carry it yet"). Per the same audit (`commit-msg-tag-readiness.txt`, superseded by
this section — kept on disk as raw audit evidence, not restated verbatim here):

1. `crown` used a hardcoded `discover()` callable instead of the already-built,
   Chicago-tested `DiscoveryRouter`.
2. The pre-existing 12-gate Chicago court (`ConsequenceCourt`/`AuthorityCourt`) was
   never invoked by `ReleaseRun`.
3. No standalone `CompositionReceipt`/`ManufacturingReceipt` type existed — digests
   were plain fields inside a combined JSON blob, not an independently verifiable
   receipt object.
4. No real fresh-instance *generator* existed for Episode 2's candidate — only an
   equivalence *checker* (`episode/equivalence.py`).

### 2-agent parallel workflow (`wf_wzw3ryfpi`-lineage, file-disjoint ownership, 0 errors)

**Agent 1 (`discoveryAndGenerator`)** — `sa2a/episode/generator.py` (new):
`generate_fresh_equivalent_candidate()`, a real deterministic structural
substitution over an 8-entry subject pool (module docstring states explicitly: not
an LLM call). `cli.py`'s `crown`/`episode1` commands now construct a real
`DiscoveryRouter` with 2 real `DiscoveryEngine`s and pass it as
`discovery_router=` to `Episode1Runner.run()`, replacing the hardcoded `discover()`
callable. 12 new tests (`tests/sa2a/episode/test_generator_chicago.py`,
`tests/sa2a/test_discovery_router_chicago.py` additions).

**Agent 2 (`receiptChicagoFalsifiers`)** — `sa2a/composition/receipt.py` (new):
`CompositionReceipt` dataclass + `build_composition_receipt()`, digest-sensitive to
both episodes' final-receipt and OCEL digests independently of the shared
`composition_digest`. `sa2a/admission/falsifier_corpus.py` (new):
`run_falsifier_corpus()` composing the real 5-falsifier `FalsifierSuite` (5
adversarial RDF fixtures) + 2 real `SubjectResolver` checks = 7 mandatory
falsifiers, returning a `FalsifierCorpusVerdict` with a real `corpus_digest` and
`survived_falsifier_ids`. `release/run.py`'s `CHICAGO_RUNNING` stage extended to
call 14 real gate methods across 2 of the 6 real court classes (5 from
`ConsequenceCourt`, 9 from `AuthorityCourt`) via `ReleaseRun.CHICAGO_COURT_GATES_WIRED`
— composed by direct method call per ARD §50 ("crown = orchestration only, no
duplicated semantic logic"), never reimplemented. A second registry,
`CHICAGO_COURT_GATES_NOT_APPLICABLE`, names exactly why `IdentityCourt` (its git-SHA
check would falsely `NONCONFORMANT` the demo's synthetic `"a"*40` fixture SHA
against this checkout's real HEAD), `AdmissionCourt` (reused separately via the
falsifier-corpus work instead), `LogicHookCourt`, and `ReplayCourt`'s own
court-wrapper (its `__init__` always constructs a real `AuthorityBroker` that
can't reproduce this crown's deliberate grant-id skip-semantics) were judged
not-applicable — each with a real, source-verified reason, not a guess.

### Independent re-verification (orchestrator, not the agents' self-report)

- `tests/sa2a/ tests/agent/` — **578 passed, 0 failed** (up from 533 at the audit
  commit). Mock-grep across all 10 touched/created files — zero matches.
- A standalone script invoking the real `crown` CLI (`typer.testing.CliRunner`)
  confirmed all 5 new claims live in one real run: `discovery_routing.
  exact_reusable_machinery_selected: true` (not the fallback engine);
  `episode2_generated_candidate` genuinely differs from the seed
  (`candidate_id`/`proposed_assertion`/`source_identity` all distinct, topic token
  preserved); `composition_receipt` present with a real computed
  `composition_receipt_digest`; `falsifier_corpus.all_mandatory_caught: true`,
  `survived_falsifier_ids: []`; all 14 `chicago_court_gates` entries `true`.
- Ran `crown` twice independently: `composition_digest` identical across both runs,
  `composition_receipt_digest` genuinely different (`457c095e...` vs
  `0b8040d8...`) — the receipt is sensitive to per-run episode digests, not just
  the shared composition identity, confirmed by observation rather than by
  construction.
- `grep`-confirmed `release/run.py` contains 14 real `.audit_*`/`.verify_*` method
  calls against `ConsequenceCourt()`/`AuthorityCourt()` instances matching the 14
  reported gate IDs exactly — not fabricated booleans.
- `tests/sa2a/test_falsifier_corpus_chicago.py::test_all_mandatory_caught_is_false_when_any_trial_survived`
  independently confirmed the corpus can genuinely detect and report a survived
  falsifier (`assert verdict.survived_falsifier_ids == ("B",)`) — not hardcoded to
  always pass.

**Scope decision, named not silently dropped**: `cli.py`'s pre-existing hardcoded
manifest field `falsifier_corpus_digest: "d" * 64` is deliberately not
cross-validated against the new `compute_falsifier_corpus_digest()`'s real value —
different identities (a declared corpus-revision claim on `ExactSubject` vs. this
runner's own real corpus-content digest). Left open for a future pass.

### Correction to Agent 1's own report (orchestrator finding, not an agent finding)

Agent 1 reported ARD-64 items 7 ("prove instance routes through KNOWN") and 8
("positively execute the known route") as `STILL_MISSING`, reasoning honestly from
its own context limits — a fresh agent has no access to the literal PRD/ARD text,
which exists only as a conversation paste, never a repo file. That report does not
hold: both items were already scored `ALIVE` in the tag-readiness audit that
produced `36eb50da`, and this session independently re-confirmed it directly
against current source — `episode/episode2.py:108`
(`self.routes.lookup(semantic_class_id, fresh_candidate)`, a real
`KnownRouteRegistry.lookup()` call classifying KNOWN) and `episode2.py:131`
(`artifact.evaluate(probe_input)`, real positive execution via
`ConsequenceBoundary`). Recorded here so the agent's `STILL_MISSING` report does
not stand uncorrected.

### `act`/`kind` validation ("validate ALIVE using act and kind")

Per instruction: use each tool "where it genuinely applies," report honestly if
either doesn't, rather than forcing a use for it.

**`kind`** (Kubernetes-in-Docker) — **does not apply**. `grep -rn
"kubernetes|k8s|kind_cluster|KindCluster" src/autofde_lab/sa2a/ tests/sa2a/`: every
match is the generic `EnvelopeKind`/`NodeKind`/`ValidatorKind`/`kh:kind`
discriminator-field naming convention, zero Kubernetes usage. `kind` is real and
used elsewhere in this repo's own CI (`.github/workflows/sregym-kind-live.yml`,
confirmed: downloads its own `kind` binary and drives a disposable cluster via
`kind/setup_kind_cluster.sh`), but exclusively for the unrelated SREGym gym
subsystem — nothing built in this pass, or anywhere in `sa2a/`, has a k8s
dependency. Also checked and ruled out: `.github/workflows/
life-autonomic-case-study.yml`'s job is literally named "Exact-head Chicago case
study" (`act -l | grep -i chicago` surfaces it) — read directly, it is scoped to
`src/autofde_lab/agent/life_autonomic_case_study.py` and gymact/wasm4pm-compat SHA
pins, using "Chicago" as this repo's generic testing-style term, not a reference to
v26.9.17 sa2a.

**`act`** (local GitHub Actions runner) — genuinely applicable, and run. No
existing CI job is narrowly scoped to `tests/sa2a/` alone: `.github/workflows/
ci.yml`'s only job that ever reaches `tests/sa2a/` is `integration`, via a broad
final catch-all step preceded, under `set -euo pipefail`, by `pytest -vv
tests/solvers/python` — the already-documented-broken ray/GNN suite — so running
that job through `act` would reproduce a known, unrelated, pre-existing failure
before ever reaching sa2a, not provide new signal. Instead, a scratch,
never-committed workflow (`act-sa2a-validate.yml`, kept only in the session
scratchpad) was authored: real `actions/checkout` + `actions/setup-python@5` +
sa2a's actual runtime deps (`pydantic`, `typer`, `rdflib`, `pytest`, no heavy
`--extra=all` matrix) + `pytest tests/sa2a/ -q`, run via `act workflow_dispatch -W
<scratch-path> -P ubuntu-latest=catthehacker/ubuntu:act-latest` against the
`colima` Docker context (confirmed live, native `linux/aarch64` — this machine's
own architecture, so no `--container-architecture linux/amd64` emulation was
needed, unlike `~/ash_a2a`'s documented Elixir/OTP-specific arm64 limitation,
which does not apply to this pure-Python package).

**Result: `BLOCKED:ACT_CONTAINER_START_HANG`, real and reproduced, not
forced/faked around.** The run hung indefinitely at `🚀 Start image=...` —
before container creation, before the pytest step ever ran — with zero further
log output. Diagnosed rather than assumed: `docker images` confirmed
`catthehacker/ubuntu:act-latest` was already fully cached (1.72GB, pulled
weeks earlier), ruling out an image-pull stall; a direct `docker pull` of the
same tag resolved instantly (registry reachable, not a network problem); a
direct `timeout 30 docker run --rm catthehacker/ubuntu:act-latest echo ...`
against the same `colima` daemon **started and exited correctly in under a
second** — ruling out Docker/colima/the image itself as the cause. The hang is
specific to `act`'s own container-creation orchestration (which does more
than a plain `docker run` — network setup, workflow/action cache bind-mounts,
capability probing) against this machine's colima + Apple Virtualization
Framework + virtiofs backend. Reproduced 3 times with different mitigations,
each timed out at 180s with the identical `context canceled` /
`Start image=...`-then-silence signature: (1) default flags: hung 15+ minutes
before being killed; (2) `--pull=false` (image already local): still hung;
(3) `--container-architecture linux/amd64` (ash_a2a's own documented
workaround) + `--pull=false`: still hung. This is a real, disclosed local
`act` limitation on this machine — in the same class as `~/ash_a2a`'s own
documented local-`act` friction (real friction exists on this machine class
using `act`), though the specific mechanism differs (ash_a2a: an in-container
Elixir/OTP toolchain failure after the container starts; here: `act` itself
never gets the container started at all). Per `~/ash_a2a`'s own script
comment, the correct fallback is the same one that repo already names: treat
a real hosted GitHub Actions run on the same SHA as the authoritative
local-parity signal, not a forced local workaround. No hosted run was
triggered here — triggering CI is a `git push`-adjacent actuation gated by
`.claude/rules/actuation-boundary.md`, and this pass did not push.

### Verification

`tests/sa2a/ tests/agent/` → 578 passed, 0 failed. Mock-grep clean. `py_compile`
clean on all touched/created files.

## See also

- `docs/STATUS.md` — pass entry for this ticket.
- `docs/jira/v26.9.16/AFDE-2604-admission-fencing-local-closure.md` — the admission/
  authority/BRCE hardening this ticket's `Episode1Runner`/`Episode2Runner` build on
  top of, unmodified.
- `.claude/rules/standing-law.md`, `absence-is-not-evidence.md`,
  `no-dual-bookkeeping.md`, `level4-completion-law.md` — the evidence discipline this
  ticket's §3/§6/§7 follow.
