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

- **`ExactSubject`/`SubjectResolver`/composition digest** (PRD §6.1-6.2, ARD §5.1,
  §6-7) — no multi-repo/artifact composition identity fence exists. `crown` in this
  pass runs a hardcoded, honestly-scoped single-class demonstration, not an arbitrary
  composition.
- **`DiscoveryRouter`/Formal Machinery Router** (PRD §6.6, ARD §14-15) — `Episode1Runner`
  takes a caller-supplied `discover` callable; it does not itself select among formal
  search/local model/frontier model/DSPy/TPOT2/RL/GymAct.
- **`CompositionCourt`/transport-failure taxonomy/cross-repo standing** (ARD §42-44) —
  zero executable machinery; unrelated to this pass.
- **`ash_a2a` Integration Boundary** (ARD §27) — no real dispatch adapter into that
  runtime exists.
- **Consolidating the 3 duplicate Chicago-gate implementations** (ARD §50) — this pass
  reuses one of them (`consequence_court.py`'s real disk actuator/verifier/store) but
  does not collapse `ChicagoCrownQualificationRunner` /
  `scripts/verify_v26_9_16_chicago.py` / the courts' own inline gate logic into one.
- **Release-level state machine** (PRD §12: `CREATED -> SUBJECT_FENCED -> ... ->
  CROWNED`) — `Episode`/`MachineExperience` each carry their own lifecycle; no
  release-scoped wrapper state machine was built.
- **Additional `Receipt` subtypes** (`AllocationReceipt`, `ManufacturingReceipt`,
  `QualificationReceipt`, `CompositionReceipt`, `VerificationReceipt` — ARD §30) — this
  pass's `qualification_receipt`/`receipt_id` fields are plain strings, not distinct
  typed receipt classes.
- **Mutation-vacuousness tooling** for the falsifier corpus (PRD §6.25's own meta-check)
  — not built.
- **A general-purpose `DiscoveryRouter`-selectable CLI** for arbitrary semantic classes
  — `episode1`/`crown` CLI commands are scoped to the one demonstrated class
  (`requires-port`), documented as such in their own docstrings/scope_note field.

## See also

- `docs/STATUS.md` — pass entry for this ticket.
- `docs/jira/v26.9.16/AFDE-2604-admission-fencing-local-closure.md` — the admission/
  authority/BRCE hardening this ticket's `Episode1Runner`/`Episode2Runner` build on
  top of, unmodified.
- `.claude/rules/standing-law.md`, `absence-is-not-evidence.md`,
  `no-dual-bookkeeping.md`, `level4-completion-law.md` — the evidence discipline this
  ticket's §3/§6/§7 follow.
