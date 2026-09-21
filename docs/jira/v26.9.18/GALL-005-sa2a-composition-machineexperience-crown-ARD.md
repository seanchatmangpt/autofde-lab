# ARD v26.9.18 — GALL-005: SA2A Composition / MachineExperience Crown

**Status:** DRAFT ARCHITECTURE SPEC
**Release:** v26.9.18
**Repository:** `seanchatmangpt/autofde-lab`
**Owner:** autofde-lab
**Dependencies:** GALL-001, GALL-002, GALL-003, GALL-004
**Authority ceiling:** planning/selection/qualification only

## Architectural objective

An immutable composition manifest turns verified upstream evidence into MachineExperience and a fresh KNOWN execution with zero equivalent exploratory inference.

The architecture follows the Chatman separation laws:

[
Received \neq Admitted,\quad Candidate \neq Authority,\quad SELECT \neq CONSTRUCT \neq DO
]

and every consequence/evidence claim is bounded by exact subject identity and replayable receipts.

## Load-bearing components

- `src/autofde_lab/sa2a/gall/composition.py` — immutable manifest
- `src/autofde_lab/sa2a/gall/receipt_admission.py` — upstream admission
- existing `MachineExperienceCompiler`
- existing CMCA/FOND-HDDL crown machinery
- `scripts/run_gall_composition_crown.py`
- `tests/sa2a/test_gall_composition_crown.py`

## Data / control flow

`Exact GALL-001..004 receipts -> manifest admission -> UNKNOWN selection/evidence -> MachineExperience compile -> fresh process -> KNOWN reflex -> crown receipt`

## Interfaces

- Input: four exact checkpoint receipts + composition manifest
- Output: manifest, MachineExperience, E1 receipt, E2 receipt, GALL-005 crown receipt
- Downstream: GALL-006

## Required invariants

1. Create content-addressed composition manifest binding exact repo SHAs and receipt digests for GALL-001..004 plus local planner/compiler/corpus identity.
2. Admit/refuse upstream receipts; never reconstruct missing evidence from source inspection.
3. Episode 1 may plan/explore only for UNKNOWN and compiles experience only after independent evidence passes.
4. Bind MachineExperience key to semantic class + exact composition digest.
5. Episode 2 runs in a new Python process with no live Episode-1 objects/handles.
6. Record frontier calls, LLM allocations, planner invocations, MachineExperience hits and reflex executions.
7. Qualified KNOWN reflex must positively execute while equivalent frontier/LLM calls are zero; planner calls zero where fully compiled out.
8. Cross-repo standing remains at most PARTIAL_ALIVE while Gate 11 is open.

## Failure and refusal boundaries

- Missing upstream receipt => BLOCKED
- Moved SHA/digest mismatch => REFUSED
- Observer evidence too weak => no compile
- Episode 2 requires E1 memory => FAIL
- Learned candidate requests authority => REFUSED

A refusal is a valid architectural result. The implementation MUST NOT add model inference, private state, ambient dependencies, alternate authority paths or hand-written generated projections merely to make a court green.

## Repository-native qualification court

- `pytest -q tests/agent/test_cmca_dogfood_crown.py`
- `pytest -q tests/planning/test_cmca_planning_probe.py`
- `pytest -q tests/sa2a/test_gall_composition_crown.py`
- `python scripts/run_cmca_dogfood_crown.py --json`
- `python scripts/run_gall_composition_crown.py --json`
- hosted exact-head workflow with persisted bundle

Each command is recorded with exact head SHA, relevant lock/toolchain identities, exit status and artifact digests. A later run against a different subject does not inherit this standing.

## Evidence contract

The checkpoint receipt MUST contain enough identity to let the next boundary validate:

- producer repository and exact SHA;
- semantic/manufacturer/runtime subject as applicable;
- predecessor receipt digests;
- court/falsifier identities;
- exact output artifact digests;
- standing and evidence ceiling.

## Security / authority

Authority is never inferred from capability, model output, successful parsing, observation, conformance, generated source or prior execution. Secrets and bearer credentials are never embedded into cross-repository evidence receipts; only opaque grant/principal identities needed for correlation are allowed.

## Definition of architectural closure

The architecture is closed only when the positive witness executes and every required negative witness is actually attempted against the exact subject. Configuration, source inspection or absence of a violation without an attempted falsifier is insufficient.
