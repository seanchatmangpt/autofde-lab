# GALL Checkpoint 005 — SA2A Composition / MachineExperience Crown

Status: DRAFT IMPLEMENTATION CONTRACT
Repository: `seanchatmangpt/autofde-lab`
Exact admitted base: `d5ac60ffde588a452ce8615f203971d17c69e31f`
Branch: `gall/checkpoint-005-composition-crown`
Owner surface: exact-subject composition manifest + bounded planning/selection + MachineExperience qualification/replay
Authority ceiling: planning/selection and qualification; this repository does not gain ambient external actuation authority

## Prior admitted evidence

PR #155 established a repository-local 8/8 `UNKNOWN -> verified MachineExperience -> KNOWN replay` crown at exact head `a72392f...`, including zero Episode-2 frontier calls. Current `master` is a different subject. That predecessor receipt is evidence to reuse, not standing to inherit.

## Objective

Turn the repo-local dogfood crown into a cross-repository composition court that consumes the earlier GALL checkpoint receipts without reimplementing their machinery.

Required graph:

`GALL-001 pack receipt -> GALL-002 manufacturer receipt -> GALL-003 command/authority receipt -> GALL-004 independent observer receipt -> MachineExperience qualification -> fresh KNOWN replay`

`autofde-lab` MUST NOT manufacture missing downstream evidence. A missing/blocked checkpoint remains missing/blocked in the composition.

## Exact-subject manifest

The checkpoint MUST introduce or emit one immutable composition manifest binding:

- ggen exact SHA + GALL-001 receipt digest;
- ggen_igniter exact SHA + GALL-002 receipt digest;
- ash_a2a exact SHA + GALL-003 receipt digest;
- beam4pm exact SHA + GALL-004 receipt digest;
- autofde-lab exact SHA;
- relevant solver/planner/toolchain/config identities;
- corpus/use-case identity;
- MachineExperience compiler identity.

No component may silently move to a newer branch head after admission.

## Episode 1 — UNKNOWN

For each qualified semantic case:

1. admit the exact composition manifest;
2. consume the upstream checkpoint receipts;
3. run the real repo-native planning/CMCA selection surface where required;
4. require independent evidence sufficient for the claimed result;
5. compile MachineExperience only from verified evidence;
6. bind the compiled rule to the exact semantic/composition identity.

## Episode 2 — KNOWN

Start from a fresh consumer process/state for the MachineExperience runtime:

- resolve the exact semantic key through compiled MachineExperience;
- execute the deterministic admitted reflex needed by this repository;
- frontier fallback is a hard falsifier;
- equivalent exploratory LLM allocation MUST be zero;
- where the planner has been compiled out of the reflex, planner invocations MUST be zero;
- evidence/contract identity MUST remain stable.

Zero model/planner calls because the reflex never executed is not a pass.

## Required crown predicates

- every required upstream GALL checkpoint exact subject is admitted;
- no stale/mismatched receipt is accepted;
- Episode 1 executes and qualifies the bounded corpus;
- MachineExperience rules compile only from verified evidence;
- Episode 2 executes the same semantic classes from fresh runtime state;
- Episode-2 frontier inference calls = 0 for qualified KNOWN classes;
- Episode-2 exploratory LLM allocation = 0 where deterministic admitted machinery is sufficient;
- replay evidence identity matches the admitted relation;
- all failures retain typed standing rather than collapsing to generic failure.

## Falsifiers

- change one upstream repo SHA while keeping its old receipt digest;
- replace one observer receipt with the actuator's self-report;
- compile MachineExperience from PARTIAL/UNKNOWN evidence;
- call frontier/LLM on a qualified KNOWN route;
- invoke a planner on a reflex whose qualified MachineExperience rule replaces equivalent planning;
- change semantic key/composition identity without invalidating the compiled rule;
- infer cross-repo ALIVE from predecessor repo-local evidence;
- let GraphSAGE or another learned candidate source self-promote beyond `CANDIDATE`;
- silently follow floating dependency branches.

## Verification ladder

1. composition-manifest schema/identity tests
2. receipt-admission/refusal tests
3. focused two-episode MachineExperience replay court
4. existing CMCA eight-use-case crown as a regression court where applicable
5. cross-repo composition court using exact pinned artifacts/receipts
6. hosted exact-head qualification with persisted receipt artifact

## Relationship to Chicago

This checkpoint can aggregate Chicago Gates 1-10 and Gate 12 evidence when supplied by the owning repos. It MUST NOT claim Gate 11 fresh-consumer closure until GALL-006 succeeds.

Therefore:

- successful GALL-005 without GALL-006 => `PARTIAL_ALIVE` for the cross-repo SA2A crown;
- successful GALL-005 + admitted successful GALL-006 against the same composition identity => eligible for the final Chicago standing issuer.

## Exclusions

- no direct external DO implementation in autofde-lab;
- no BRCE implementation copied into this repo;
- no promotion of learned candidate scores to authority;
- no merge/publication/deployment standing.

## Definition of done

One exact composition manifest closes the UNKNOWN-to-KNOWN two-episode loop using real upstream receipts, zero equivalent exploratory inference on KNOWN, deterministic evidence identity, and typed refusal of stale/mismatched subjects. The resulting receipt explicitly states whether Gate 11 remains open.

Standing on completion before GALL-006: at most `PARTIAL_ALIVE` for the cross-repo composition crown; repo-local bounded subjects may separately be `ALIVE`.

## 2026-09-18 semantic telemetry and consequence-profile propagation

When the composition uses the OTLP/Weaver observation path, the immutable GALL-005 manifest MUST preserve the stronger GALL-004 evidence decomposition.

At minimum, these predicates remain distinct:

- telemetry semantic validation;
- process / OCEL conformance;
- independent postcondition verification;
- consequence-profile observation;
- authority / DO standing.

The GALL-004 manifest edge MUST bind the exact beam4pm observer subject and the exact semantic-registry / Weaver validation receipt identities required by that observer. The stacked beam4pm contract is `seanchatmangpt/beam4pm#76`.

Repository-local semantic consequence profiling from autofde-lab PR #157 is complementary evidence. Typed additive measures such as BEAM reductions or later AtomVM energy/radio measures remain observational. They MUST NOT substitute for authority, independent postcondition proof, or the GALL-004 observer receipt.

MachineExperience compile-back MUST preserve the source evidence class and ceiling. A learned KNOWN path may reuse validated consequence knowledge without promoting that profile into stronger standing than its bound receipts support.

## Implementation specifics — refined 2026-09-18

Current docs-only PR head at this refinement: `aaa65ed5cf1f1718d7f59f1d03a56b67993dc2ba`.

### Verified predecessor surfaces from PR #155

Do not rewrite the repo-local crown. Extend these exact surfaces:

- `src/autofde_lab/agent/cmca_dogfood_crown.py`
  - existing eight-use-case Episode-1/Episode-2 dogfood crown.
- `src/autofde_lab/planning/cmca_probe.py`
  - CMCA planning/frontier probe used by the crown.
- `src/autofde_lab/sa2a/unknown/compilation.py`
  - `MachineExperienceCompiler`, the existing UNKNOWN -> compiled experience seam.
- `src/autofde_lab/planning/fond_hddl_product.py`
  - FOND/HDDL product machinery used by the operational crown.
- `src/autofde_lab/cmca/cascade.py`
  - bounded CMCA allocation.
- `src/autofde_lab/ocel/object_centric_conformance.py`
  - repo-local object-centric conformance used by UC-8.
- `scripts/run_cmca_dogfood_crown.py`
  - existing executable CLI/reporting surface.
- `tests/agent/test_cmca_dogfood_crown.py`
- `tests/planning/test_cmca_planning_probe.py`
- `.github/workflows/cmca-dogfood-crown.yml`
  - hosted persistence/receipt precedent.

PR #155 at exact head `a72392f...` remains predecessor evidence only.

### Smallest coherent new module set

Add a narrow cross-repo composition package rather than expanding `cmca_dogfood_crown.py` into a multi-repo loader.

Preferred files:

```text
src/autofde_lab/sa2a/gall/__init__.py
src/autofde_lab/sa2a/gall/composition.py
src/autofde_lab/sa2a/gall/receipt_admission.py
scripts/run_gall_composition_crown.py
tests/sa2a/test_gall_composition_crown.py
```

Responsibilities:

#### `composition.py`

Own one immutable `GALLCompositionManifest` representation with:

```text
schema
ggen {repo_sha, receipt_digest}
ggen_igniter {repo_sha, receipt_digest}
ash_a2a {repo_sha, receipt_digest}
beam4pm {repo_sha, receipt_digest}
autofde_lab {repo_sha}
planner_identity
cmca_identity
machine_experience_compiler_identity
corpus_identity
```

The manifest is content-addressed by canonical SHA-256.

No branch names count as identity.

#### `receipt_admission.py`

Parse each upstream receipt and verify:

- expected repository;
- exact SHA;
- exact digest;
- required standing for the claimed edge;
- semantic-subject continuity;
- predecessor linkage where present;
- no missing required evidence field.

This module does **admission**, not remote execution.

It MUST NOT fabricate a missing GALL-001..004 receipt from source inspection.

### Episode 1 execution contract

For the initial crown, preserve the eight PR-155 use-case classes as the regression corpus, but add at least one **cross-repo SA2A composition case** whose verified evidence includes the exact GALL-001..004 receipts.

The cross-repo case MUST prove:

1. composition manifest admitted;
2. repo-native planner/CMCA SELECT path executes only if the case is UNKNOWN;
3. external consequence evidence is consumed from GALL-003 rather than performed by autofde-lab;
4. independent postcondition/process evidence comes from GALL-004;
5. MachineExperience is compiled only after receipt admission succeeds;
6. the compiled experience binds the composition-manifest digest.

### Episode 2 fresh-runtime contract

Run Episode 2 in a new Python process, not merely a new object in the same test process.

The runner MUST receive only:

- immutable composition manifest;
- compiled MachineExperience artifact;
- explicitly admitted deterministic inputs.

It MUST NOT receive:

- live Episode-1 objects;
- an in-memory planner instance;
- cached frontier resolver closures;
- open producer handles;
- mutable singleton state.

For the qualified cross-repo semantic class, record counters:

```text
frontier_resolution_calls
llm_allocations
planner_invocations
machine_experience_hits
reflex_executions
```

Pass condition:

```text
machine_experience_hits >= 1
reflex_executions >= 1
frontier_resolution_calls == 0
llm_allocations == 0
planner_invocations == 0   # only where the compiled reflex replaces equivalent planning
```

### New acceptance tests

`tests/sa2a/test_gall_composition_crown.py` MUST include:

1. exact four-upstream-receipt manifest admission;
2. stale SHA with valid old receipt => refusal;
3. valid SHA with tampered receipt digest => refusal;
4. GALL-003 self-report substituted for GALL-004 observer receipt => refusal;
5. PARTIAL/UNKNOWN observer evidence cannot compile an ALIVE MachineExperience relation;
6. MachineExperience semantic key changes when composition identity changes;
7. fresh-process Episode 2 uses compiled experience;
8. qualified KNOWN route has zero frontier/LLM allocation;
9. planner counter remains zero where the reflex replaces planning;
10. GNN/GraphSAGE candidate input cannot self-promote beyond candidate standing.

### Exact acceptance commands

Use the repository's Python environment/tooling, then at minimum:

```bash
pytest -q tests/agent/test_cmca_dogfood_crown.py
pytest -q tests/planning/test_cmca_planning_probe.py
pytest -q tests/sa2a/test_gall_composition_crown.py
python scripts/run_cmca_dogfood_crown.py --json
python scripts/run_gall_composition_crown.py --json
```

Then trigger the hosted GALL composition workflow only after local exact-subject closure. Persist the manifest, MachineExperience artifact, stdout JSON, and crown receipt as hosted artifacts.

### GALL-005 output artifact

The crown emits one machine-readable bundle:

```text
gall-composition-manifest.json
machine-experience.json
episode-1-receipt.json
episode-2-receipt.json
gall-005-crown-receipt.json
```

The crown receipt MUST explicitly state:

```text
gates_1_10
gate_11 = OPEN | PASS
gate_12
cross_repo_standing
```

Before GALL-006, `gate_11 = OPEN` and cross-repo standing cannot exceed `PARTIAL_ALIVE`.

### Handoff to GALL-006

GALL-006 receives only the immutable released bundle above plus public consumer instructions.

It MUST NOT require access to the Python process that created the bundle.

### Stop conditions

Stop rather than filling gaps locally when:

- any GALL-001..004 receipt is absent;
- an upstream exact SHA moved;
- a receipt digest does not match the manifest;
- independent observer evidence is weaker than the requested MachineExperience standing;
- Episode 2 can only succeed using Episode-1 process state;
- a learned candidate source would need to be treated as authority.

GALL-005 is an **aggregator and cognition-retirement court**, not a place to reproduce missing manufacturer, actuation, or observer implementations.

## 2026-09-18 exact-head code review

Reviewed source subject: `2ef0bb511908fa099a1edb55ea3a85c0e570c36c`.

### Observed implementation

The repository-local composition machinery is already mature:

- `ExactSubject` is a frozen identity over exact repository SHAs, artifact digests, root manifest, semantic profile, court/falsifier/query revisions, and environment identity.
- `SubjectResolver` has typed fail-closed refusals for floating refs, missing digests, conflicting repository/artifact identities, and malformed manifest shapes.
- `CompositionReceipt` independently hashes the composition identity together with the specific Episode 1 / Episode 2 final-receipt and OCEL digests.
- Chicago source tests exercise digest sensitivity and end-to-end crown binding.
- `sa2a.release.fresh_consumer` already runs in a separate OS process over durable checkpoint/OCEL artifacts and independently re-derives several claims instead of trusting producer booleans.

These are source/test surfaces observed at the reviewed head, not newly executed evidence.

### Cross-repository gap

The reviewed composition types are generic enough to carry upstream GALL artifacts, but the current `CompositionReceipt` fields bind Episode 1 / Episode 2 evidence; they do not themselves require or verify typed GALL-001..004 receipt identities.

GALL-005 therefore still needs a release manifest schema/court that makes all upstream checkpoint subjects mandatory and independently verifies each upstream receipt before the composition can crown.

A generic `ArtifactRef` carrying a digest is not enough unless the court also proves what artifact class that digest represents and which exact repository subject produced it.

### OTel court is not exact-head crown evidence yet

The reviewed `.github/workflows/sa2a-mfg-otel-court.yml` has two named sibling-repository assumptions:

- `$HOME/wasm4pm-compat`;
- `$HOME/ggen-marketplace/packs/otel-weaver-ocel-pack`.

The workflow itself documents that a clean GitHub-hosted runner does not provide them. It also uses `otel/opentelemetry-collector-contrib:latest`, a floating runtime identity.

It runs a collector + instrumented runtime + OCEL accumulator/equivalence check, but it does not invoke Weaver Live-check.

Therefore this workflow cannot currently serve as exact-subject GALL-004/005 evidence on a clean hosted runner.

### Semantic consequence profiler subject boundary

The semantic consequence profiler exists in autofde-lab PR #157, but its `src/autofde_lab/sa2a/profiling/*` files are absent from this reviewed GALL-005 head. Treat PR #157 as external/staged evidence, not as a capability of the current GALL-005 subject.

Do not bind profiler standing into the composition crown until the exact composition manifest names the profiler subject or the implementation is integrated.

### Revised next action

1. define typed mandatory upstream checkpoint references for GALL-001..004;
2. independently verify their repository SHA + receipt digest + evidence class before crown construction;
3. replace sibling-path assumptions with exact, provisioned subjects or report `BLOCKED`;
4. pin OTel/Weaver runtime identities rather than `:latest`;
5. require the beam4pm GALL-004 Weaver/observer receipt as a distinct upstream predicate;
6. only then compile MachineExperience / KNOWN evidence from the closed composition.

### Review standing

- repository-local exact-subject/composition receipt machinery: `PARTIAL_ALIVE` by source inspection;
- clean hosted OTel court: `BLOCKED` by declared missing-sibling assumption unless provisioned;
- Weaver live-check in current head: `UNKNOWN`;
- cross-repository GALL-001..004 composition crown: `UNKNOWN`.

## Four-hour conversation synthesis — cognition, learning and cross-runtime composition, 2026-09-18

The last four hours clarify repository responsibility and prevent GALL-005 from swallowing the rest of the system.

### Repository responsibility

For this crown:

- **autofde-lab** = cognition, planning, learning, qualification, UNKNOWN -> MachineExperience -> KNOWN;
- **GymAct** = consequence runtime: admission/SHACL, reversible closure, authority, BRCE, receipts/replay, OCEL and runtime consequence handling;
- **XaaS** = persistent BEAM application/manufacturing/control plane: durable Run/Epoch scheduling, Ash/Reactor/Oban, delegation and persistent receipts.

GALL-005 composes evidence from those roles. It must not reimplement GymAct consequence execution or XaaS durable scheduling inside autofde-lab merely to make the crown self-contained.

### Learned candidate plane

autofde-lab PR #159 at exact head `e2909db1090a143ac7fcc8c2c8a8c8905f455db7` adds authority-fenced GraphSAGE candidate inference:

`canonical RDF -> feature projection -> learned score -> Standing.CANDIDATE -> normal SA2A admission`.

That is the template for GNN/ONNX integration in the crown. If a learned model influences selection, the exact composition must bind model identity, feature-projection identity, and relevant inference artifact as ordinary exact artifacts/evidence. The model does not become semantic authority.

A future "galaxy" of ONNX/ML models may therefore be SELECT machinery. The crown is valid only if every selected candidate still crosses the same formal admission, authority, consequence and independent-verification boundaries.

### Ticket graph joins the exact subject

When the release is driven by semantic GALL tickets, the admitted work-order graph digest is part of the exact composition evidence. Markdown/WBPR/Vision projections cannot substitute for that graph identity.

This makes the release crown answer both:

`what code/receipts were composed?`

and:

`what admitted work order required that composition?`

### Relationship to the broader GALL ladder

The newly discussed GNN checkpoints and GALL-015..032 full-autonomics checkpoints are downstream/orthogonal qualification surfaces, not silent prerequisites for GALL-005. They enter this crown only when the candidate manifest explicitly includes their exact subjects/receipts.

The eventual larger crown may prove:

`disturbance -> observation -> diagnosis -> verified plan -> authority -> DO -> postcondition -> MachineExperience -> equivalent KNOWN replay`.

GALL-005 remains the exact-subject composition/learning crown inside that larger loop.

### Framework exclusion

Jido, LangGraph, CrewAI and similar frameworks are competitive-intelligence specimens only. GALL-005 must not gain standing by importing their agent-loop state as a trusted planning or evidence substrate.
