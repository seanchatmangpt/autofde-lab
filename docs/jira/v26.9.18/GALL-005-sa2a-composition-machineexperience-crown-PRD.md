# PRD v26.9.18 — GALL-005: SA2A Composition / MachineExperience Crown

**Status:** DRAFT IMPLEMENTATION SPEC
**Release:** v26.9.18
**Repository:** `seanchatmangpt/autofde-lab`
**Owner:** autofde-lab
**Dependencies:** GALL-001, GALL-002, GALL-003, GALL-004
**Authority ceiling:** planning/selection/qualification only

## Product thesis

An immutable composition manifest turns verified upstream evidence into MachineExperience and a fresh KNOWN execution with zero equivalent exploratory inference.

## Problem

The repository-local CMCA crown proved UNKNOWN→MachineExperience→KNOWN on one exact subject, but cross-repository SA2A needs immutable upstream receipts and must not inherit standing from historical SHAs or fabricate missing execution evidence.

## User / consumer

The primary consumer is another machine boundary in the GALL chain. Human maintainers need the same artifact to be inspectable, falsifiable and executable through repository-native courts. No downstream consumer is allowed to infer stronger standing than this checkpoint emits.

## Required product behavior

1. Create content-addressed composition manifest binding exact repo SHAs and receipt digests for GALL-001..004 plus local planner/compiler/corpus identity.
2. Admit/refuse upstream receipts; never reconstruct missing evidence from source inspection.
3. Episode 1 may plan/explore only for UNKNOWN and compiles experience only after independent evidence passes.
4. Bind MachineExperience key to semantic class + exact composition digest.
5. Episode 2 runs in a new Python process with no live Episode-1 objects/handles.
6. Record frontier calls, LLM allocations, planner invocations, MachineExperience hits and reflex executions.
7. Qualified KNOWN reflex must positively execute while equivalent frontier/LLM calls are zero; planner calls zero where fully compiled out.
8. Cross-repo standing remains at most PARTIAL_ALIVE while Gate 11 is open.

## Acceptance criteria

1. All four exact upstream receipts admit against immutable manifest.
2. Stale SHA/old receipt, tampered digest and self-report substituted for observer receipt are refused.
3. PARTIAL/UNKNOWN evidence cannot compile stronger MachineExperience standing.
4. Fresh Episode 2 executes compiled reflex with MachineExperience hit >=1 and reflex execution >=1.
5. Frontier and LLM allocation counters are zero on qualified KNOWN case.
6. Planner counter is zero where equivalent planning was compiled out.
7. Output bundle explicitly reports Gate 11 OPEN until GALL-006.

## Product outputs

The implementation MUST emit a machine-readable, content-addressed checkpoint artifact/receipt that binds the exact subject, evidence ceiling, falsifiers attempted, commands/courts executed and resulting standing. Prose documentation is explanatory only and cannot confer standing.

## Success metrics

- 100% upstream edges exact-SHA/digest bound
- 0 frontier calls on qualified KNOWN replay
- 0 MachineExperience rules compiled from insufficient evidence

## Non-goals

- Direct external DO
- Copy of BRCE/CommandBus
- Learned model authority
- Gate 11 self-claim

## Release semantics

- A configured workflow is not execution evidence.
- Source presence is not runtime standing.
- Local PASS, hosted PASS, runtime standing, merge and publication remain separate evidence classes.
- Any changed base/head SHA is a changed subject unless explicitly re-admitted.
- UNKNOWN/PARTIAL/REFUSED/BLOCKED states are preserved rather than collapsed into generic failure.

## Definition of done

An immutable composition manifest turns verified upstream evidence into MachineExperience and a fresh KNOWN execution with zero equivalent exploratory inference.

The exact v26.9.18 subject earns only the bounded standing proven by its repository-native court. No cross-repository promotion is implied.
