# AFDE-2606: local projection seam for MFW's recursive DME closure loop

- **Status**: OPEN
- **Severity**: Medium — nothing here is broken; this names a real, currently
  unaddressed composition gap between this repo's projection seam and a loop
  this repo does not own. Not High: per `.claude/rules/ecosystem-boundary.md`
  and `docs/ecosystem-standing.md` RP-6, closing the loop itself is explicitly
  not this repo's ownership, so this repo cannot be blocking on its own
  authority.
- **Standing** (per `.claude/rules/standing-law.md`, split per boundary —
  never one line for the whole ticket):
  - `fabric/pddl_engine.py` satisfying mfw's `classical` engine contract:
    `ALIVE` — real command run this session, see Evidence below.
  - `fabric/powl.py` projecting a plan to POWL2 Turtle: `ALIVE` — real
    command run this session, see Evidence below.
  - Any epoch/residual-obligation/recursion composition *at the
    `fabric/pddl_engine.py` + `fabric/powl.py` layer specifically*:
    `NOT_FOUND` — these two modules are single-shot (one domain/problem pair
    -> one plan -> one POWL document); grep and source-read this session
    found no `epoch`, `residual`, `descent`, or `recursi*` vocabulary
    anywhere in `src/autofde_lab/fabric/`.
  - A repository-wide recursive bootstrap controller (`Blocked -> spawn
    child -> manufacture -> verify -> admit -> resume`, the literal shape
    A2A-2606 asks MFW to close): `NOT_FOUND` locally, confirmed this
    session (`ls src/autofde_lab/fabric/recursive_controller.py` ->
    "No such file or directory"), and asserted absent on purpose by this
    repo's own regression test — see Evidence.
  - A narrower, differently-scoped local epoch/lineage mechanism
    (`agent/epoch.py`, `agent/replan.py`) and a reduced local
    admission/broker/replay prototype (`receipts/`): `ALIVE` for what they
    actually claim (session-scoped POWL-structural traversal; a documented
    ERRC-reduced reproduction of `mfw-pcp-broker`/`mfw-pcp-replay`), real
    tests run this session — see Evidence. Neither is wired to
    `fabric/pddl_engine.py`, confirmed this session by grep (zero hits).
  - `src/autofde_lab/sa2a/` (RFC-SA2A-001/002, a full local BRCE reference
    implementation: `admission/`, `authority/broker.py`, `brce/{boundary,
    receipts,replay}.py`): existence and stated scope confirmed by source
    read this session; its own conformance to A2A-2606's six laws is
    `UNKNOWN` — its test suite was not run against this ticket's specific
    laws this session, and it is a separate, much larger subsystem than the
    projection seam this ticket scopes. Named here as the most
    law-shaped in-repo candidate for a future falsifier pass, not claimed
    as evidence for this ticket.
  - Enterprise/organizational standing: not applicable to this ticket —
    this is a technical-standing-only document per
    `.claude/rules/fde-authority-boundary.md`.

- **Owning repo(s)**: this repo (`autofde-lab`) owns *only* the two real
  local seams named above (candidate-plan computation + POWL projection —
  `docs/ecosystem-standing.md` stages S3/S3b). It owns none of: the
  admitted-world bounded-epoch IR, the broker, the receipt/replay chain, or
  the recursive controller A2A-2606 asks for. Per `docs/ecosystem-standing.md`
  RP-6, ownership of the recursive controller itself is "genuinely undecided"
  across the portfolio, with `mfw` named the least-bad home (currently
  `BUILD_BROKEN`, RP-2) and both `scikit-decide`/`autofde-lab`
  ("planning must not authorize") and `ggen`
  (self-attestation circularity) explicitly ruled out as hosts.

- **Depends on**:
  - `A2A-2606` (upstream, `seanchatmangpt/ash_a2a`; owning repos
    `seanchatmangpt/ggen`, `seanchatmangpt/bcinr`) — the ticket this document
    is the local-scope equivalent of. Read in full this session from this
    session's own scratchpad copy, `ash_a2a_tickets/
    A2A-2606-mfw-recursive-dme-closure.md` (ephemeral session path, not
    cited verbatim here since it is not a stable reference).
  - `~/mfw`'s `mfw-planner`: `BUILD_BROKEN` per `docs/ecosystem-standing.md`
    RP-2 (not re-verified this session; cited from the standing ledger, not
    re-run — this document does not claim fresh evidence for a sibling repo
    it did not touch).
  - `~/bcinr`'s POWL executor: `PARTIAL_ALIVE`, symbolic, unwired to any
    actuating broker per `docs/ecosystem-standing.md` S3c/RP-7 (same
    caveat: cited from the ledger, not re-verified this session).
  - This repo's own `fabric/pddl_engine.py` and `fabric/powl.py`: `ALIVE`,
    re-verified this session (see Evidence).

## Problem

A2A-2606 asks MFW to close one recursive contract:
`admitted world -> bounded epoch -> SELECT -> projection -> execution
package -> receipt -> residual obligations -> next epoch | closure`, with
the claim that "the missing work is composition, not a new planner."

This repo is not a candidate to close that contract — `.claude/rules/
ecosystem-boundary.md` states plainly that this repo computes candidate
plans and projects them to POWL, nothing more, and that attaching receipt,
admission, or actuation semantics to anything here is exactly the erosion
`tests/ecosystem/` exists to catch. What this repo *is* is one real,
already-`ALIVE` producer that the remote loop's `SELECT -> projection` hop
depends on: `fabric/pddl_engine.py` computes the candidate plan (satisfying
mfw's `classical` external-engine contract, `mfw-planner/src/config.rs`),
and `fabric/powl.py` projects it into the POWL2 Turtle mfw's own SHACL
shapes (`~/mfw/mfw-planner/shapes/powl2.shacl.ttl`) can validate.

The real local problem, established by source-reading both modules in full
this session, is narrower than "the recursive loop is unclosed" (that is
already recorded, ecosystem-wide, as S7/`UNSUPPORTED` in
`docs/ecosystem-standing.md`, and is not this repo's finding to make). It is:

1. **Neither module has any notion of an epoch.** `solve_to_plan_file()`
   takes exactly one `(domain_path, problem_path)` pair and writes exactly
   one plan and, optionally, one POWL document. There is no parameter, no
   field on the emitted Turtle, and no docstring reference anywhere in
   `fabric/pddl_engine.py` or `fabric/powl.py` for a parent epoch, a
   residual-obligation set, or a descent/bound witness. If A2A-2606's loop
   is ever closed by `mfw`, this repo's projection output today gives that
   loop nothing to key a "child epoch" off of beyond content addressing
   the plan itself.
2. **The pieces that *do* exist locally under an "epoch" vocabulary
   (`agent/epoch.py`, `agent/replan.py`) are a different mechanism at a
   different layer**, and are not connected to `fabric/pddl_engine.py` at
   all (confirmed this session — zero references either direction). They
   advance a *POWL structural marking* within one fabric session, bounded by
   a per-traversal step budget (`powl/bounds.py::ExecutionBound`), not an
   admitted-world PDDL epoch chain with a cross-epoch descent measure.
3. **The local admission/broker/replay prototype (`receipts/`) that already
   exercises the mfw `classical`-engine contract *shape*
   (`planning/runner.py::run_engine`, `EngineConfig(role="classical", ...)`)
   does so against `tests/.../fake_engine.py`, never against this repo's own
   real `fabric/pddl_engine.py`** (confirmed this session — zero references
   either direction). The one real local falsification testbed capable of
   exercising "planner output stays candidate-only through an admit ->
   broker -> receipt -> replay circulation" has never actually been pointed
   at this repo's own real planner.

## Required change

Not "implement the recursive loop" — that remains out of this repo's
ownership per the boundary above, and forcing it in here would recreate the
exact self-attestation circularity `ecosystem-boundary.md` and
`docs/ecosystem-standing.md` RP-6 already rule out for the neighboring
candidates (planning must not authorize itself; a generator must not also
certify itself).

The locally-owned, locally-actionable change is composition-readiness of
the two real seams this repo already has, so that whichever repo eventually
closes A2A-2606 does not have to renegotiate this repo's contract:

1. Give `project_plan_to_powl()` (or a sibling function, additive — never
   change the existing SHACL-conformant shape mfw already validates against)
   an optional way to carry a caller-supplied parent-epoch identity and
   residual-obligation reference alongside `mfwp:plannerRun` — content-
   addressed like everything else in that module, refused rather than
   guessed when absent, exactly like `DigestUnavailable` already refuses
   rather than forging a digest.
2. Wire the existing local `receipts/` broker/replay testbed's
   `run_engine(EngineConfig(role="classical", ...))` path against the real
   `python -m autofde_lab.fabric.pddl_engine` invocation (today it only
   exercises `fake_engine.py`), so this repo has one real, in-repo,
   Chicago-style falsifier for "this repo's real planner output stays
   candidate-only through a full admit -> broker -> receipt -> replay
   circulation" — explicitly labelled, as `receipts/`'s own module
   docstrings already are, as a reduced local reproduction of mfw's
   pattern, never as ecosystem admission.
3. Do not touch `agent/epoch.py` / `agent/replan.py` to force-fit them onto
   PDDL epochs — they are a real, working, differently-scoped mechanism
   (POWL-structural, single-hop, session-bounded) and conflating them with
   an admitted-world epoch chain would be exactly the kind of "coerce an
   absence into whichever value is convenient" `.claude/rules/
   absence-is-not-evidence.md` forbids.

## Laws

A2A-2606 states six laws for the recursive contract itself. This repo does
not hold that contract, so most of them describe a system this repo is not
part of. Named individually, not force-fit:

1. *"Every child epoch references one parent epoch and one residual
   obligation set."* **Not this repo's law to satisfy** — no PDDL/mfw
   epoch chain exists here (see Standing). A structurally analogous, more
   narrowly scoped rule already holds one layer up, locally: every
   `DecisionEpoch.advanced()` produces a new, immutable epoch carrying
   `supersedes`/`preserves` back-references (`agent/epoch.py:113-126`), and
   `PreserveMap.redo` + `redo_justification` is a real local encoding of "the
   residual work the next hop must still account for, explicitly justified"
   (`agent/replan.py:326-339`). This is real and tested (see Evidence) but is
   a POWL-marking law, not a PDDL-epoch law — naming both together would be
   the analogy-before-equivalence-proof error `.claude/rules/
   criticism-discipline.md` rule 1 warns against, so they are kept separate
   here rather than presented as the same law satisfied twice.
2. *"Recursion requires an explicit descent measure."* **Not satisfied
   locally, precisely.** `powl/bounds.py::ExecutionBound` is, by its own
   docstring, "budget declarations only" — a per-epoch step ceiling
   (`max_activity_fires`/`max_node_visits`/`max_marking_states`) folded into
   that one epoch's content identity. It bounds how far a single epoch's
   traversal may go; it is not a measure that must strictly decrease across
   a *chain* of epochs, which is what a descent measure names. `agent/
   replan.py`'s single-hop-only rule (`NON_ADJACENT_EPOCH` /
   `SKD-AGENT-008`, refusing `to_epoch != from_epoch + 1`) is the closest
   real local analog — it bounds recursion depth to exactly one hop by
   refusal, rather than by a decreasing measure. `UNKNOWN` whether this
   satisfies the remote law's intent; not claimed as equivalent here.
3. *"A closed consequence horizon emits no successor epoch."* **Not this
   repo's law** — no successor-epoch emission exists here in any form
   (`NOT_FOUND`, see Problem #1).
4. *"Planner output remains candidate-only until the downstream admission
   boundary accepts it."* **This is the one law this repo's own tests
   already actively defend, and it is `ALIVE`.**
   `TestPlannerOutputIsCandidateNotActuation::
   test_engine_emits_no_receipt_and_claims_no_admission`
   (`tests/ecosystem/test_chatman_chain_chicago.py:453-481`) asserts by name
   that `fabric/pddl_engine.py` writes exactly the plan and POWL files it was
   asked for (no receipt artifact) and that the projected Turtle contains
   none of `"Admitted"`, `"admitted"`, `"ALIVE"`, `"receipt("`. Passed this
   session — see Evidence.
5. *"Receipt feedback cannot grant authority."* **Not this repo's law in
   the ecosystem sense** — this repo issues no receipts (law 4). The
   reduced local `receipts/` prototype enforces a structurally identical
   rule at its own (explicitly local, explicitly reduced) scope:
   `ColludingRoles` refuses at construction when the same object is wired
   as both actuator and verifier, because — per that module's own docstring
   — a single object in both roles "can lie about verification with nothing
   in `actuate`/`replay.verify` able to catch it" (`receipts/broker.py:
   43-48`). Real and tested (see Evidence), but explicitly a local
   reproduction, never claimed here as mfw's actual broker.
6. *"Identical admitted epoch + profile produces identical semantic identity
   and projection witness."* **Partially instantiated, one layer down.**
   `DecisionEpoch.create()` derives `epoch_id` as a `sha256` over
   `{session_id, index, model_sha256, bound_sha256, supersedes, preserves}`
   (`agent/epoch.py:60-91`) — identical inputs deterministically produce an
   identical epoch identity, tested (see Evidence). This is real content
   addressing at the POWL-epoch layer, not at an "admitted epoch + profile"
   layer this repo has no concept of.

## Chicago falsifiers

Same treatment — each of A2A-2606's five falsifiers, named as it actually
maps (or does not) onto real local evidence.

1. *"A closed plan terminates without manufacturing a successor epoch."*
   **N/A here** — nothing here manufactures a successor epoch to not-emit.
2. *"A non-descending residual loop is refused before recursive
   execution."* **N/A in the remote sense** (no admitted-world epoch chain
   exists locally). Real local analog: `validate_preserve_map()` refuses a
   non-adjacent epoch pair (`ReplanRefusal.NON_ADJACENT_EPOCH`) and refuses
   a redo without a written justification (`REDO_WITHOUT_JUSTIFICATION`) —
   tested this session (`tests/agent/test_replan_unit.py`, see Evidence).
3. *"A child epoch cannot change the parent's admitted ontology identity
   silently."* **N/A** — no admitted ontology identity flows between local
   epochs; `agent/epoch.py`'s epochs carry a POWL `model_sha256`, and
   `atom_labels()` exists specifically to let a caller check label
   preservation across a supersession, but nothing in this repo calls it as
   an enforced gate today (checked by source read; no caller found this
   session). This is a real gap worth naming precisely rather than silently
   passing over: the *primitive* exists, the *enforcement* does not.
4. *"Receipt feedback can alter observations/residuals but cannot mint
   authority."* Real local analog tested this session:
   `TestPlannerOutputIsCandidateNotActuation::
   test_engine_emits_no_receipt_and_claims_no_admission` (law 4, above) plus
   `receipts/broker.py`'s `ColludingRoles` refusal (law 5, above). Both
   `ALIVE` at their own local scope; see Evidence.
5. *"Replay of a prior epoch does not create a second DO."* Real local
   analog: `src/autofde_lab/receipts/replay.py::verify()` is documented as
   pure, offline, deterministic re-verification of an already-issued
   Open/Close certificate chain — "it does not re-run the original
   actuation" (module docstring, lines 1-13). Exercised by
   `receipts/tests/test_broker_receipt_replay.py`, 11 cases passed this
   session (see Evidence). This is the one falsifier with the most direct
   real local instantiation, at the reduced local scope stated throughout
   this document.

## Definition of done

Scoped to what this repo can actually close, not to A2A-2606's own
definition of done (which is `mfw`/`bcinr`'s to satisfy):

- `project_plan_to_powl()` (or a named sibling) can carry an optional,
  content-addressed parent-epoch / residual-obligation reference without
  breaking `TestPowlProjection`'s existing SHACL-conformance tests.
- The local `receipts/` broker/replay testbed has at least one Chicago-style
  test that drives `run_engine` against the real
  `python -m autofde_lab.fabric.pddl_engine` entry point (not
  `fake_engine.py`), asserting the same candidate-only properties
  `test_engine_emits_no_receipt_and_claims_no_admission` already asserts,
  end-to-end through the local admit -> broker -> receipt -> replay chain.
- `tests/ecosystem/test_recursive_bootstrap_controller_is_absent_across_
  ecosystem` stays red-by-absence (still asserting `NOT_FOUND`) unless and
  until a real recursive controller lands somewhere in the portfolio, per
  its own docstring's instruction to update `docs/ecosystem-standing.md`
  when that happens — this ticket's local changes must not touch that
  test's assertion.
- This document's own claims stay falsifiable: re-running the commands in
  Evidence below at a later commit and getting a different result is a
  finding against this ticket, not evidence to quietly revise it away.

## Evidence

All commands run this session, from `/Users/sac/autofde-lab`, HEAD
`f5727fa970c8fd1060e662bc9e963c484aa5ed14`, branch
`feat/semantic-model-manufacturing`. No source file was edited this session.

```text
$ ls src/autofde_lab/fabric/recursive_controller.py
ls: src/autofde_lab/fabric/recursive_controller.py: No such file or directory

$ grep -rln "pddl_engine" src/autofde_lab/planning src/autofde_lab/receipts
(no output -- zero matches)
```

```text
$ .venv/bin/python -m pytest tests/ecosystem/test_chatman_chain_chicago.py \
    tests/ecosystem/test_powl_roundtrip_chicago.py \
    tests/fabric/test_decision_result_to_plan_lines.py -v --tb=no
collected 42 items
tests/ecosystem/test_chatman_chain_chicago.py .......F...FF.....         [ 42%]
tests/ecosystem/test_powl_roundtrip_chicago.py .....................     [ 92%]
tests/fabric/test_decision_result_to_plan_lines.py ...                   [100%]
FAILED ...TestIndependentVerificationNotSelfAttestation::
  test_at_least_one_verifier_admits_the_receipt
FAILED ...TestOntologyIsGeneratedNotCurated::test_ontology_matches_live_registry_exactly
FAILED ...TestOntologyIsGeneratedNotCurated::test_ontology_covers_every_declared_kind
================= 3 failed, 39 passed, 232 warnings in 21.28s ==================
```

The 3 failures are pre-existing and unrelated to this ticket (no source was
edited this session, so nothing this document proposes could have caused
them): two are ontology drift for `HDDLDomain`/`HTNDomain` gated on the
missing optional `unified_planning` extra (a known `UNSUPPORTED`-class gap,
`.claude/rules/ecosystem-boundary.md`), and one is the independent-
verification stage that `tests/ecosystem/CLAUDE.md` invariant 4 already
documents as *deliberately* left red pending EV-1/RP-1. This includes real
passing coverage of `TestEngineSatisfiesMfwClassicalContract`,
`TestSilentWrongAnswerIsRefused`, `TestPowlProjection` (SHACL conformance,
BLAKE3 digest honesty, round-trip decode), `TestPlannerOutputIsCandidateNotActuation`
(law 4 above), and `test_recursive_bootstrap_controller_is_absent_across_ecosystem`.

```text
$ .venv/bin/python -m pytest tests/agent/test_session.py tests/agent/test_replan_unit.py \
    tests/agent/test_ledger.py src/autofde_lab/receipts/tests/test_broker_receipt_replay.py -v
collected 32 items
tests/agent/test_session.py ........                                     [ 25%]
tests/agent/test_replan_unit.py ....                                     [ 37%]
tests/agent/test_ledger.py ......                                        [ 56%]
src/autofde_lab/receipts/tests/test_broker_receipt_replay.py ........... [ 90%]
...                                                                      [100%]
======================== 32 passed, 3 warnings in 1.97s ========================
```

## Local closure work (this session)

Second agent, same session boundary as the rest of this ticket. `cd
/Users/sac/autofde-lab && pwd` confirmed `/Users/sac/autofde-lab` before any
other command. HEAD unchanged from the rest of this ticket:
`f5727fa970c8fd1060e662bc9e963c484aa5ed14`, branch
`feat/semantic-model-manufacturing`. Neither `fabric/pddl_engine.py` nor
`fabric/powl.py` was touched this pass — both read only, per this ticket's
own "Required change" item 1 caveat and the task's explicit instruction not
to patch either module.

**Scope discipline restated**: this closure work checks two of A2A-2606's
six laws (4 and 6) as they apply to this repo's real local projection seam
only — `fabric/pddl_engine.py::solve_to_plan_file()` and
`fabric/powl.py::project_plan_to_powl()`. It does not claim this repo closes
A2A-2606's recursive admitted-world epoch contract (laws 1, 2, 3, 5 in the
ecosystem sense remain out of this repo's ownership, exactly as the rest of
this ticket already states) and it exercises no `autofde_lab.sa2a` machinery
as ecosystem admission — `sa2a` is read/checked here only as "this repo's
own local candidate for admission machinery that the real projection path
must never reach into," per the task's own framing, not as mfw's broker.

- **Law 4** ("planner output remains candidate-only until the downstream
  admission boundary accepts it," scoped to this repo's projection seam
  specifically: no ambient writes beyond the explicit output path, and no
  reach into this repo's own `autofde_lab.sa2a` admission/authority/BRCE
  reference implementation): **`law_held: true`**, `ALIVE`. Three real,
  passing tests — one real source-content check, two runtime checks against
  a real `Astar.solve()` call on the real `tests/domains/python/
  pddl_domains/blocks/` fixture (the same fixture
  `tests/ecosystem/test_chatman_chain_chicago.py` uses).
- **Law 6** ("identical admitted input + profile produces identical
  projection identity," scoped to this repo's real projection function since
  no admitted-epoch/profile concept exists locally — see Problem #1 above):
  **`law_held: true`**, `ALIVE`. One real, passing test: two independent
  in-process `solve_to_plan_file()` calls against the identical real
  domain/problem fixture, in two separate output directories, produce
  byte-identical `.plan` and `.powl.ttl` output.
- **Gap found, named precisely rather than silently passed over**: this
  closure work does *not* establish law 6 across process boundaries (a
  second, independent Python interpreter/subprocess invocation) — both
  in-process calls share one `Astar` solver import, one PDDL parser import,
  and one interpreter-level hash-seed, so a source of nondeterminism that
  only appears across a fresh process (e.g. `PYTHONHASHSEED` variation
  feeding into any unordered-collection iteration inside the C++ backend)
  is `UNKNOWN`, not ruled out by this pass. The existing ecosystem crown
  test (`tests/ecosystem/test_chatman_chain_chicago.py::
  TestEngineSatisfiesMfwClassicalContract`) already runs the CLI as a real
  subprocess but does not currently assert cross-process byte-identity of
  two separate invocations against the same input — that remains open,
  precisely scoped, for a future pass; not claimed as closed here.

### Test file

`tests/fabric/test_afde_2606_projection_candidate_only_closure.py` (new file,
139 lines of test code across two classes,
`TestLaw4PlannerOutputStaysCandidateOnly` — 3 tests — and
`TestLaw6IdenticalInputProducesIdenticalProjectionIdentity` — 1 test).

### Command and real output

```text
$ .venv/bin/python -m pytest tests/fabric/test_afde_2606_projection_candidate_only_closure.py -v --tb=short -p no:cacheprovider
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
rootdir: /Users/sac/autofde-lab
configfile: pyproject.toml
collected 4 items

tests/fabric/test_afde_2606_projection_candidate_only_closure.py ....    [100%]

============================== 4 passed in 0.12s ===============================
```

Re-run combined with a neighboring, previously-passing fabric test as a
regression check (`tests/fabric/test_decision_result_to_plan_lines.py`, the
suite that already exercises `fabric/powl.py`'s decode/roundtrip path):

```text
$ .venv/bin/python -m pytest tests/fabric/test_decision_result_to_plan_lines.py tests/fabric/test_afde_2606_projection_candidate_only_closure.py -v --tb=short -p no:cacheprovider
collected 7 items

tests/fabric/test_decision_result_to_plan_lines.py ...                   [ 42%]
tests/fabric/test_afde_2606_projection_candidate_only_closure.py ....    [100%]

============================== 7 passed in 2.64s ===============================
```

(`-q` is pinned in `pyproject.toml`'s pytest `addopts`, so `-v` renders as
dot-per-test rather than one line per node id here — 4 dots for 4 collected
items, matching "collected 4 items" above, is the real per-test result; no
test in this file was skipped or deselected.)

### Chicago-style verification (zero-mock grep)

```text
$ grep -n "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" tests/fabric/test_afde_2606_projection_candidate_only_closure.py
40:``unittest.mock``/``Mock``/``MagicMock``/``patch``/``monkeypatch`` anywhere
```

The one match is the module docstring's own sentence *naming* the banned
tokens to state that none of them are used in this file — not a code usage.
Zero real occurrences of `unittest.mock`, `Mock(`, `MagicMock`, `patch(`, or
`monkeypatch` as executable code in this file. Real collaborators used
throughout: `autofde_lab.fabric.pddl_engine.solve_to_plan_file()` (which
constructs a real `PDDLDomain` from the real blocks-world PDDL fixture and
calls a real, registered `Astar` solver's `solve()`), and
`autofde_lab.fabric.powl.project_plan_to_powl()` (called internally by
`solve_to_plan_file()`, not stubbed).

### Pre-check evidence for the source-level law-4 assertion

Before writing the test, the same claim was verified directly against the
committed source (not just via the test, so the test's own correctness
could be cross-checked against an independent command):

```text
$ grep -n "autofde_lab.sa2a\|from autofde_lab import sa2a\|import sa2a" src/autofde_lab/fabric/pddl_engine.py src/autofde_lab/fabric/powl.py
(no output -- zero matches, grep exit code 1)
```

### Standing (this closure work only, `.claude/rules/standing-law.md`
vocabulary; does not restate or supersede the per-boundary Standing block at
the top of this ticket)

- `fabric/pddl_engine.py::solve_to_plan_file()` writes only its explicit
  output paths and never reaches `autofde_lab.sa2a` (source-level or
  runtime-side-effect): `ALIVE`.
- `fabric/powl.py::project_plan_to_powl()` never reaches `autofde_lab.sa2a`
  at the source level: `ALIVE`.
- Same-process determinism of `solve_to_plan_file()` given identical real
  domain/problem input: `ALIVE`.
- Cross-process determinism of the same claim (a fresh interpreter per run,
  not two calls in one process): `UNKNOWN` — named as a real gap above, not
  claimed either way.
- This test file's own zero-mock discipline: `ALIVE` (real grep, real
  output, above).
- Everything this ticket's own top-level Standing block already marks
  `NOT_FOUND` / `UNKNOWN` / out-of-ownership (the recursive bootstrap
  controller, laws 1/2/3/5 in the ecosystem sense, `sa2a`'s own conformance
  to A2A-2606) is **unchanged** by this closure work — this pass adds two
  narrowly-scoped `ALIVE` findings and one narrowly-scoped `UNKNOWN` gap; it
  does not touch, weaken, or attempt to close any of the ticket's existing
  `NOT_FOUND` findings.

This document's claims stay falsifiable per the ticket's own Definition of
done: re-running the two commands above at a later commit and getting a
different result is a finding against this section, not evidence to quietly
revise it away.

## Cross-process closure (this session)

Third agent, same session boundary as the rest of this ticket. `cd
/Users/sac/autofde-lab && pwd` confirmed `/Users/sac/autofde-lab` before any
other command. HEAD unchanged from the rest of this ticket:
`f5727fa970c8fd1060e662bc9e963c484aa5ed14`, branch
`feat/semantic-model-manufacturing`. Neither `fabric/pddl_engine.py` nor
`fabric/powl.py` was touched this pass -- both read only. This pass adds
exactly one new file (`tests/fabric/test_afde_2606_cross_process_determinism.py`)
and this doc section; nothing else changed.

**Scope**: this closure work resolves precisely the one named gap the prior
"Local closure work" section left open -- "this closure work does *not*
establish law 6 across process boundaries ... `UNKNOWN`, not ruled out by
this pass." It does not reopen or restate any other finding in this ticket.

### What was run

The real ~/mfw `classical` external-engine contract CLI entry point
(`python -m autofde_lab.fabric.pddl_engine <domain> <problem> <plan>
<powl>`), invoked as a genuinely separate OS-level `subprocess.run` call
twice -- fresh interpreter each time, no shared `sys.modules`, no shared
`Astar`/PDDL-parser import -- against the identical real
`tests/domains/python/pddl_domains/blocks/{domain.pddl,
probBLOCKS-3-0.pddl}` fixture already used throughout this ticket. Two
tests:

1. `test_two_fresh_subprocesses_default_env_produce_byte_identical_output`
   -- two subprocesses, no explicit `PYTHONHASHSEED` (each gets CPython's
   own independently-randomized per-process seed by default).
2. `test_two_fresh_subprocesses_different_hash_seeds_produce_byte_identical_output`
   -- two subprocesses with deliberately different explicit
   `PYTHONHASHSEED` values (`0` vs `424242`), targeting by name the exact
   candidate nondeterminism source the prior section named: "PYTHONHASHSEED
   variation feeding into any unordered-collection iteration inside the
   C++ backend."

Both tests assert the two real output `.plan` and `.powl.ttl` files are
byte-identical (`Path.read_text()` equality) **and** independently
hash-identical (real `hashlib.sha256` digest equality over the real file
bytes) -- two separate real checks, neither substituting for the other.

### Test file

`tests/fabric/test_afde_2606_cross_process_determinism.py` (new file, one
class `TestLaw6CrossProcessDeterminism`, 2 tests).

### Command and real output

```text
$ .venv/bin/python -m pytest tests/fabric/test_afde_2606_cross_process_determinism.py -v --tb=long -p no:cacheprovider
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
rootdir: /Users/sac/autofde-lab
configfile: pyproject.toml
plugins: langsmith-0.12.1, anyio-4.14.0, nbmake-1.5.5, cov-7.1.0, xdist-3.8.0, timeout-2.4.0, Faker-40.36.0, cases-3.10.1
collected 2 items

tests/fabric/test_afde_2606_cross_process_determinism.py ..              [100%]

============================== 2 passed in 1.71s ===============================
```

(Stderr for this run carried only pre-existing, unrelated pytest tmpdir
cleanup `PermissionError`/`OSError` warnings against a stale
`/Users/sac/.cache/tmp/pytest-of-sac/garbage-*` directory tree left by
other, unrelated test files' historical runs -- e.g.
`test_pack_source_fingerprint_c0`, `test_find_violations_ignores_n0`. None
of those names match either test in this file, they are emitted after this
file's own two tests already ran, and the run's exit code is 0. Not this
ticket's finding to carry further; noted here only so the raw output is not
misread as this file's own failure.)

Re-run combined with the existing in-process closure test, as a regression
check:

```text
$ .venv/bin/python -m pytest tests/fabric/test_afde_2606_cross_process_determinism.py tests/fabric/test_afde_2606_projection_candidate_only_closure.py -v --tb=short -p no:cacheprovider
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
rootdir: /Users/sac/autofde-lab
configfile: pyproject.toml
plugins: langsmith-0.12.1, anyio-4.14.0, nbmake-1.5.5, cov-7.1.0, xdist-3.8.0, timeout-2.4.0, Faker-40.36.0, cases-3.10.1
collected 6 items

tests/fabric/test_afde_2606_cross_process_determinism.py ..              [ 33%]
tests/fabric/test_afde_2606_projection_candidate_only_closure.py ....    [100%]

============================== 6 passed in 1.46s ===============================
```

### Chicago-style verification (zero-mock grep)

```text
$ grep -n "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" tests/fabric/test_afde_2606_cross_process_determinism.py
50:projection inside that subprocess). No ``unittest.mock``/``Mock``/
51:``MagicMock``/``patch``/``monkeypatch`` anywhere in this file -- verified by
```

Both matches are the module docstring's own sentence *naming* the banned
tokens to state that none are used as code in this file -- not a code
usage; grep exit code 0 (matches found are the docstring lines quoted
above, and no other line in the file matches). Real collaborators
throughout: a real OS subprocess running the real
`autofde_lab.fabric.pddl_engine` CLI end to end (real `Astar.solve()` and
real `project_plan_to_powl()` inside that subprocess), the same real blocks
fixture the rest of this ticket uses.

### Standing (this closure work only)

- Cross-process determinism of `solve_to_plan_file()`'s real subprocess
  contract, given identical real domain/problem input and two genuinely
  separate interpreters with default (independently-randomized) hash
  seeds: **`ALIVE`** -- real command run this session, output above,
  byte-identical and hash-identical `.plan`/`.powl.ttl` output confirmed.
- The same claim, narrowed to the specific named candidate nondeterminism
  source (`PYTHONHASHSEED` variation across processes) using two
  deliberately different explicit seed values: **`ALIVE`** -- same run,
  same evidence; no divergence observed under `PYTHONHASHSEED=0` vs
  `PYTHONHASHSEED=424242`.
- This closes the one gap the prior "Local closure work" section named as
  `UNKNOWN`. That section's own in-process Law 6 finding
  (`ALIVE`, same-process determinism) is unchanged and not restated here.
- Falsifier for this finding, stated precisely per this repo's
  `absence-is-not-evidence.md`: this result is `ALIVE` for the exact
  blocks-world domain/problem pair and the exact `Astar` solver path
  exercised here, in this environment (Python 3.13.9, this machine, this
  commit). It is not a general proof that no PDDL domain/problem pair or
  no future dependency version could ever introduce cross-process
  nondeterminism -- re-running this file at a later commit or against a
  different domain/problem pair and observing a byte mismatch would be a
  finding against this section, not evidence to quietly revise it away,
  exactly as the rest of this ticket's Evidence sections already commit to.
- Everything else in this ticket (all other Standing entries, all Laws,
  all Chicago falsifiers, the Definition of done) is **unchanged** by this
  closure work.
