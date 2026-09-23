# PRD v26.9.18 — GALL-011: Active Falsifier

**Status:** DRAFT IMPLEMENTATION SPEC
**Release:** v26.9.18
**Repository:** `seanchatmangpt/autofde-lab`
**Owner:** autofde-lab
**Dependencies:** GALL-010 belief-state semantics, existing GALL mutation corpus
**Authority ceiling:** TEST/QUALIFY only

## Product outcome
The system searches for invariant-breaking executions, minimizes any discovered counterexample, and promotes it into a permanent deterministic falsifier/corpus update without gaining operational authority.

## Problem
Static test suites only falsify what maintainers remembered to encode. Full autonomics requires a machine process that actively searches admitted state/action spaces for counterexamples without confusing a generated adversarial candidate with truth.

## Functional requirements
1. Represent release invariants as executable predicates over bounded state/action traces.
2. Generate adversarial candidates using symbolic search, mutation, property-based exploration or bounded learned heuristics.
3. Execute candidates only in admitted test/simulation environments.
4. Minimize a discovered failure to a stable MinimalCounterexample.
5. Emit `Defect -> MinimalCounterexample -> NewFalsifier -> PermanentCorpus -> CourtRevision` receipt chain.
6. Re-run the revised court and prove the original defect class is now rejected.
7. Generated adversarial candidates remain CANDIDATE until execution evidence confirms the defect.

## Acceptance criteria
1. At least one seeded invariant defect is found without hard-coding its exact failing trace.
2. Failure is minimized while preserving the violation.
3. New falsifier fails before repair and passes after repair/court revision.
4. No adversarial test action crosses production/real DO authority.
5. Same minimized counterexample replays deterministically.
6. No-finding run reports bounded search coverage rather than claiming absence of defects.

## Evidence product
Emit a content-addressed checkpoint artifact/receipt binding exact repository SHA, predecessor identities, inputs, courts/falsifiers, outputs, standing and evidence ceiling.

## Release rules
Source presence, configuration, hosted workflow definitions and model scores are not runtime standing. UNKNOWN, PARTIAL, REFUSED, BLOCKED and UNSUPPORTED remain typed. Changed identities are changed subjects.

## Definition of done
The system searches for invariant-breaking executions, minimizes any discovered counterexample, and promotes it into a permanent deterministic falsifier/corpus update without gaining operational authority.
