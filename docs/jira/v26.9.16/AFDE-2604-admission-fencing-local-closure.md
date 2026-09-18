# AFDE-2604: local admission fencing — wire `AdmissionPipeline` as the mandatory predecessor of the local Authority/BRCE DO path

- **Status (2026-09-17, fail-secure closure pass — the breaking default-flip
  previously named as undecided is now DECIDED and EXECUTED). Corrected count,
  per an external review that caught this session's own bookkeeping error:
  the 2026-09-16 adversarial round found 9 distinct named findings, not 7
  (Lens 2: DW-1, DW-2 — 2; Lens 3: UE-2, UE-3 — 2; Lens 4: R1, R2, R3 — 3;
  Lens 5: item (1) admission-identity evidence, item (2) parameters not
  bound — 2; total 2+2+3+2=9). This session's own earlier "2 of 7" / "4 of 7"
  phrasing (below) incorrectly folded Lens 5's two findings into "the 7"
  Lens 2-4 findings actually name. Real, corrected tally across both closure
  passes this session: 4 of 9 CLOSED — DW-2 and Lens 5 item (1) (prior pass,
  below), DW-1 and UE-2 (this pass). 5 of 9 remain OPEN: UE-3, R1, R2, R3
  (Lens 4, deliberately unaffected — see below), and Lens 5 item (2). Per
  this repo's own docs/CLAUDE.md invariant ("retracted claim gets a
  retraction note in place, with the corrected finding beside it"), the
  original "7"-based phrasing below is left exactly as written, not edited
  away — this note is the correction, not a silent fix.** `ConsequenceBoundary.__init__`'s
  `require_admission` class-level default flipped from `False` to `True`;
  `ReactiveSemanticLoop.__init__`'s `admission_pipeline`, when the parameter is
  OMITTED (not explicitly passed, including as `None`), now constructs a real
  `AdmissionPipeline()` instead of defaulting to `None` (a `_NotSet` sentinel
  distinguishes "omitted" from an explicit, affirmative `admission_pipeline=None`
  opt-out). This is the real, wide-blast-radius breaking change every earlier
  entry in this ticket correctly declined to make silently.
  - **Real blast radius, measured before deciding, not guessed**: flipping the
    default broke 44 previously-passing tests across 19 files (confirmed via a
    real, full `tests/sa2a/ tests/agent/` run before any fix was attempted).
    Every one of the 44 was triaged with real understanding of what it actually
    tests (never a mechanical "make it pass") via 19 parallel agents plus 2
    direct follow-up fixes for shared infrastructure and one file the agents
    correctly reported BLOCKED rather than silently working around:
    - **DW-1 CLOSED**: `test_mutation_dw1_direct_library_construction_bypasses_
      admission_entirely` — the exact gap this default flip exists to close —
      updated fix-forward from `SURVIVED` (asserting `EXECUTED`) to `DEFEATED`
      (asserting `REFUSED`/`REFUSED_ADMISSION_CONTENT_NOT_BOUND`), matching the
      DW-2 pattern already established in the prior pass.
    - **UE-2 CLOSED**: `ReactiveSemanticLoop.admission_pipeline` and
      `ConsequenceBoundary.require_admission` are no longer two
      independently-configured knobs that could silently drift apart — both
      now default to the secure shape, and `loop.consequence_boundary.execute()`
      called directly now hits the same gate a gated `run_reflex_cycle()` call
      would.
    - **~40 tests where admission was genuinely incidental** (replay,
      tamper-detection, authority, receipts, hooks, construction binding,
      token-mismatch, cross-actor identity, etc.) — each fixed by wiring a
      real, valid `Standing.ADMITTED` `AdmissionResult` (via a real
      `AdmissionPipeline().admit()` call with the exact
      `<action_iri> afl:targetResource <target_resource> .` binding triple and
      a real provenance record) into the `ExecutionEnvelope`/
      `ReactiveSemanticLoop` construction the test already used, so each test
      reaches the exact same code path it always tested. `require_admission=
      False` was used only where wiring real admission was genuinely
      disproportionate to a test's own orthogonal purpose (named at each such
      site, never silent).
    - **Lens 4's R1/R2/R3 (TOCTOU/concurrency) deliberately left SURVIVED,
      verified not accidentally masked**: `test_afde_2604_toctou_residual_
      qualification.py`'s 3 tests wire real admission so they still reach the
      real receipt-store/grant-revocation race they document, then confirm the
      original findings still reproduce — admission and concurrency-safety are
      orthogonal axes, and this default flip does not, and was never claimed
      to, close them. All 3 still assert `SURVIVED` with the identical real
      counterexamples as before.
    - **Shared infrastructure fix (this pass, direct — not a per-file agent's
      scope)**: `src/autofde_lab/sa2a/conformance/courts/consequence_court.py`
      (`ConsequenceCourt`, the older RFC-SA2A-001 court predating and
      orthogonal to admission fencing) constructs its own internal
      `ConsequenceBoundary`/`ExecutionEnvelope` instances with no visibility
      point for a test file to inject admission through. One assigned agent
      (`test_court_consequence.py`) correctly identified this, correctly
      declined to hack around it from the test file, and reported `all_passed:
      false` with a precise, evidence-based explanation instead of forcing
      green — exactly the discipline this repo requires. Fixed directly:
      `require_admission=False` added explicitly to all 7 real
      `ConsequenceBoundary(...)` constructions inside `ConsequenceCourt`
      (the deliberate actuator-is-verifier collusion-check construction, which
      raises before `require_admission` would ever matter, was left alone),
      with one additional, related fix found while reading this file:
      `DurableDiskReceiptStore._sync_from_disk()` reconstructed `PreparedReceipt`
      from disk JSON without reading back the new `admission_digest` field
      (added in the prior pass), which would have silently produced a
      digest-mismatched reload for any real admitted receipt — a real,
      necessary follow-up to that prior fix, not a new problem this pass
      introduced. One test-file-level fix beyond the shared infrastructure:
      `test_strict_prepared_receipt_commitment_before_actuation`'s own
      falsification-check `ConsequenceBoundary` (a receipt-store-commit-failure
      probe, unrelated to admission) needed `require_admission=False` too.
  - **Final, real regression, this pass**: `.venv/bin/python -m pytest
    tests/sa2a/ tests/agent/` → **425 passed**, 0 failed. `tests/fabric/
    test_coverage.py tests/planning/` → 41 passed, 2 skipped (environment-gated,
    unrelated). `grep -rn "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch"`
    over every one of the 21 files this pass touched → only docstring/comment
    mentions naming the discipline (including, in one file, the literal grep
    command embedded in its own verification instructions), zero actual usage.
  - **Overall ticket standing, restated**: `PARTIAL_ALIVE` still — UE-3 (`
    ConsequenceBoundary._require_admission` is a plain mutable attribute with no
    write guard, tamperable at runtime — inherent to Python attribute access,
    not something `__slots__`/property machinery meaningfully closes without
    disproportionate complexity for the demonstrated risk) and Lens 5 item (2)
    (admission never binds `ExecutionEnvelope.parameters`) remain open,
    unattempted, named here rather than silently implied closed. R1/R2/R3 are
    explicitly NOT closed by this pass and were never claimed to be — they are
    a different, still-real, still-open finding about receipt-store
    concurrency-safety.

- **Status (2026-09-17, closure pass — 2 of the 7 named-open gaps below closed for
  real, remainder explicitly left open, no breaking default-flip attempted)**: this
  pass closed **DW-2** (Lens 2) and **Lens 5 item (1)**, both real, narrow,
  non-breaking bug fixes verified with real pytest runs. It explicitly did **NOT**
  attempt **DW-1**, **UE-2/UE-3** (Lens 3), **Lens 4**'s R1/R2/R3, or **Lens 5 item
  (2)** — all of those require either flipping `ConsequenceBoundary`'s/
  `ReactiveSemanticLoop`'s own class-level default to secure-by-default (a real,
  wide-blast-radius breaking change affecting every existing library-level call
  site, not something to do silently without an explicit decision to make it) or
  adding real concurrency-control machinery (`ReceiptStore` has no locking of any
  kind today) disproportionate to this repo's demonstrated single-process,
  synchronous usage pattern. Named here rather than silently left implying "closed":
  - **DW-2 CLOSED**: `sa2a/cli.py`'s `hook_reflex` now resolves
    `skip_admission_check` defensively — a non-`bool` value (Click's own
    unsubstituted `OptionInfo` sentinel, reachable only when the function is called
    directly, never through real CLI dispatch) resolves to the sentinel's own
    configured default (`False`) instead of being trusted as truthy. Verified:
    `test_mutation_dw2_calling_real_hook_reflex_function_directly_defaults_to_skip`
    (updated, fix-forward, to assert the corrected `REFUSED` outcome instead of the
    formerly-documented `EXECUTED` survival) now passes.
  - **Lens 5 item (1) CLOSED**: `PreparedReceipt` gains a new `admission_digest`
    field (default `"none"`, additive), bound to the exact
    `AdmissionResult.digest` that gated the actuation via
    `_enforce_admission_gate()`/`execute_admitted()`, wherever an admission was
    presented. `brce/replay.py`'s independent digest-verification recomputation
    (the one that reads durable JSON with zero in-process trust, per
    `no-dual-bookkeeping.md`'s crown threshold) was updated to include the new
    field in its own recomputed body, or every real receipt would have started
    failing replay verification the moment the digest formula changed — caught by
    running the full regression suite before considering this closed, not assumed
    safe from the additive field alone. Named honestly, narrower than a hypothetical
    full fix: only `AdmissionResult.digest` is bound, not
    `admission.receipt.receipt_id` (a separate, narrower internal label) — and
    `FinalReceipt` still carries no admission identity of its own (a reader joins
    via `idempotency_token` to the `PreparedReceipt`, the same join
    `receipts.py`'s own `_validate_final_grant_id` already performs internally).
    Verified: `test_fresh_lens_1_receipt_carries_no_admission_identity_edge`
    (updated, fix-forward, to assert the closed shape) now passes; Lens 5 item (2)
    (admission never binds `parameters`) is untouched and remains open.
  - **Local execution, this pass**: `.venv/bin/python -m pytest tests/sa2a/ -v` →
    **332 passed**, 0 failed, 0 errors. `grep -rn
    "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" src/autofde_lab/sa2a/brce/
    tests/sa2a/conformance/test_afde_2604_fresh_lens_admission_gaps.py
    tests/sa2a/conformance/test_afde_2604_default_wiring_bypass_qualification.py
    src/autofde_lab/sa2a/cli.py` → only docstring mentions naming the discipline,
    zero actual usage.
  - **Overall ticket standing, restated**: still `PARTIAL_ALIVE`. Two real, narrow
    gaps closed this pass; DW-1, UE-2, UE-3, R1, R2, R3, and Lens 5 item (2) remain
    open, exactly as the 2026-09-16 status below already named them — this pass
    does not upgrade the ticket to `ALIVE`, and the breaking-default-flip question
    (the one change that would close DW-1/UE-2/UE-3/R1 at once) remains an explicit,
    undecided architecture choice, not silently deferred.

- **Status (2026-09-16, this session — 5-lens adversarial qualification round on top of
  the architecture fix)**: the architecture fix described below (relational binding via
  `_admission_covers_action_target()`, unified enforcement via `require_admission`/
  `_enforce_admission_gate()`, secure-by-default CLI wiring in `sa2a/cli.py`'s
  `hook reflex`, and receipt-store TOCTOU/grant-validation defense-in-depth in
  `receipts.py`) genuinely holds against 2 of 5 fresh, independent adversarial lenses run
  this round, and does **NOT** hold against the other 3 — real, currently-live gaps were
  found and are named precisely below, not silently absorbed into a green summary. This
  is a `PARTIAL_ALIVE` status, stated plainly, not a closed one.
  - **Lens 1 (relational-binding bypass)** — HOLDS. 3 fresh mutations (blank-node
    indirection, RDF reification, `owl:sameAs`-bridged cross-pairing) all attempted
    against `_admission_covers_action_target()`; **3/3 defeated**, zero survivors.
  - **Lens 2 (default-wiring / opt-out abuse)** — DOES NOT FULLY HOLD. 2 fresh mutations
    attempted; **0/2 defeated, both survived**: (DW-1) constructing
    `ConsequenceBoundary`/`ReactiveSemanticLoop` directly with bare library defaults
    (bypassing `sa2a/cli.py` entirely) reaches real, unfenced actuation — a previously
    disclosed, still-real gap; (DW-2, newly found this round) calling the real
    `hook_reflex` Typer command function directly as a plain Python function (bypassing
    Click's CLI dispatch) binds `skip_admission_check` to a truthy `typer.models
    .OptionInfo` sentinel instead of literal `False`, silently reproducing the fully
    permissive `--skip-admission-check` configuration with **no flag, no argument, and
    no caller intent to skip anything** — "secure by default" holds only for a real CLI
    invocation (subprocess or `CliRunner`), not for the identical production function
    called in-process.
  - **Lens 3 (unified-enforcement bypass)** — PARTIAL_ALIVE. The narrow claim (`execute()`
    and `execute_admitted()` behave identically on ONE `ConsequenceBoundary` instance
    when `require_admission=True`) holds (1/1 mutation defeated). Two further mutations
    on adjacent surfaces **survived**: (UE-2) `ReactiveSemanticLoop.admission_pipeline`
    and `ConsequenceBoundary.require_admission` are independently configured with no
    invariant tying them together, and `loop.consequence_boundary` is a plain public
    attribute — calling it directly (`.execute()`) reaches real actuation for content an
    admission-configured loop's own gated dispatch just refused; (UE-3, lower severity)
    `ConsequenceBoundary._require_admission` is a plain mutable attribute with no write
    guard — tamperable at runtime to silently disable the fence on `execute()` while
    `execute_admitted()` on the same instance keeps enforcing it.
  - **Lens 4 (receipt-store TOCTOU residual)** — DOES NOT HOLD. 3 fresh mutations
    attempted; **0/3 defeated, all 3 survived**: (R1) the receipts.py `save_final`
    grant-revalidation fix is a structural no-op for the only real production entry
    point in this repo (`sa2a/cli.py:445` constructs `ConsequenceBoundary` without
    `receipt_store=`, so its default broker-less `ReceiptStore()` never gets the
    `authority_broker` the fix depends on); (R2) even when a caller deliberately wires
    `ReceiptStore(authority_broker=...)`, a mid-actuation grant revocation makes
    `ReceiptGrantValidationError` propagate UNCAUGHT out of `execute()` (no
    try/except around `boundary.py`'s Step 7 `save_final()` call), leaving the real
    actuation with **zero** terminal receipt at all — worse than the original gap,
    since Zero Unreceipted Actuation is now violated by the fix's own refusal path;
    (R3) two genuinely concurrent `execute()` calls on the same idempotency token (real
    `threading.Thread`/`Event`, no locking anywhere in `ReceiptStore`) can leave a
    receipt that says REFUSED for an actuation that genuinely happened, or raise a bare
    uncaught `ValueError` ("Idempotency token conflict").
  - **Lens 5 (fresh-eyes, no prior constraint)** — DOES NOT HOLD for 2 newly-found gaps,
    neither previously named anywhere in this ticket or in any existing conformance
    test: (1) the durable `PreparedReceipt`/`FinalReceipt` carries no identity edge
    (digest or receipt_id) back to the `AdmissionResult` that gated it — per this repo's
    own `no-dual-bookkeeping.md` crown threshold, standing here is not recomputable from
    durable artifacts alone, only from live in-process enforcement; (2)
    `_admission_covers_action_target()` binds only `(action_iri, target_resource)` —
    it never inspects `ExecutionEnvelope.parameters` — so one admission, reused across
    every intent in a `ReactiveSemanticLoop` reflex cycle, authorizes structurally
    different actuation payloads (confirmed via a benign vs. a 999,999,999-amount
    transfer to a different destination, both reaching real DO) under the identical
    action/target admission.
  - **Independent verification (skepticR) + regression**: both prior self-reports
    (architecture fix, receipt-store defense-in-depth) were independently spot-checked
    this round with 8 real re-run commands, zero discrepancies found. Full `tests/sa2a/`
    regression, re-run again this session: `328 passed`, 0 failed, 0 errors (verbatim
    output below, under "Local execution, this session"). The 6 tests that were failing
    in the prior round's snapshot (`test_afde_2604_cross_entry_point_confused_deputy.py`
    ×2, `test_afde_2604_identity_binding_bypass_qualification.py` ×2,
    `test_afde_2604_replay_idempotency_fresh_mutations.py` ×2) now all pass; collected
    count rose 314→328 from other untracked test files added in this shared working
    tree, not from any change made this pass.
  - No source file was modified this round (only the five lens sessions' new,
    additive test files under `tests/sa2a/conformance/` were added, per their own
    task scope; this header-rewrite pass touched only this ticket document). No
    `git commit`/`git push` was run. Local file edits and local test runs only.
- **Severity**: High (local scope only — see Owning repo(s) and Standing)
- **Standing**: no single value — split per claim in "Local standing, scoped" below,
  and now further split by this round's 5-lens qualification above. Headline
  (superseded twice, kept for history): the required *fence* was originally
  `NOT_FOUND`; after the first architecture-fix pass every named gap was closed for
  the scope that pass tested. This round's 5-lens adversarial re-qualification found
  that the fence design is **real but incomplete**: it defeats every content-level
  relational-binding attack tried (Lens 1, 3/3), and the single-instance
  `execute()`/`execute_admitted()` unification holds narrowly (Lens 3's own mutation,
  1/1) — but bypasses remain at three different altitudes: (a) construction-level
  (bare library defaults, and a Typer command's own Python-level default sentinel,
  both reachable without going through `sa2a/cli.py`'s hardened Click dispatch —
  Lens 2), (b) composition-level (the loop and the boundary each independently
  configurable, with no invariant binding them, plus a tamperable private flag —
  Lens 3's UE-2/UE-3), (c) store/concurrency-level (the receipt-store fix protects
  nothing on the real production path, and has no locking — Lens 4), and (d)
  content-precision-level (admission binds the action/target pair, never the
  actuation parameters, and leaves no durable identity edge back to itself — Lens 5).
  Overall: `PARTIAL_ALIVE`, precisely — not `ALIVE`, and not `BLOCKED` (nothing here
  prevents further work; the gaps are named, reproducible, real).
- **Local execution, this session** (header-rewrite pass, real command run to confirm
  the regression claim above before writing it):
  ```
  $ cd /Users/sac/autofde-lab && pwd
  /Users/sac/autofde-lab
  $ .venv/bin/python -m pytest tests/sa2a/ --basetemp=/tmp/afl_header_rewrite_verify3
  ........................................................................ [ 21%]
  ........................................................................ [ 43%]
  ........................................................................ [ 65%]
  ........................................................................ [ 87%]
  ........................................                                 [100%]
  328 passed in 12.56s
  ```
  (exit code `0`, confirmed separately). Every `test_afde_2604_*` file the 5 lenses
  above cite was confirmed present on disk this session (`ls -la
  tests/sa2a/conformance/test_afde_2604_{relational_binding_bypass_fresh_mutations,
  default_wiring_bypass_qualification,unified_enforcement_lens_mutations,
  toctou_residual_qualification,fresh_lens_admission_gaps}.py`, all present, mtimes
  19:48-19:51 today). `src/autofde_lab/sa2a/brce/boundary.py`,
  `src/autofde_lab/sa2a/hooks/reactive_loop.py`, `src/autofde_lab/sa2a/cli.py`, and
  `src/autofde_lab/sa2a/brce/receipts.py` were re-read in full this session and each
  cited finding above (Lens 1's exact-triple check at `boundary.py:98-137`, Lens 2's
  `skip_admission_check: bool = typer.Option(False, ...)` at `cli.py:358-371` and the
  boundary/loop construction at `cli.py:445-463`, Lens 3's plain `self
  ._require_admission` at `boundary.py:274`/`281-282` and `ReactiveSemanticLoop`'s
  independent `admission_pipeline` field with no coupling to `consequence_boundary`
  at `reactive_loop.py:80-93`, Lens 4's broker-less default `ReceiptStore()` at
  `boundary.py:270` and the unguarded `self._receipt_store.save_final(final_receipt)`
  at `boundary.py:703`, and receipts.py's real `_validate_final_grant_id` wiring at
  `receipts.py:341-450`) was independently confirmed against the real, current source
  by direct reading, not merely restated from the lens reports. This pass did not
  modify any file under `src/autofde_lab/sa2a/`; only this ticket document was
  edited. No `git commit`/`git push` was run.
- **Owning repo(s)**: `seanchatmangpt/autofde-lab` only, scoped entirely to
  `src/autofde_lab/sa2a/**` — the in-repo RFC-SA2A-001/002 conformance testbed
  (Knowledge Hooks, Authority Broker, BRCE Consequence Boundary, Admission Pipeline,
  and the `tests/sa2a/conformance/` courts that falsify them). Per
  `.claude/rules/ecosystem-boundary.md` this repo "computes candidate plans... A
  planner selects; the broker authorizes; the executor performs; the verifier
  evaluates" — that framing is about the domain/solver decision engine
  (`fabric/`, `openclaw_*.py`), a *different* subsystem from `sa2a/`. The `sa2a/`
  courts are a real, self-contained local implementation of admission/authority/BRCE
  used as a conformance testbed for RFC-SA2A-001/002 — they are **not** the
  ecosystem admission/broker `mfw` owns, and nothing in this ticket claims
  cross-repo closure. `src/autofde_lab/CLAUDE.md`'s "No admission, no broker, no
  actuation... `mfw` owns those" is written about the fabric/domain/solver surface
  and does not describe `sa2a/`, which genuinely implements a local admission
  pipeline, a local authority broker, and a local (real-disk) actuation boundary as
  its own RFC-conformance subject matter.
- **Depends on** (all real, in this repo, all read in full this session):
  - `AdmissionPipeline` — `src/autofde_lab/sa2a/admission/pipeline.py`
  - `AuthorityBroker` / `AuthorityGrant` / `ConsequenceRequest` — `src/autofde_lab/sa2a/authority/broker.py`
  - `ConsequenceBoundary` / `ExecutionEnvelope` — `src/autofde_lab/sa2a/brce/boundary.py`
  - `KnowledgeHookEngine` — `src/autofde_lab/sa2a/hooks/engine.py`
  - `ReactiveSemanticLoop` — `src/autofde_lab/sa2a/hooks/reactive_loop.py`
  - `UnknownResolutionPipeline` / `admit` CLI command — `src/autofde_lab/sa2a/cli.py:86-120`

This is the autofde-lab-local equivalent of the real upstream ticket
`seanchatmangpt/ash_a2a` A2A-2604 ("wire semantic admission into the live
consequence path"), read in full this session from
`/private/tmp/claude-501/-Users-sac-autofde-lab/805b2d1b-7d56-456a-b169-7ab879cabf6b/scratchpad/ash_a2a_tickets/A2A-2604-wire-semantic-admission-to-live-do-path.md`.
No text below is copied from that document — every claim here is established by
grep/Read/pytest run against this repo's own source this session, per the task's
own instruction.

## Problem

A2A-2604's target law, restated in ash_a2a's own vocabulary, is:

```
candidate semantic state -> ADMIT -> SELECT -> CONSTRUCT -> authority grant -> CommandBus/DO
```

never

```
candidate -> authority -> DO
```

This repo's `sa2a/` subtree contains a real, independently-working local analog of
every element on the left side of that law:

- `AdmissionPipeline.admit()` (`admission/pipeline.py:182-361`) — a genuine 10-stage
  fail-closed pipeline (parse -> identity policy -> ShEx -> SHACL -> Datalog closure
  -> N3 derivation -> SPARQL falsifiers -> provenance -> meta-admission -> ADMITTED),
  returning `AdmissionResult(standing: Standing.ADMITTED | Standing.REFUSED, ...)`.
- `AuthorityBroker.evaluate()` (`authority/broker.py:109-309`) — a genuine
  non-implication-enforcing broker (`REFUSED_AGENT_IS_NOT_AUTHORITY`,
  `REFUSED_CAPABILITY_IS_NOT_AUTHORITY`, `REFUSED_PLAN_IS_NOT_AUTHORITY`,
  `REFUSED_PROOF_IS_NOT_AUTHORITY`) plus real ODRL policy/grant matching.
- `ConsequenceBoundary.execute()` (`brce/boundary.py:154-322`) — a genuine BRCE
  pipeline enforcing Zero Unreceipted Actuation, with a real
  `ConsequenceActuator`/`ConsequenceVerifier` protocol and a real `ReceiptStore`.

**Grep evidence that these are never composed** (run this session, from
`/Users/sac/autofde-lab`, zero results in both directions):

```
$ grep -rln "AdmissionPipeline\|AdmissionResult" src/autofde_lab/sa2a/
src/autofde_lab/sa2a/admission/__init__.py
src/autofde_lab/sa2a/admission/pipeline.py
src/autofde_lab/sa2a/conformance/benchmarks/harness.py
src/autofde_lab/sa2a/conformance/courts/admission_court.py

$ grep -rn "AdmissionResult\|AdmissionPipeline\|admission" \
    src/autofde_lab/sa2a/hooks/*.py src/autofde_lab/sa2a/brce/boundary.py \
    src/autofde_lab/sa2a/authority/broker.py
src/autofde_lab/sa2a/hooks/engine.py:14:from autofde_lab.sa2a.admission.graphlaw_bridge import GraphLawBridge
```

The only "admission" reference anywhere in the hooks/authority/BRCE code is
`hooks/engine.py`'s import of `GraphLawBridge` — a real WASM Turtle/SHACL hook
*evaluator* (`admission/graphlaw_bridge.py:171-191`, real Node.js subprocess), not
the `AdmissionPipeline` fail-closed fence. `AdmissionPipeline`/`AdmissionResult`
never appear in `boundary.py`, `broker.py`, `reactive_loop.py`, or anywhere reached
from `sa2a/cli.py`'s `hook reflex` command (`cli.py:350-452`, which imports
`AuthorityBroker` and `ConsequenceBoundary` directly and never imports
`admission.pipeline` at all).

Reading `hooks/reactive_loop.py`'s `ReactiveSemanticLoop.run_reflex_cycle`
(`reactive_loop.py:74-160`) confirms the live composed path is exactly:

```
hook_engine.evaluate()  (line 94)
  -> authority_broker.evaluate()  (line 114)
    -> consequence_boundary.execute()  (line 126)
```

i.e. literally `candidate -> authority -> DO`, the exact anti-pattern A2A-2604 names.
Separately, `sa2a/cli.py`'s `admit` command (`cli.py:86-120`) does route a candidate
through admission-shaped machinery — but through `UnknownResolutionPipeline`
(`unknown/resolution.py`), a *different* pipeline than `AdmissionPipeline`, and its
output (`AdmissionReceipt` in `unknown/resolution.py`, a distinct dataclass sharing
only a name with `admission/pipeline.py`'s `AdmissionReceipt`) is never passed to
`AuthorityBroker` or `ConsequenceBoundary` either. There are, today, two
independent CLI commands (`admit`, `hook reflex`) and zero code path connecting
either candidate-admission surface to the real authority/BRCE surface.

**Real, this-session repro** confirming the gap is exploitable, not merely a static
absence. Script:
`/private/tmp/claude-501/-Users-sac-autofde-lab/805b2d1b-7d56-456a-b169-7ab879cabf6b/scratchpad/afde2604_repro.py`
— real collaborators only (real `AuthorityBroker`+`AuthorityGrant`, real
`KnowledgeHookEngine` driving the real Node.js WASM `GraphLawBridge`, real
`ConsequenceBoundary` with a real actuator/verifier, real `AdmissionPipeline` run
separately on the identical candidate). Command and full real output:

```
$ .venv/bin/python /private/tmp/.../scratchpad/afde2604_repro.py
=== ReactiveSemanticLoop result (real DO path) ===
steps: 1
  triggered_hooks: ('afde2604_repro_hook',)
  intents_synthesized: ['intent-7ebbcde9c412']
  authority_decisions: [(True, 'grant-afde2604-repro')]
  final_receipt.state: EXECUTED postcondition_verified: True
REACHED_REAL_DO (EXECUTED receipt) despite garbage/never-admitted event_ttl: True

=== AdmissionPipeline result on the SAME candidate content (never actually consulted above) ===
standing: REFUSED
refusal_code: REFUSED_PARSE_FAILURE
reasons: ('Graph parsing failed: at line 1 of <>:\nBad syntax (expected directive or
statement) at ^ in:\n"b\'\'^b\'the sky is blue and this sentence is not RDF in any
serializ\'..."',)
ADMISSION_WOULD_HAVE_REFUSED_THIS_EXACT_CANDIDATE: True

=== VERDICT ===
GAP_CONFIRMED (reached real DO with a candidate the real admission pipeline refuses): True
```

The candidate content (`"the sky is blue and this sentence is not RDF in any
serialization"`) is not valid Turtle/RDF at all. Presented directly to the real
`ReactiveSemanticLoop`, it produces a fired hook, a synthesized intent, a real
`authorized=True` decision from the real `AuthorityBroker` (because a grant was
registered for that actor/action/target — the broker did its job correctly given
what it was asked), and a real `EXECUTED` `FinalReceipt` from the real
`ConsequenceBoundary` (real actuation happened — `RealBoolActuator.actuate()` ran).
Presented to the real `AdmissionPipeline.admit()` on the exact same string, Stage 1
(Parse Candidate) refuses it with `REFUSED_PARSE_FAILURE`. Nothing in the executed
path ever asked the admission pipeline. This is `candidate -> authority -> DO`,
demonstrated with a real receipt on disk-adjacent state, not inferred from reading
code.

## Required change

Local restatement of A2A-2604's required invariants, in this repo's own
`sa2a/` vocabulary:

1. `ConsequenceBoundary.execute()` and `ReactiveSemanticLoop.run_reflex_cycle()`
   must refuse to reach `AuthorityBroker.evaluate()` for any `ExecutionEnvelope`
   whose originating candidate content has not first produced
   `AdmissionResult.standing == Standing.ADMITTED` from a real
   `AdmissionPipeline.admit()` call.
2. `AdmissionResult`/`AdmissionReceipt` must continue to carry no authority field
   (true today — see Laws #2 below) — admission staying authority-inert is a
   property to preserve, not to add.
3. An `AuthorityGrant`/`AuthorityDecision` must never be treated as sufficient on
   its own to reach `ConsequenceBoundary.execute()`; a bound, exact-identity
   `AdmissionResult` must also be present for the same candidate content.
4. A valid `AuthorityGrant` must not be usable to repair or bypass a `REFUSED`
   admission outcome for the same candidate — i.e. the fix must not simply move the
   admission check to a point the authority grant can route around.
5. The binding between the admitted candidate and the authorized action must be an
   explicit typed edge (candidate digest -> intent -> authority decision -> receipt),
   per `.claude/rules/no-dual-bookkeeping.md` — not inferred from call order alone,
   which is exactly the class of defect the two already-pinned mutation tests
   (see below) demonstrate for the *authority/receipt* edge already.

## Laws — remote vs. local instantiation, named explicitly

| A2A-2604 law | Local instantiation | Status |
|---|---|---|
| 1. `standing != :admitted` implies no `:change`/`:external_do` dispatch | Real local primitive exists (`Standing.ADMITTED`, `ConsequenceBoundary.execute`) but is never composed — no code path checks `AdmissionResult.standing` before dispatch. Demonstrated bypassed by the repro above. | `NOT_FOUND` (as enforced behavior); the primitive itself is `ALIVE` in isolation |
| 2. semantic admission always leaves `authority: :none` | Holds *vacuously* — `AdmissionResult`/`AdmissionReceipt` (`admission/pipeline.py:46-96`) carry no authority-shaped field at all, so admission structurally cannot mint authority today. Never exercised jointly with the authority path because the two are never composed. | `ALIVE` as a structural fact, `UNKNOWN` as an exercised joint invariant |
| 3. authority is acquired only after successful admission | False today, demonstrated by the repro: `AuthorityBroker.evaluate()` was reached and returned `authorized=True` with zero prior admission call. | `NOT_FOUND` |
| 4. a broker grant cannot repair or bypass failed semantic admission | Cannot yet be meaningfully tested — since admission is never in the path at all (law 3), there is no "repair" to observe; the grant doesn't bypass admission, it simply never meets it. | `UNKNOWN` (no composed edge exists yet to falsify) |
| 5. deterministic KNOWN routing retains the same fence | **No real local instantiation of "deterministic KNOWN routing" as a distinct concept exists next to admission.** The closest local analog, `MachineExperienceCompiler`'s compiled-rule fast path (`unknown/compilation.py:107-120`, `sa2a/cli.py execute` command), also never touches `AdmissionPipeline`, `AuthorityBroker`, or `ConsequenceBoundary` at all — it resolves a query string and returns a value, with no consequence-bearing dispatch anywhere in its call graph. Force-fitting this law onto that compiler would misdescribe it; **named here as not locally applicable**, not as a passing or failing case. | `NOT_APPLICABLE` (not force-fit) |
| 6. LLM output remains candidate-only until admission succeeds | **No code path in this repo connects LLM/fallback output to `ConsequenceBoundary`/`CommandBus`-equivalent at all**, admitted or not (`MachineExperienceCompiler.resolve()`'s `fallback_llm_inference` return value is handed straight back to the CLI caller as a JSON field, `cli.py:196-204`; it is never constructed into an `ExecutionEnvelope`). A narrower, real, already-existing local falsifier covers an adjacent but different claim — `admission_court.py`'s `falsify_sparql_llm_direct_admitted` (`admission_court.py:861-891`, `SA2A-SPARQL-005`) — which checks that a candidate graph cannot *self-assert* `ADMITTED` standing via a triple, entirely inside `AdmissionPipeline`. That is not the same claim as "LLM output cannot reach CommandBus directly": no CommandBus-equivalent call exists downstream of any LLM-shaped output in this repo today, so the falsifier is vacuously true for want of a target, not because a real gate defeated a real attempt. | `NOT_FOUND` (no LLM-to-DO edge exists to test); adjacent existing falsifier named, not conflated |

## Chicago falsifiers — remote vs. local mapping

| A2A-2604 falsifier | Local mapping | Status |
|---|---|---|
| 1. Grounded admitted package + standing broker grant reaches one real DO and one receipt | Would require composing `AdmissionPipeline.admit()` ahead of `ReactiveSemanticLoop`/`ConsequenceBoundary` — not written yet. | Not yet written (this ticket's DoD, below) |
| 2. Ungrounded semantic candidate with a valid broker grant is refused before DO | **This is exactly the repro above, inverted**: today it is proven NOT refused (`GAP_CONFIRMED: True`). A real falsifier test asserting the *correct* (refusing) behavior does not exist yet; the repro script demonstrates the current wrong behavior only, matching the pattern the two pinned mutation tests below already use (assert current wrong behavior as a named fixture). | `NOT_FOUND` as a passing falsifier; current-wrong-behavior demonstrated real this session |
| 3. Admitted package with no authority is refused before DO | `ConsequenceBoundary.execute()` step 2 (`boundary.py:173-201`) already does refuse when `AuthorityBroker.evaluate()` returns `authorized=False` — this half of the chain is real and working. But since no code path feeds an `AdmissionResult` into the boundary at all, "admitted package" cannot yet be constructed as an input to this check. | `PARTIAL_ALIVE` (the authority-refusal half is real; the admission half has no wiring to test through) |
| 4. Expired/revoked authority cannot turn an admitted package into DO | `AuthorityBroker.evaluate()` already checks `grant.valid_until` (`broker.py:234-240`, real `REFUSED_EXPIRED_GRANT`) — that primitive is real. Composing it with an admitted-package precondition is the same missing wiring as above. | `PARTIAL_ALIVE` |
| 5. Replaying an admitted package does not create a second consequence | `ConsequenceBoundary`'s idempotency-token replay path is real (`boundary.py:159-171`) but **already known broken on the identity axis**: see "Related, already-pinned local violations" below — a replay under a different, never-granted `actor_id` returns the same `EXECUTED` receipt. That is a stronger, already-proven failure of this exact falsifier class. | `NOT_FOUND` for the honest form of this falsifier — the pinned mutation test proves a worse violation exists |
| 6. An LLM candidate cannot call `CommandBus` directly | See Laws #6 above — vacuously true today; no LLM-to-BRCE edge exists to falsify. | `NOT_APPLICABLE` / vacuous |

## Related, already-pinned local violations (different edge, same family — not re-litigated here)

The prior swarm this session found and pinned two real local violations, both read
in full before writing this ticket, both re-run this session for fresh evidence:

```
$ .venv/bin/python -m pytest tests/sa2a/conformance/test_mutation_consequence.py \
    tests/sa2a/conformance/test_mutation_cross_court_identity.py -v
...
3 passed in 0.54s
```

- `tests/sa2a/conformance/test_mutation_consequence.py` —
  `test_idempotency_replay_does_not_bind_replaying_actor_identity`: an ungranted
  adversary who learns a valid idempotency token can replay it under their own
  `actor_id` and receive the original granted actor's `EXECUTED` receipt
  byte-for-byte, without `AuthorityBroker.evaluate()` ever being invoked for the
  adversary's own request. `DEFEATED = FALSE`, asserted as a fixture (module
  docstring, `test_mutation_consequence.py:24-30`).
- `tests/sa2a/conformance/test_mutation_cross_court_identity.py` — a
  `PreparedReceipt`/`FinalReceipt` can self-assert any `grant_id` for any
  action/target pair, and `DurableDiskReceiptStore.save_prepared`/`save_final`
  accept it with no cross-check against a real `AuthorityDecision`; the
  `ConsequenceCourt`'s own real public `audit_idempotency_replay_refusal` gate
  reports `GateVerdict.PASSED` for a receipt whose claimed grant was, moments
  earlier in the same test, independently `REFUSED` by the real broker. Gap finding
  in the module docstring, `test_mutation_cross_court_identity.py:37-52`.

Both are instances of `.claude/rules/no-dual-bookkeeping.md`'s "identity is
explicit or it does not exist" — the **authority-to-receipt** identity edge is
unbound. This ticket's gap is a *different* edge in the same causal chain — the
**candidate-to-authority** edge (admission is skipped entirely, rather than bound
loosely) — upstream of where those two tests operate. Fixing this ticket's gap does
not fix those two, and fixing those two does not fix this ticket's gap; both must be
closed independently. Neither test file was modified by this session.

## Definition of done

- [x] `ReactiveSemanticLoop.run_reflex_cycle` (a new composed entry point, additive
      and opt-in via a new `admission_pipeline` constructor parameter) calls
      `AdmissionPipeline.admit()` on the candidate content and refuses to reach
      `AuthorityBroker.evaluate()` unless `AdmissionResult.standing ==
      Standing.ADMITTED`, bound to the exact same candidate digest that reaches
      authority/BRCE via a new `ExecutionEnvelope.admission_result` field (not merely
      called-before, per `no-dual-bookkeeping.md`). See
      `src/autofde_lab/sa2a/hooks/reactive_loop.py` and
      `src/autofde_lab/sa2a/brce/boundary.py::ConsequenceBoundary.execute_admitted()`.
- [ ] `sa2a/cli.py`'s `hook reflex` command wires the same fence -- **intentionally
      left unwired this session**, documented here as the named reason: `cli.py`'s
      `hook reflex` command constructs `ReactiveSemanticLoop` without an
      `admission_pipeline` (see `cli.py:423`), so it keeps its pre-fix,
      admission-exempt behavior. This was a deliberate scoping decision (the task
      that produced this fix named three gaps, all rooted in the
      `ExecutionEnvelope`/`ConsequenceBoundary.execute()` surface, plus wiring
      `ReactiveSemanticLoop` specifically as "the one real composed entry point";
      `cli.py` wiring was not in that list) -- not an oversight. A follow-up ticket
      should either wire `cli.py` the same way or explicitly refuse to, with its own
      reasoning.
- [x] A Chicago-style falsifier test proves falsifier #2 above in its *correct*
      form: an ungranted-from-admission candidate with a valid broker grant is
      refused before DO -- flipped from proven false to proven true. See
      `tests/sa2a/conformance/test_afde_2604_admission_fencing_closure.py` Part (b)
      (now using `execute_admitted()`, `law_held = True`) and the new, standalone
      `tests/sa2a/conformance/test_afde_2604_boundary_fences.py`.
- [x] A Chicago-style falsifier test proves falsifier #3 in its composed form
      (admitted package + real authority evaluation, not just the authority-only
      half already covered) -- see the same test file's Part (a) (unchanged, still
      real) composed with the now-fixed Part (b), plus new Part (c) proving Required
      Change #4 (a valid grant cannot repair a refused admission).
- [x] `tests/sa2a/` (the real, full suite, not just `conformance/`) re-run with the
      new test(s) included, output pasted verbatim below: `288 passed`.
- [x] No merge, publication, hosted-CI, or cross-repo/ecosystem standing claim is
      inferred from local verification alone, per `.claude/rules/ecosystem-boundary.md`.
      No `git commit`/`git push` was run this session; local file edits and local test
      runs only.
- [x] This ticket's own "Local standing, scoped" table below stays current with
      whatever is actually re-run — see the new section below, added this session.

## Local standing, scoped

- **"The fence (admission as mandatory predecessor of authority/BRCE) does not
  exist in code today"**: `ALIVE` as a negative-existence claim — real grep run
  this session, zero matches, plus a real repro script proving the bypass is
  exploitable, output pasted above.
- **"Each individual component (`AdmissionPipeline`, `AuthorityBroker`,
  `ConsequenceBoundary`, `ReactiveSemanticLoop`) works correctly in isolation"**:
  `ALIVE` — established by reading real source this session; the existing,
  independently-passing test suite for each (`test_admission_pipeline.py`,
  `test_authority.py`, `test_court_consequence.py`,
  `test_autonomic_closed_loop_lifecycle.py`) was not re-run in full this session
  (only the two named mutation files and the closed-loop lifecycle test were run),
  so this line is `PARTIAL_ALIVE` for full-suite confidence, `ALIVE` for the parts
  actually executed this session (`test_autonomic_closed_loop_lifecycle.py`: `1
  passed`, confirmed above).
- **"This ticket closes a cross-repo/ecosystem admission concern"**: explicitly
  false — `UNKNOWN`/not-claimed by construction, per
  `.claude/rules/ecosystem-boundary.md`. This repo's `sa2a/` courts are a local
  testbed for an RFC this repo itself implements for conformance-checking purposes;
  they are not `mfw`'s admission/broker, and no claim here should be read as
  touching that boundary.
- **Overall ticket standing**: `PARTIAL_ALIVE` — the problem is real, reproduced,
  and precisely located; the fix is not yet implemented.

## Local closure work (this session)

**law_held = FALSE.** One new, real, end-to-end fixture composes `AdmissionCourt` +
`AuthorityCourt` + `ConsequenceBoundary` together (not one court in isolation) and
asserts the composed law from the task directly. The composed law does not hold as a
whole; it holds on exactly one of its two halves.

- **Test file (new, this session)**:
  `tests/sa2a/conformance/test_afde_2604_admission_fencing_closure.py`
- **Test function**: `test_composed_admission_authority_consequence_fence`
- **Command (real, run this session)**:
  ```
  .venv/bin/python -m pytest tests/sa2a/conformance/test_afde_2604_admission_fencing_closure.py -v
  ```
- **Real output (verbatim)**:
  ```
  ============================= test session starts ==============================
  platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
  rootdir: /Users/sac/autofde-lab
  configfile: pyproject.toml
  plugins: anyio-4.14.0, nbmake-1.5.5, cov-7.1.0, xdist-3.8.0, timeout-2.4.0, cases-3.10.1
  collected 1 item

  tests/sa2a/conformance/test_afde_2604_admission_fencing_closure.py .     [100%]

  ============================== 1 passed in 0.90s ===============================
  ```
  (This repo's `~/.cache/tmp/pytest-of-sac/garbage-*` stale-tmpdir cleanup — an
  unrelated, pre-existing environment condition, not caused by this file — prints a
  long `PermissionError`/`OSError` warning stream after every local pytest
  invocation on this machine, including bare re-runs of this exact command; it does
  not affect collection, pass/fail, or exit code (`0` on every run this session) and
  is omitted above for signal.)
- **No-mock verification (real grep, this session, over the new file)**:
  ```
  $ grep -n "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" tests/sa2a/conformance/test_afde_2604_admission_fencing_closure.py
  72:- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in
  ```
  The one match is the module docstring's own literal listing of the banned tokens
  (documentation, stating the discipline being followed) — zero matches in actual
  code. Real collaborators only: `AdmissionCourt`/`AdmissionPipeline`,
  `AuthorityCourt`/`AuthorityBroker`/`AuthorityGrant`, `ConsequenceBoundary`,
  `RealDiskJournalActuator`/`IndependentDiskJournalVerifier` (genuine physical disk
  I/O, the same real collaborators the two already-pinned mutation tests use),
  `DurableDiskReceiptStore`.
- **Regression check (real, this session, whole conformance directory)**:
  ```
  $ .venv/bin/python -m pytest tests/sa2a/conformance/ -q
  ........................................................................ [ 43%]
  ........................................................................ [ 86%]
  ......................                                                   [100%]
  ```
  Exit code `0`; all dots, zero `F`/`E` markers, across three separate invocations
  this session (including one with an explicit fresh `--basetemp` under this
  session's own scratchpad directory, to rule out the stale-tmpdir noise above as a
  masked failure). The stale-tmpdir cleanup noise (see above) also suppresses this
  particular pytest configuration's final `"N passed in Xs"` summary line on this
  machine for the whole-directory run specifically (a pre-existing, environment-
  level quirk, reproduced identically on a bare re-run with no source changes at
  all — not something this session's new file causes or fixes); the per-test dot
  stream and the `0` exit code are the real, sufficient evidence that no existing
  test in `tests/sa2a/conformance/` regressed.
- No source under `src/autofde_lab/sa2a/` was modified by this session. No court or
  boundary was patched. Only the new test file above and this ticket were written.

### What the composed fixture establishes

The fixture builds two fully isolated composed episodes (distinct actors, actions,
targets, idempotency tokens, brokers, and disk paths) inside one test function, per
the task's "assert the composed law directly: (a) ... and (b) ...":

**Part (a) — admitted-but-not-yet-authorized is refused before DO: HOLDS.**
A candidate is admitted for real (`AdmissionCourt.pipeline.admit()` →
`Standing.ADMITTED`, confirmed). A fresh `AuthorityBroker` with zero grants and zero
policies is composed into a fresh real `ConsequenceBoundary`
(`RealDiskJournalActuator` + `IndependentDiskJournalVerifier`, real disk-backed
`DurableDiskReceiptStore`). `ConsequenceBoundary.execute()` is called directly for
that admitted content's action/target/actor. Real, observed result:
`success=False`, `state=REFUSED`, `refusal_code=REFUSED_NO_GRANT`,
`actuator.call_count == 0`, and the journal file was never created (zero disk
mutation). This closes for real, under composition, because `ConsequenceBoundary
.execute()`'s Step 2 (`AuthorityBroker.evaluate()`) runs unconditionally before Step
5 (actuate) for every envelope — it does not depend on admission ever having been
consulted; it is simply always-on before any DO.

**Part (b) — authorized-but-never-admitted is refused before DO: DOES NOT HOLD.**
The exact non-RDF candidate content from this session's earlier repro (`"the sky is
blue and this sentence is not RDF in any serialization"`) is submitted to the real
`AdmissionCourt.pipeline.admit()` and is, for real, `Standing.REFUSED` /
`REFUSED_PARSE_FAILURE`. Independently, a real `AuthorityGrant` scoped to a
*different*, unrelated actuation identity (same actor/action/target the DO attempt
below uses, but with no reference anywhere to the refused candidate or its digest)
is registered and confirmed authorized via the real, public
`AuthorityCourt.verify_legitimate_grant_authorized()` gate (not a reimplementation
of `AuthorityBroker.evaluate()`'s logic — the court's own real entry point).
`ExecutionEnvelope` — the sole input type `ConsequenceBoundary.execute()` accepts —
is then asserted, as a real state-based fact (`dataclasses.fields(ExecutionEnvelope)`
compared against the exact field set read from `boundary.py:91-105` this session),
to carry no field that could bind this actuation attempt to the refused
`AdmissionResult` at all: `admitted_semantics: Optional[AdmittedSemantics]` exists on
the envelope but is a **different, self-asserted dataclass** from
`construct/constructor.py`, unrelated to `admission/pipeline.py`'s `AdmissionResult`,
optional, and never populated by the real composed caller
`ReactiveSemanticLoop.run_reflex_cycle` today (`reactive_loop.py:118-125` sets only
`idempotency_token`/`action_iri`/`target_resource`/`parameters`/`actor_id`/
`grant_id`). The authorized envelope is then executed through the real boundary.
Real, observed result: `success=True`, `state=EXECUTED`, `refusal_code=None`,
`actuator.call_count == 1` (a real disk journal entry was written),
`final_receipt.postcondition_verified is True` (independent verifier, reading the
disk back, confirms the write genuinely happened). This reproduces the exact
`candidate -> authority -> DO` anti-pattern from this session's earlier
`afde2604_repro.py` script, now as a pinned pytest fixture composing all three real
courts/boundary together rather than a one-off script — and shows that composing the
courts in one test cannot, by itself, close the gap: the gap is at the
`ExecutionEnvelope` interface, not merely a call this test could route around.

### law_held: FALSE — precise gap_finding

Composing `AdmissionCourt` + `AuthorityCourt` + `ConsequenceBoundary` together in one
real, end-to-end test does **not** close the fence AFDE-2604 requires. The composed
law holds on exactly one of its two required halves:

- (a) holds unconditionally today, because Authority evaluation in
  `ConsequenceBoundary.execute()` is an always-on precondition of actuation,
  independent of admission.
- (b) fails, and cannot be made to pass by composition alone, because
  `ExecutionEnvelope` (`src/autofde_lab/sa2a/brce/boundary.py:91-105`) — the only
  input `ConsequenceBoundary.execute()` accepts — has no field capable of carrying a
  real `admission.pipeline.AdmissionResult`/`AdmissionReceipt`, and the one
  superficially similarly-named field it does have (`admitted_semantics`) is a
  distinct, self-asserted, unwired dataclass from a different module. There is
  therefore no way, at the object/interface level, for an `AdmissionResult.standing
  == Standing.REFUSED` verdict to ever reach or influence `ConsequenceBoundary
  .execute()` — not because no caller happens to check it today, but because there
  is nowhere on the envelope to put it. Closing this requires changing
  `ExecutionEnvelope`/`ConsequenceBoundary.execute()` (or the composed entry point
  that constructs the envelope, e.g. `ReactiveSemanticLoop.run_reflex_cycle`) per
  AFDE-2604's own Definition of Done — out of scope for a test-only fixture, and
  correctly left unpatched here per the task's instruction not to patch court or
  boundary source.

This confirms, under a genuine three-court composition (not a single-boundary
repro), the same conclusion the rest of this ticket already reached from source
reading and the standalone repro script: AFDE-2604 Laws #1 and #3 remain
`NOT_FOUND` as enforced behavior, and Chicago falsifier #2 remains unsatisfied in
its correct (refusing) form. The two already-pinned, different-edge violations
(`test_mutation_consequence.py`, `test_mutation_cross_court_identity.py`, the
authority-to-receipt identity edge) are unaffected by and independent of this
finding, consistent with the rest of this ticket's "Related, already-pinned local
violations" section above.

### Local standing, scoped (this session's addition)

- **"A genuine three-court composition (admission_court + authority_court +
  ConsequenceBoundary) closes the candidate-to-authority fence"**: `NOT_FOUND` — real
  pytest fixture run this session, output above; the composed law is FALSE
  (`law_held = False`), part (b) fails for real, with real disk evidence of an
  actual DO on admission-refused content.
- **"Part (a) of the composed law (admitted-but-unauthorized refused before DO)
  holds under real composition"**: `ALIVE` — real pytest fixture run this session,
  zero actuation, zero disk mutation, `REFUSED_NO_GRANT`.
- **This ticket's overall standing** is unchanged by this addition:
  `PARTIAL_ALIVE` — the problem is real, now reproduced through three independent
  artifacts (the original repro script, the two already-pinned mutation tests on the
  neighboring edge, and this session's new composed fixture), precisely located, and
  the fix is not yet implemented.

**Superseded by the "Local closure work (fix implemented)" section immediately
below, from a later pass in this same session** — kept in place, not deleted, per
`docs/CLAUDE.md`'s "historical corrections stay visible" invariant. Everything above
this point in the file describes the state BEFORE the fix; everything below
describes the fix itself, run and verified this session.

## Local closure work (fix implemented)

**law_held = TRUE for the three named gaps.** This session (a later pass than the one
above, in the same sitting) implemented the fix, updated the two pre-existing pinned
tests whose assertions pinned the OLD, wrong behavior, and added one new standalone
test file. All changes are additive to `src/autofde_lab/sa2a/brce/boundary.py` and
`src/autofde_lab/sa2a/hooks/reactive_loop.py` only — no other court/boundary source
under `src/autofde_lab/sa2a/` was touched.

### Gap (1): `ExecutionEnvelope` had no field to bind a real `AdmissionResult`

**Fix**: `ExecutionEnvelope` gained a new, optional, additive field:

```python
admission_result: Optional[AdmissionResult] = None
```

(`src/autofde_lab/sa2a/brce/boundary.py`, `ExecutionEnvelope` dataclass.) Every
existing caller that never populates it is completely unaffected —
`ConsequenceBoundary.execute()` itself never inspects this field.

A new, strict, opt-in entry point was added alongside `execute()`, not in place of
it:

```python
ConsequenceBoundary.execute_admitted(envelope) -> BoundaryExecutionResult
```

It refuses (typed `REFUSED_NOT_ADMITTED`, never a bare exception) any envelope whose
`admission_result` is `None` or whose `standing != Standing.ADMITTED`, **before**
`AuthorityBroker.evaluate()` (Step 2) or actuation (Step 5) are ever reached. If a
final receipt already exists for the envelope's `idempotency_token` (a prior
admission refusal, authority refusal, or real execution), the admission gate is
skipped and the call is delegated straight to `execute()`, whose own Step 1 handling
(including the Gap (2)/(3) fix below) is the single source of truth for a repeated
token — this avoids a double `ReceiptStore.save_final()` write under the same token,
which would otherwise raise on digest mismatch.

`ReactiveSemanticLoop` (`src/autofde_lab/sa2a/hooks/reactive_loop.py`) — "the one
real composed entry point this repo actually has for the live semantic-dispatch
path" — gained a new, optional `admission_pipeline: Optional[AdmissionPipeline] =
None` constructor parameter. When configured, `run_reflex_cycle` admits the current
cycle's candidate content (`current_event`) once per cycle via a real
`AdmissionPipeline.admit()` call, and every intent synthesized from that cycle is
refused (typed `REFUSED_NOT_ADMITTED`, `AuthorityBroker.evaluate()` never consulted)
unless the resulting `AdmissionResult.standing == Standing.ADMITTED` — the SAME
admission result is bound onto every envelope constructed from that cycle
(`admission_result=admission_result`), and `execute_admitted()` is used instead of
`execute()`. When `admission_pipeline` is omitted (the default), behavior is
byte-for-byte unchanged from before this session — confirmed by the full
`tests/sa2a/` run below, which includes seven pre-existing call sites of
`ReactiveSemanticLoop`/`run_reflex_cycle` that never pass `admission_pipeline` and
all still pass. `sa2a/cli.py`'s `hook reflex` command is one of those seven and was
deliberately left unwired this session — see the Definition of Done item above for
the named reason.

### Gap (2): idempotency-token replay never verified the replaying actor's identity

**Fix**: `ConsequenceBoundary.execute()` Step 1's idempotency short-circuit
(`src/autofde_lab/sa2a/brce/boundary.py`, inside `execute()`) now, whenever the
cached `FinalReceipt` for a repeated `idempotency_token` has `state ==
TerminalReceiptState.EXECUTED`, performs a **fresh** `AuthorityBroker.evaluate()`
call for the REPLAYING envelope's own `actor_id`/`action_iri`/`target_resource`
(deliberately never trusting `envelope.grant_id` or the cached receipt's own
self-asserted `grant_id`) before returning the cached response. If that fresh
re-check does not confirm authorization, the replay is refused with a new typed
code, `REFUSED_REPLAY_NOT_REAUTHORIZED`, and a deterministic (not
`uuid4()`/`time.time()`-based) refusal receipt is returned — never persisted under
the token, since the store already durably owns the original final and
`ReceiptStore.save_final()` would raise on a digest mismatch if overwritten. Cached
`REFUSED` (non-`EXECUTED`) replays are unaffected — this fix is scoped to protecting
a cached **success** from being handed to an unauthorized replaying identity, the
literal concern named in the gap.

A legitimate same-actor replay is now re-verified (not merely cached) and still
succeeds, returning the exact same cached digest — confirmed both by the updated
`test_mutation_consequence.py`'s own gate-composed replay and by the new standalone
test.

### Gap (3): no receipt grant_id was bound to a real, re-checkable `AuthorityDecision`

**Fix**: the SAME re-authorization check that closes Gap (2) also closes Gap (3): a
directly-constructed, forged `PreparedReceipt`/`FinalReceipt` pair (self-asserting a
real `grant_id` for an action/target that grant never actually covers, bypassing
`ConsequenceBoundary.execute()` entirely to reach the store) is durably persisted by
`ReceiptStore.save_prepared`/`save_final` exactly as before — that finding in
`test_mutation_cross_court_identity.py` Test 1 stands, unchanged, deliberately (the
store remains an intentionally dumb, append-only persistence layer). What changed:
the moment ANYTHING replays that token through the real
`ConsequenceBoundary.execute()` again, the fresh re-authorization check re-derives
whether the request's own actor/action/target identity is currently, honestly
authorized — ignoring the forged receipt's self-asserted `grant_id` string entirely
— and refuses it. A forged receipt sitting in the store is therefore inert: it can
never again be handed back as a trusted `EXECUTED` result.

### Evidence

**Zero-mock grep, run this session, over every test file touched or added**:

```
$ grep -n "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" \
    tests/sa2a/conformance/test_afde_2604_boundary_fences.py \
    tests/sa2a/conformance/test_afde_2604_admission_fencing_closure.py \
    tests/sa2a/conformance/test_mutation_consequence.py \
    tests/sa2a/conformance/test_mutation_cross_court_identity.py
tests/sa2a/conformance/test_afde_2604_boundary_fences.py:38:- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in this
tests/sa2a/conformance/test_afde_2604_admission_fencing_closure.py:80:- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in
tests/sa2a/conformance/test_mutation_cross_court_identity.py:94:  the mismatch. No `unittest.mock`, `Mock`, `MagicMock`, `patch`, or
tests/sa2a/conformance/test_mutation_cross_court_identity.py:95:  `monkeypatch` appears anywhere in this file.
tests/sa2a/conformance/test_mutation_consequence.py:16:- Zero unittest.mock / Mock / MagicMock / patch / monkeypatch.
```

Every match is a module docstring's own literal listing of the banned tokens
(documentation stating the discipline being followed) — zero matches in actual code,
across all four files.

**Real, full `tests/sa2a/` suite run, this session, verbatim tail**:

```
$ .venv/bin/python -m pytest tests/sa2a/ -v --basetemp=/tmp/afl_fix_taskA_final
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
rootdir: /Users/sac/autofde-lab
configfile: pyproject.toml
plugins: anyio-4.14.0, nbmake-1.5.5, cov-7.1.0, xdist-3.8.0, timeout-2.4.0, cases-3.10.1
collected 288 items

tests/sa2a/conformance/test_afde_2604_admission_fencing_closure.py .     [  0%]
tests/sa2a/conformance/test_afde_2604_boundary_fences.py ...             [  1%]
tests/sa2a/conformance/test_court_admission.py ........................  [  9%]
tests/sa2a/conformance/test_court_authority.py .....................     [ 17%]
tests/sa2a/conformance/test_court_consequence.py ......                  [ 19%]
tests/sa2a/conformance/test_court_identity.py .......................... [ 28%]
....                                                                     [ 29%]
tests/sa2a/conformance/test_court_logic_hook.py ........................ [ 37%]
......                                                                   [ 39%]
tests/sa2a/conformance/test_court_replay.py .......                      [ 42%]
tests/sa2a/conformance/test_mutation_admission.py ...                    [ 43%]
tests/sa2a/conformance/test_mutation_authority.py ..                     [ 44%]
tests/sa2a/conformance/test_mutation_consequence.py .                    [ 44%]
tests/sa2a/conformance/test_mutation_cross_court_identity.py ..          [ 45%]
tests/sa2a/conformance/test_mutation_identity.py ...                     [ 46%]
tests/sa2a/conformance/test_mutation_logic_hook.py ..                    [ 46%]
tests/sa2a/conformance/test_mutation_replay.py .                         [ 47%]
tests/sa2a/conformance/test_ocel_queries.py ...........................  [ 56%]
tests/sa2a/conformance/test_ocel_queries_falsifiers.py ......            [ 58%]
tests/sa2a/test_admission_pipeline.py ...........                        [ 62%]
tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py ...   [ 63%]
tests/sa2a/test_authority.py ............                                [ 67%]
tests/sa2a/test_autonomic_closed_loop_lifecycle.py .                     [ 68%]
tests/sa2a/test_brce_replay.py ........                                  [ 70%]
tests/sa2a/test_canonicalizer_shacl.py ......                            [ 72%]
tests/sa2a/test_construct.py .......                                     [ 75%]
tests/sa2a/test_cross_runtime_falsifier.py .                             [ 75%]
tests/sa2a/test_datalog_n3.py ......                                     [ 77%]
tests/sa2a/test_falsifiers_meta.py ....................                  [ 84%]
tests/sa2a/test_foundation.py ........                                   [ 87%]
tests/sa2a/test_graphlaw_bridge.py ...                                   [ 88%]
tests/sa2a/test_hook_synthesis.py .                                      [ 88%]
tests/sa2a/test_knowledge_hooks.py .....                                 [ 90%]
tests/sa2a/test_novelty_ingest.py ..                                     [ 91%]
tests/sa2a/test_unknown_bridge.py ...........                            [ 95%]
tests/sa2a/test_v26_9_16_chicago_court.py ..                             [ 95%]
tests/sa2a/test_v26_9_16_falsification_court.py ............             [100%]

============================= 288 passed in 9.24s ==============================
```

Zero failures, zero errors, `288 passed`. This is a real whole-`tests/sa2a/` run
(not just `conformance/`), including every pre-existing test that constructs
`ReactiveSemanticLoop` (seven real call sites across
`test_afde_2612_repeat_episode_zero_inference_closure.py`,
`test_autonomic_closed_loop_lifecycle.py`, `test_knowledge_hooks.py` (×2),
`test_v26_9_16_chicago_court.py`, `test_v26_9_16_falsification_court.py` (×2)),
every pre-existing test that constructs `ExecutionEnvelope` directly, and both
pre-existing pinned mutation tests (now updated) plus the new composed and
standalone test files — nothing regressed.

### Pinned tests updated (not deleted, not weakened)

Per this repo's fix-forward, no-reverted-tests discipline: both pre-existing pinned
tests whose assertions pinned the OLD, wrong behavior were updated in place to
assert the NEW, correct behavior, with docstrings explaining exactly what changed
and why — the adversarial construction (identity swap / forged grant claim) is
unchanged; only the expected outcome flips from accepted-wrongly to
correctly-refused:

- `tests/sa2a/conformance/test_mutation_consequence.py` —
  `test_idempotency_replay_does_not_bind_replaying_actor_identity`: now asserts
  `DEFEATED = TRUE` (previously `FALSE`); the adversary's replay now receives
  `success=False`, `state=REFUSED`, `refusal_code=REFUSED_REPLAY_NOT_REAUTHORIZED`,
  and a receipt digest that DIFFERS from the granted actor's original — the granted
  actor's own durable record is left completely untouched.
- `tests/sa2a/conformance/test_mutation_cross_court_identity.py` —
  Test 1 (`test_receipt_store_accepts_grant_id_claim_for_never_authorized_actuation_identity`)
  is UNCHANGED (the store-layer finding still stands, deliberately — see Gap (3)
  fix above). Test 2
  (`test_consequence_court_replay_gate_reports_conformant_for_mismatched_grant_claim`)
  keeps its `gate_result.verdict == GateVerdict.PASSED` assertion (that gate checks
  replay *stability*, not claim legitimacy, and both pre- and post-fix a stable
  replay is what happens — pre-fix stably wrong, post-fix stably refused) but adds a
  new, direct `ConsequenceBoundary.execute()` call proving the underlying fix:
  `success=False`, `state=REFUSED`, `refusal_code=REFUSED_REPLAY_NOT_REAUTHORIZED`.

### New test file added

`tests/sa2a/conformance/test_afde_2604_boundary_fences.py` — three standalone,
court-free Chicago tests exercising `ConsequenceBoundary`/`ExecutionEnvelope`
directly, one per fix:

1. `test_execute_admitted_refuses_missing_and_refused_admission_but_allows_admitted`
   — Gap (1): no `admission_result` → refused; `REFUSED` `admission_result` →
   refused; `ADMITTED` `admission_result` with a real grant → genuinely executes
   (real disk actuation, real independent postcondition verification).
2. `test_replay_under_different_never_granted_actor_is_refused` — Gap (2): a
   legitimate same-actor replay is re-verified and still succeeds; a distinct,
   never-granted adversary actor replaying the same token is refused.
3. `test_forged_receipt_pair_is_refused_on_replay_despite_self_asserted_grant_id` —
   Gap (3): a directly-forged `PreparedReceipt`/`FinalReceipt` pair, durably saved
   to the store bypassing the boundary, is refused the moment a real
   `ConsequenceBoundary.execute()` call replays that token — with a positive control
   confirming the same broker still honestly authorizes the real, legitimate
   identity the grant actually covers.

### Local standing, scoped (fix-implemented addition)

- **"`ConsequenceBoundary.execute_admitted()` refuses an authorized-but-never-
  admitted candidate before DO"**: `ALIVE` — real pytest run this session, zero
  actuation, zero disk mutation, `REFUSED_NOT_ADMITTED`
  (`test_afde_2604_admission_fencing_closure.py` Part (b),
  `test_afde_2604_boundary_fences.py`).
- **"A valid AuthorityGrant cannot repair or bypass a REFUSED admission outcome for
  the same candidate"** (Required Change #4): `ALIVE` — real pytest run this
  session, `test_afde_2604_admission_fencing_closure.py` Part (c).
- **"An idempotency-token replay under a different, never-granted actor identity is
  refused"**: `ALIVE` — real pytest run this session,
  `test_mutation_consequence.py` (updated) and `test_afde_2604_boundary_fences.py`.
- **"A receipt's self-asserted `grant_id` cannot be used to reach a trusted
  `EXECUTED` result once replayed through the real boundary, even if it was durably
  persisted bypassing the boundary"**: `ALIVE` — real pytest run this session,
  `test_mutation_cross_court_identity.py` (updated) and
  `test_afde_2604_boundary_fences.py`.
- **"`ReactiveSemanticLoop.run_reflex_cycle`'s DEFAULT (no `admission_pipeline`)
  behavior is unchanged"**: `ALIVE` — the full `tests/sa2a/` run above (288 passed)
  includes seven pre-existing call sites that never pass `admission_pipeline`.
- **"The receipt store itself (`ReceiptStore.save_prepared`/`save_final`) now
  validates a `grant_id` claim before accepting it"**: explicitly `UNSUPPORTED` (not
  attempted, not claimed) — this was a deliberate scope decision, not an oversight;
  see the Gap (3) fix description above for why the store was intentionally left
  unchanged.
- **"`sa2a/cli.py`'s `hook reflex` command enforces the admission fence"**:
  `UNSUPPORTED` (intentionally unwired this session) — see the Definition of Done
  item above.
- **Overall ticket standing**: `PARTIAL_ALIVE` (upgraded from `PARTIAL_ALIVE` for a
  different reason than before — previously "the fix is not yet implemented," now
  "the fix is implemented and verified for the opt-in/strict paths named in the
  task, but the repo-wide default paths (`execute()` without
  `admission_result`/`ReactiveSemanticLoop` without `admission_pipeline`, including
  `sa2a/cli.py`) remain deliberately unfenced by additive design, not a completed
  global migration"). No `git commit`/`git push` was run this session — local file
  edits and local test runs only, per the task's own instruction.

## Fresh-mutations qualification closure (2026-09-16, this session)

**law_held = TRUE for all 3 freshly-found gaps.** A later, independent adversarial
qualification pass (a fresh reviewer, not the session that produced "Local closure
work (fix implemented)" above) constructed three NEW mutations against the SAME
`ExecutionEnvelope`/`ConsequenceBoundary` surface, deliberately different from the two
already-pinned mutations this ticket names above, and pinned them as real failing
tests in `tests/sa2a/conformance/test_afde_2604_fresh_mutations_qualification.py`.
This session closed all three, additively, on top of the existing fix -- no existing
test in `tests/sa2a/` was reverted or weakened to make these pass.

### Mutation A: content-unbound admission reuse

**Finding**: `ExecutionEnvelope.admission_result`/`ConsequenceBoundary
.execute_admitted()` checked only `admission.standing == Standing.ADMITTED`. A real,
genuinely `Standing.ADMITTED` `AdmissionResult` produced by admitting one harmless,
unrelated candidate graph could be reused verbatim on an envelope for a completely
different, more sensitive action/target the admitted candidate's content never
mentioned at all -- neither the envelope nor the boundary bound the admitted
CONTENT to the actuated `action_iri`/`target_resource`.

**Fix**: a new module-level helper in `src/autofde_lab/sa2a/brce/boundary.py`,
`_admission_covers_action_target(admission, action_iri, target_resource)`, inspects
the admitted candidate's own real rdflib graph (`AdmissionResult.graph` -- the exact
graph that reached `Standing.ADMITTED`, per `admission/pipeline.py`) for both the
`action_iri` and `target_resource` as real RDF nodes (`Graph.all_nodes()`
containment). `ConsequenceBoundary.execute_admitted()` calls this whenever
`admission.standing == Standing.ADMITTED`, refusing with a new typed code,
`REFUSED_ADMISSION_CONTENT_NOT_BOUND`, before `AuthorityBroker.evaluate()` or
actuation are ever reached, if the check fails. Binding is derived from the admitted
CONTENT itself, deliberately never from a self-asserted field on the envelope (an
adversary controls a self-asserted field exactly as freely as a legitimate caller
does, so a self-asserted binding would prove nothing) -- consistent with
`.claude/rules/no-dual-bookkeeping.md`'s "identity is explicit or it does not exist."

**Fixture consequence**: `tests/sa2a/conformance/test_afde_2604_boundary_fences.py`'s
`_ADMITTABLE_TTL` (episode 1c, the file's own "ADMITTED admission_result with a real
grant genuinely executes" positive control) previously used content wholly unrelated
to its own action/target -- exactly the same shape as Mutation A's exploit, just not
adversarially probed. It was updated to literally reference its own
`action`/`urn:resource:fence-c` identity so it remains a legitimately content-bound
admission under the new, stricter contract. This is a fixture adaptation to the
tightened contract, not a weakening: the test still proves the exact same property
it always did.

### Mutation B: cross-action idempotency-token substitution

**Finding**: the SAME actor, holding valid, independent grants for TWO DIFFERENT
actions, executes action1 under token T (real actuation, real receipt), then replays
the SAME token T with action2/target2 substituted in. The existing fix (2)/(3)
re-authorization check in `ConsequenceBoundary.execute()` Step 1 correctly evaluates
authority for action2/target2 (and it IS authorized) -- but then unconditionally
returned the STALE `existing_final` receipt minted for action1, reporting
`success=True`, WITHOUT ever actuating action2. The receipt handed back named
action1's identity for an action2 request -- a `no-dual-bookkeeping.md`
object-identity violation, distinct from (and upstream of) the actor-identity
violation the original fix (2)/(3) already closed.

**Fix**: inside `ConsequenceBoundary.execute()` Step 1's
`existing_final.state == TerminalReceiptState.EXECUTED` branch, BEFORE the existing
re-authorization check, the token's bound identity -- the `action_iri`/
`target_resource` recorded on the `PreparedReceipt` minted at this token's first
EXECUTED write (Step 4 always mints this before actuation, so it is always present
for an EXECUTED final) -- is compared against the REPLAYING envelope's own
`action_iri`/`target_resource`. A mismatch refuses immediately with a new typed code,
`REFUSED_TOKEN_ACTION_MISMATCH`, WITHOUT ever asking whether the substituted identity
happens to be independently authorized: an idempotency token identifies one fixed
actuation identity, never a menu of identities the replaying request may swap in
after the fact. The refusal receipt is deterministic and non-persisted (the store
already durably owns the original action1 final under this token), mirroring the
existing fix (2)/(3) non-persisted-mismatch-receipt pattern.

**Test tightening**: `test_mutation_b_...`'s original assertion was a deliberately
weak disjunction (`(not second.success) or action2_actually_actuated`), written
before the specific fix approach was known. With the fix's exact behavior now known
(refuse, never substitute-actuate), the test was tightened to assert the precise
outcome (`REFUSED_TOKEN_ACTION_MISMATCH`, zero actuation of action2, action1's
original receipt digest untouched) in addition to the original disjunction, which is
kept in place as a standing, more permissive fallback check.

### Mutation C: admission fence bypass via already-executed token replay

**Finding**: a token was first executed through `execute_admitted()` with a real
ADMITTED `admission_result` (genuine actuation). The SAME token was then replayed
through `execute_admitted()` a second time with `admission_result=None`. Because the
original fix only checked admission when `receipt_store.get_final(token) is None`,
and a final receipt now existed from the first call, the admission gate was skipped
entirely on the second call and control fell straight through to `execute()`'s
replay/reauth path, which re-authorized (same actor/action/target as the first call)
and returned `success=True` -- so the "strict, admission-gated entry point" required
admission only on the first call through it, not on every call.

**Fix**: `ConsequenceBoundary.execute_admitted()` was restructured so the admission
gate (both the `Standing.ADMITTED` check and the new Mutation-A content-binding
check above) is evaluated unconditionally on EVERY call through this entry point --
never skipped merely because a final receipt already exists under the token. When
the gate fails on a call made AFTER a final receipt already exists, a deterministic,
non-persisted typed refusal (`REFUSED_NOT_ADMITTED` or
`REFUSED_ADMISSION_CONTENT_NOT_BOUND`, as applicable) is returned for THAT call,
leaving the token's existing durable record completely untouched. When the gate
passes, control is delegated to `execute()` exactly as before, so a genuine,
correctly-admitted replay (same token, same real admission presented again) is
unaffected.

**Fixture consequence**: Mutation C's own candidate content was changed from the
byte-identical `_HARMLESS_ADMITTABLE_TTL` Mutation A uses to a new, dedicated
`_MUT_C_BOUND_TTL` that explicitly references Mutation C's own action/target. This
was necessary so Mutation C's legitimate FIRST call (which must still succeed) is
not itself refused by the NEW Mutation-A content-binding check -- isolating the two
concerns cleanly: Mutation C's mutation is specifically "is admission checked on
every call," not "is the admission content-bound," which Mutation A already covers
on its own dedicated, deliberately unbound fixture. This is a fixture adaptation to
the tightened contract, not a weakening of the mutation itself.

### Evidence

**Zero-mock grep, run this session, over both files touched**:

```
$ grep -n "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" \
    tests/sa2a/conformance/test_afde_2604_fresh_mutations_qualification.py \
    tests/sa2a/conformance/test_afde_2604_boundary_fences.py
tests/sa2a/conformance/test_afde_2604_boundary_fences.py:38:- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in this
tests/sa2a/conformance/test_afde_2604_fresh_mutations_qualification.py:48:- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in this
```

Both matches are the module docstrings' own literal listing of the banned tokens
(documentation stating the discipline being followed) -- zero matches in actual code.

**Fresh-mutations file alone, run this session**:

```
$ .venv/bin/python -m pytest tests/sa2a/conformance/test_afde_2604_fresh_mutations_qualification.py -v --basetemp=/tmp/afl_finishA_mut
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
collected 3 items

tests/sa2a/conformance/test_afde_2604_fresh_mutations_qualification.py . [ 33%]
..                                                                       [100%]

=============================== warnings summary ===============================
src/autofde_lab/sa2a/brce/boundary.py:192
  /Users/sac/autofde-lab/src/autofde_lab/sa2a/brce/boundary.py:192: SyntaxWarning: invalid escape sequence '\m'
    3. Verify Construction integrity if artifact supplied: A = \mu(O*) (§5, §26)

========================= 3 passed, 1 warning in 1.47s =========================
```

(The `SyntaxWarning` is a pre-existing docstring artifact in `boundary.py`'s class
docstring, unrelated to and unchanged by this session's edits -- noted for
completeness, not a new defect.)

**Directly-related, previously-passing files, re-run this session to confirm zero
regression from the boundary.py fix**:

```
$ .venv/bin/python -m pytest tests/sa2a/conformance/test_afde_2604_boundary_fences.py \
    tests/sa2a/conformance/test_afde_2604_admission_fencing_closure.py \
    tests/sa2a/conformance/test_mutation_consequence.py \
    tests/sa2a/conformance/test_mutation_cross_court_identity.py -v --basetemp=/tmp/afl_finishA_related
collected 7 items

tests/sa2a/conformance/test_afde_2604_boundary_fences.py ...             [ 42%]
tests/sa2a/conformance/test_afde_2604_admission_fencing_closure.py .     [ 57%]
tests/sa2a/conformance/test_mutation_consequence.py .                    [ 71%]
tests/sa2a/conformance/test_mutation_cross_court_identity.py ..          [100%]

============================== 7 passed in 0.98s ===============================
```

**Full `tests/sa2a/` suite, run this session, verbatim tail**:

```
$ .venv/bin/python -m pytest tests/sa2a/ -v --basetemp=/tmp/afl_finishA
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
rootdir: /Users/sac/autofde-lab
configfile: pyproject.toml
plugins: langsmith-0.12.1, anyio-4.14.0, nbmake-1.5.5, cov-7.1.0, xdist-3.8.0, timeout-2.4.0, Faker-40.36.0, cases-3.10.1
collected 299 items

tests/sa2a/conformance/test_afde_2604_admission_fencing_closure.py .     [  0%]
tests/sa2a/conformance/test_afde_2604_boundary_fences.py ...             [  1%]
tests/sa2a/conformance/test_afde_2604_fresh_mutations_qualification.py . [  1%]
..                                                                       [  2%]
tests/sa2a/conformance/test_afde_2604_receipt_store_grant_validation.py . [  2%]
......                                                                   [  4%]
tests/sa2a/conformance/test_court_admission.py ........................  [ 12%]
tests/sa2a/conformance/test_court_authority.py .....................     [ 19%]
tests/sa2a/conformance/test_court_consequence.py ......                  [ 21%]
tests/sa2a/conformance/test_court_identity.py .......................... [ 30%]
....                                                                     [ 31%]
tests/sa2a/conformance/test_court_logic_hook.py ........................ [ 39%]
......                                                                   [ 41%]
tests/sa2a/conformance/test_court_replay.py .......                      [ 44%]
tests/sa2a/conformance/test_mutation_admission.py ...                    [ 45%]
tests/sa2a/conformance/test_mutation_authority.py ..                     [ 45%]
tests/sa2a/conformance/test_mutation_consequence.py .                    [ 46%]
tests/sa2a/conformance/test_mutation_cross_court_identity.py ..          [ 46%]
tests/sa2a/conformance/test_mutation_identity.py ...                     [ 47%]
tests/sa2a/conformance/test_mutation_logic_hook.py ..                    [ 48%]
tests/sa2a/conformance/test_mutation_replay.py .                         [ 48%]
tests/sa2a/conformance/test_ocel_queries.py ...........................  [ 57%]
tests/sa2a/conformance/test_ocel_queries_falsifiers.py ......            [ 59%]
tests/sa2a/test_admission_pipeline.py ...........                        [ 63%]
tests/sa2a/test_afde_2612_repeat_episode_zero_inference_closure.py ...   [ 64%]
tests/sa2a/test_authority.py ............                                [ 68%]
tests/sa2a/test_autonomic_closed_loop_lifecycle.py .                     [ 68%]
tests/sa2a/test_brce_replay.py ........                                  [ 71%]
tests/sa2a/test_canonicalizer_shacl.py ......                            [ 73%]
tests/sa2a/test_construct.py .......                                     [ 75%]
tests/sa2a/test_cross_runtime_falsifier.py .                             [ 76%]
tests/sa2a/test_datalog_n3.py ......                                     [ 78%]
tests/sa2a/test_falsifiers_meta.py ....................                  [ 84%]
tests/sa2a/test_foundation.py ........                                   [ 87%]
tests/sa2a/test_graphlaw_bridge.py ....                                  [ 88%]
tests/sa2a/test_hook_synthesis.py .                                      [ 89%]
tests/sa2a/test_knowledge_hooks.py .....                                 [ 90%]
tests/sa2a/test_novelty_ingest.py ..                                     [ 91%]
tests/sa2a/test_unknown_bridge.py ...........                            [ 95%]
tests/sa2a/test_v26_9_16_chicago_court.py ..                             [ 95%]
tests/sa2a/test_v26_9_16_falsification_court.py ............             [100%]

============================= 299 passed in 9.85s ===============================
```

299 collected/passed here vs. the 288 quoted in "Local closure work (fix
implemented)" above: the delta is other, unrelated test files added to
`tests/sa2a/` by other work in this same branch between that session and this one
(`test_afde_2604_fresh_mutations_qualification.py` itself, plus
`test_afde_2604_receipt_store_grant_validation.py` and others already present in
this session's working tree before this task began -- confirmed via `git status
--porcelain` showing only `src/autofde_lab/sa2a/brce/boundary.py` as a tracked
modification, and `tests/sa2a/conformance/` as a pre-existing untracked directory
this session did not create). Zero failures, zero errors, `299 passed` -- no
regression from the boundary.py fix in any pre-existing test.

### Local standing, scoped (fresh-mutations closure addition)

- **"Mutation A (content-unbound admission reuse) is defeated"**: `ALIVE` -- real
  pytest run this session, `REFUSED_ADMISSION_CONTENT_NOT_BOUND`, zero actuation,
  zero disk mutation.
- **"Mutation B (cross-action idempotency-token substitution) is defeated"**:
  `ALIVE` -- real pytest run this session, `REFUSED_TOKEN_ACTION_MISMATCH`, zero
  actuation of the substituted action, original receipt untouched.
- **"Mutation C (admission fence bypass via already-executed token replay) is
  defeated"**: `ALIVE` -- real pytest run this session, `REFUSED_NOT_ADMITTED` on
  every call through `execute_admitted()`, not merely the first.
- **"No existing test in `tests/sa2a/` regressed"**: `ALIVE` -- full-suite run this
  session, `299 passed`, zero failures/errors.
- **Overall ticket standing**: unchanged at `PARTIAL_ALIVE` for the same reason
  named in the prior section (the repo-wide default/backward-compatible paths
  remain deliberately unfenced by additive design) -- now additionally qualified
  against three fresh, independent adversarial mutations on top of the two
  originally-pinned ones, with all five now defeated. No `git commit`/`git push`
  was run this session -- local file edits and local test runs only.

## See also

- `A2A-2604-wire-semantic-admission-to-live-do-path.md` (remote ash_a2a ticket this
  document is the local equivalent of; not owned by this repo, read but not copied).
- `.claude/rules/ecosystem-boundary.md` — the boundary this ticket stays inside.
- `.claude/rules/no-dual-bookkeeping.md` — the "identity is explicit or it does not
  exist" discipline both the pinned mutation tests and this ticket's candidate-to-
  authority edge instantiate.
- `.claude/rules/standing-law.md` — the status vocabulary used in this document.
- `.claude/rules/testing-chicago-style.md` — the real-collaborator discipline the
  repro script and the two pinned mutation tests both follow.
- `tests/sa2a/conformance/test_mutation_consequence.py`,
  `tests/sa2a/conformance/test_mutation_cross_court_identity.py` — the related,
  already-pinned violations on the neighboring authority-to-receipt edge; both
  updated this session to assert the fixed behavior (see "Local closure work (fix
  implemented)" above).
- `tests/sa2a/conformance/test_afde_2604_boundary_fences.py` — new standalone,
  court-free direct falsifiers for all three fixes, added this session.
- `tests/sa2a/conformance/test_afde_2604_fresh_mutations_qualification.py` — the
  three freshly-found mutations closed this session (see "Fresh-mutations
  qualification closure" above).
- `src/autofde_lab/sa2a/brce/boundary.py`,
  `src/autofde_lab/sa2a/hooks/reactive_loop.py` — the two files modified this
  session to implement the fix; `boundary.py` was modified again in the
  fresh-mutations closure pass above (`reactive_loop.py` was not touched by that
  pass).
- `docs/jira/v26.9.16/AFDE-2607-cross-repo-seam-typing.md` — sibling local ticket in
  this same v26.9.16 directory, same scoping discipline applied to a different
  remote ticket.

## Local closure work (store-layer defense-in-depth, later session)

**law_held = TRUE for the scope named below.** A prior pass ("fix implemented" above)
closed the candidate-to-authority and replay-reauthorization gaps entirely at the
point of use (`ConsequenceBoundary.execute()`/`execute_admitted()`), and explicitly
left `ReceiptStore.save_prepared`/`save_final` performing zero validation of a
receipt's claimed `grant_id`, naming that `UNSUPPORTED` (deliberate scope decision,
not an oversight) so the store could remain "an intentionally dumb, append-only
persistence layer." This session adds a SECOND, INDEPENDENT layer directly at the
store, per this session's own task: real `grant_id` validation inside
`ReceiptStore.save_prepared`, opt-in via a new constructor-injected
`authority_broker: Optional[AuthorityBroker] = None` parameter (default `None`
preserves every existing caller byte-for-byte).

### What changed

- **`src/autofde_lab/sa2a/brce/receipts.py`** (modified):
  - `ReceiptStore.__init__` gained `authority_broker: Optional[AuthorityBroker] =
    None`.
  - New method `ReceiptStore._validate_grant_id(receipt)`: no-op when
    `authority_broker is None`; otherwise calls a fresh, real
    `AuthorityBroker.evaluate(ConsequenceRequest(actor_id=receipt.actor_id,
    action_iri=receipt.action_iri, target_resource=receipt.target_resource,
    grant_id=receipt.grant_id))` and raises a new typed exception,
    `ReceiptGrantValidationError` (carrying `.receipt`, `.refusal_code`, `.reason`),
    if `decision.authorized` is `False`.
  - `save_prepared` calls `_validate_grant_id` exactly once, for a genuinely NEW
    receipt (a repeated idempotency-token write with an identical digest still
    short-circuits before validation, matching existing idempotent-write semantics
    unchanged).
  - `save_final` is unchanged and documented as unchanged: `FinalReceipt`
    (`receipts.py` dataclass fields, read in full this session) carries no
    `grant_id` field at all, so there is no independent grant claim on a
    `FinalReceipt` for this defense to validate.
  - Named scope limitation (in the `ReceiptGrantValidationError` docstring, not
    silently mishandled): the check validates against directly-registered
    `AuthorityGrant` objects in the broker's real grant registry only (the exact
    `grant_id`-lookup path `AuthorityBroker.evaluate()` itself uses when
    `request.grant_id is not None`). A receipt whose `grant_id` is a synthetic
    ODRL-policy-permission id (the `"policy-grant-<policy>-<perm>"` string
    `AuthorityBroker.evaluate()` mints for a policy-permission match with no
    explicit registered grant) would be refused by this store-layer check if
    presented while a broker is configured. This does not affect any real call
    path today: grep confirms zero existing constructors of `ReceiptStore` or
    `DurableDiskReceiptStore` anywhere in `src/` or `tests/` pass
    `authority_broker` — this feature is additive and, before this session's own
    new test file, entirely unexercised.
- **`src/autofde_lab/sa2a/conformance/courts/consequence_court.py`** (modified,
  minimally): `DurableDiskReceiptStore.__init__` gained the same optional
  `authority_broker: Optional[AuthorityBroker] = None` parameter, forwarded to
  `super().__init__(authority_broker=authority_broker)`. All 13 existing call sites
  (grep, this session) construct it with only `store_dir` and are unaffected.

### Why `ConsequenceBoundary`'s own internal receipt store is unaffected

`ConsequenceBoundary.__init__` still does `self._receipt_store = receipt_store or
ReceiptStore()` — a plain, broker-less `ReceiptStore()` when no `receipt_store` is
passed, exactly as before. Even where a caller explicitly passes a
`DurableDiskReceiptStore` alongside a separate `authority_broker` argument to
`ConsequenceBoundary` itself (the pattern `test_afde_2604_fresh_mutations_
qualification.py`'s `_boundary()` helper uses, read this session), that store is
still constructed with the single positional `store_dir` argument only — so its own
`_authority_broker` stays `None` and this session's validation never fires inside
`ConsequenceBoundary.execute()`'s existing Step 4 `save_prepared` call. This is a
deliberate, additive, opt-in feature: nothing in `ConsequenceBoundary` itself was
changed to construct a broker-aware store automatically, per this session's own task
scope (`receipts.py`'s store layer specifically, not `boundary.py`'s existing
point-of-use fence, which a prior pass already closed).

### New test file

`tests/sa2a/conformance/test_afde_2604_receipt_store_grant_validation.py` — 7 real,
Chicago-style tests:

1. `test_in_memory_store_accepts_receipt_with_real_matching_grant` — (a), in-memory
   `ReceiptStore`.
2. `test_disk_store_accepts_receipt_with_real_matching_grant_and_writes_real_bytes`
   — (a), `DurableDiskReceiptStore`, asserts real bytes land on disk.
3. `test_in_memory_store_refuses_forged_grant_id_when_broker_configured` — (b),
   in-memory `ReceiptStore`, asserts `ReceiptGrantValidationError` with
   `refusal_code == REFUSED_NO_GRANT` and that the forged receipt never entered the
   store.
4. `test_disk_store_refuses_forged_grant_id_with_zero_disk_mutation` — (b),
   `DurableDiskReceiptStore`, asserts the refusal AND zero disk mutation (the forged
   receipt's `prep_*.json` file is never written, because `DurableDiskReceiptStore
   .save_prepared` calls `super().save_prepared(receipt)` — where the new
   validation raises — strictly before its own disk-write code runs).
5. `test_unregistered_grant_id_is_refused_not_a_lookup_error` — a `grant_id`
   referencing no registered grant at all is refused the same typed way (not a
   `KeyError`/lookup crash).
6. `test_in_memory_store_without_broker_behaves_exactly_as_before` — (c),
   `ReceiptStore()` (the pre-existing zero-argument construction) accepts the
   identical forged receipt with zero exception, exactly as before this session.
7. `test_disk_store_without_broker_behaves_exactly_as_before` — (c),
   `DurableDiskReceiptStore(store_dir)` (the pre-existing single-argument
   construction) accepts the identical forged receipt and durably writes it to
   disk, exactly as `test_mutation_cross_court_identity.py`'s Test 1 already pins.

`tests/sa2a/conformance/test_mutation_cross_court_identity.py` was read in full this
session and **not modified** — correctly: both its `store` fixtures construct
`DurableDiskReceiptStore(tmp_path / "receipts")` with no `authority_broker`, so this
session's opt-in validation never fires for it, and its Test 1 finding ("the store
durably accepts a grant_id claim the broker never authorized, with no cross-check")
remains true and unchanged, exactly as its own docstring already documented ("This
remains true after the fix -- deliberately"). Re-run this session, standalone: `2
passed` (see Evidence below).

### Evidence

**Zero-mock grep, run this session, over the new file**:

```
$ grep -n "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" \
    tests/sa2a/conformance/test_afde_2604_receipt_store_grant_validation.py
65:- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in this
```

The one match is the module docstring's own literal listing of the banned tokens
(documentation stating the discipline being followed) — zero matches in actual code.

**Required command, run this session, verbatim (stale-tmpdir cleanup noise from
`~/.cache/tmp/pytest-of-sac/garbage-*` — the same pre-existing, unrelated
environment condition already documented earlier in this file — omitted for
signal; exit code `0`)**:

```
$ .venv/bin/python -m pytest tests/sa2a/conformance/test_afde_2604_receipt_store_grant_validation.py \
    tests/sa2a/test_brce_replay.py tests/sa2a/conformance/test_court_replay.py \
    tests/sa2a/conformance/test_court_consequence.py -v
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
rootdir: /Users/sac/autofde-lab
configfile: pyproject.toml
plugins: langsmith-0.12.1, anyio-4.14.0, nbmake-1.5.5, cov-7.1.0, xdist-3.8.0, timeout-2.4.0, Faker-40.36.0, cases-3.10.1
collected 28 items

tests/sa2a/conformance/test_afde_2604_receipt_store_grant_validation.py . [  3%]
......                                                                   [ 25%]
tests/sa2a/test_brce_replay.py ........                                  [ 53%]
tests/sa2a/conformance/test_court_replay.py .......                      [ 78%]
tests/sa2a/conformance/test_court_consequence.py ......                  [100%]

============================== 28 passed in 0.69s ==============================
```

(This pytest configuration's `-v` flag renders per-file dot progress rather than
per-test names on this machine/config — a pre-existing display characteristic,
unrelated to this session's changes; the collected-item count (28), the dot stream
with zero `F`/`E` markers, and the `28 passed` / exit code `0` are the real,
sufficient pass evidence, matching this ticket's own established practice.)

**Full `tests/sa2a/` regression run, this session** (broader than the required
command, run for completeness per this repo's own discipline of checking the whole
directory, not just the named files):

```
$ .venv/bin/python -m pytest tests/sa2a/ -v
...
=================== 3 failed, 296 passed, 1 warning in 9.46s ===================
```

All 3 failures are in `tests/sa2a/conformance/test_afde_2604_fresh_mutations_
qualification.py` (`test_mutation_a_admission_content_not_bound_to_actuated_
action_target`, `test_mutation_b_replay_reauthorized_for_different_action_returns_
stale_receipt`, `test_mutation_c_execute_admitted_admission_gate_bypassed_on_
replay`) — a file this session did not create and did not modify (`git status
--porcelain` confirms it as pre-existing `??` untracked, added by an earlier,
independent qualification pass per its own module docstring: "written by an
independent qualification pass ... These are DELIBERATELY DIFFERENT mutations").
These three failures are **pre-existing, not introduced this session**, confirmed
by direct code-path reading: that file's `_boundary()` helper constructs its
`DurableDiskReceiptStore` with a single positional argument
(`DurableDiskReceiptStore(tmp_path / name / "receipts")`, no `authority_broker`),
so this session's new, opt-in validation is a structural no-op for every code path
in that file — `self._authority_broker` stays `None` inside that store regardless
of this session's change. The three failures document three separate, genuine,
already-known gaps in `ConsequenceBoundary.execute()`/`execute_admitted()`
(admission-content binding, cross-action idempotency-token identity, and
per-call admission re-checking) that are out of this session's scope (store-layer
`grant_id` validation only) and were never claimed closed by this ticket's prior
"fix implemented" section either — they are new findings from a different,
independent pass, named here honestly rather than silently absorbed into this
session's own pass/fail count. `test_mutation_cross_court_identity.py` (the file
named in this session's task) and every other test in `tests/sa2a/` pass; the
delta from the prior session's recorded `288 passed` baseline to this session's
`296 passed` + `3 failed` (`299` total, `+11`) reflects new test files added by
other, independent, untracked work already present in the working tree at this
session's start (per the git-status snapshot: multiple `??` entries under
`tests/sa2a/conformance/` predating this session), not a regression this session
introduced.

### Local standing, scoped (this session's addition)

- **"`ReceiptStore.save_prepared` independently validates a receipt's claimed
  `grant_id` against the real `AuthorityBroker` grant registry when a broker is
  configured"**: `ALIVE` — real pytest run this session, `28 passed`, exit code
  `0`; new file's tests 1-5 above.
- **"A `ReceiptStore`/`DurableDiskReceiptStore` constructed without a broker (the
  existing default and every current caller) is completely unaffected"**: `ALIVE`
  — real pytest run this session, new file's tests 6-7 above, plus
  `test_mutation_cross_court_identity.py` re-run standalone this session
  (`2 passed`), unmodified.
- **"This closes `ReceiptStore`'s store-layer gap for every grant_id shape,
  including ODRL-policy-derived grants"**: explicitly `UNSUPPORTED`, named honestly
  — this defense validates against directly-registered `AuthorityGrant` objects
  only; a synthetic `"policy-grant-..."` id would be refused by this check if ever
  presented to a broker-configured store, which no real call path does today (see
  `ReceiptGrantValidationError`'s docstring in `receipts.py`).
- **"`ConsequenceBoundary`'s own live execution path now benefits from this
  store-layer check by default"**: `UNSUPPORTED`, named honestly — `boundary.py`
  was not modified this session, and its internal receipt store (`self
  ._receipt_store = receipt_store or ReceiptStore()`) is still constructed
  broker-less by default; wiring a broker-aware store into `ConsequenceBoundary`'s
  own default construction was out of this session's task scope (store-layer
  validation as an independently addressable, defense-in-depth layer, not a
  boundary.py change).
- **Three pre-existing, unrelated failures in
  `test_afde_2604_fresh_mutations_qualification.py`**: named above, confirmed not
  caused by this session's changes, left exactly as found (fix-forward discipline:
  this session did not touch that file, per its own out-of-scope subject matter).
- **Overall ticket standing**: `PARTIAL_ALIVE`, refined further by this session's
  addition — the store-layer `grant_id` self-assertion gap named in this ticket's
  Gap (3) discussion and pinned by `test_mutation_cross_court_identity.py` Test 1
  now has a real, working, opt-in second layer of defense (`ALIVE` for the scope
  named above), while remaining explicitly `UNSUPPORTED` for ODRL-policy-derived
  grants and for `ConsequenceBoundary`'s own default (broker-less) internal store
  construction, both named rather than silently assumed closed.
