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
