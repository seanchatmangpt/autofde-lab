# ARD v26.9.18 — GALL-010: Partial Observability Planning

**Status:** DRAFT ARCHITECTURE SPEC
**Release:** v26.9.18
**Repository:** `seanchatmangpt/autofde-lab`
**Owner:** autofde-lab
**Dependencies:** GALL-009 admitted observations where available
**Authority ceiling:** PLAN/SELECT only

## Architecture objective

FOND/HDDL planning can operate over explicit belief/knowledge partitions, choose information-gathering actions, and refuse plans whose safety requires unobserved facts.

## Components

- belief-state/knowledge-partition model
- FOND problem compiler
- HDDL task/method representation
- observation action interface
- policy receipt with belief-state identity

## Control/data flow

`Admitted O* + UNKNOWN partitions -> FOND/HDDL compile -> contingent planning -> observation request -> state refinement -> SELECT candidate policy`

## Invariants

1. Represent KNOWN_TRUE, KNOWN_FALSE and UNKNOWN separately in planning state.
2. Compile observation actions and information partitions into FOND/HDDL problem representation.
3. Never coerce UNKNOWN into convenient deterministic values.
4. Allow contingent policy branches keyed by future observations.
5. Expose confidence/provenance only as candidate evidence, not admitted facts.
6. Bind produced policy to observation projection and belief-state identity.

## Failure/refusal boundaries

- Load-bearing unknown unresolved => BLOCKED/contingent only
- Observation source unavailable => policy retains uncertainty
- Model probability treated as fact => refusal
- Planner attempts DO => architecture violation

## Qualification court

- focused belief-state unit tests
- FOND/HDDL contingent planning fixture
- UNKNOWN-collapse mutation falsifier
- deterministic policy replay test

## Evidence boundary

Every PASS binds exact producer and predecessor identities. A changed SHA, mapping, model, lockfile, observation projection or runtime subject is a changed subject. A gate is PASS only from observed execution and its required falsifier, never from absence of evidence.

## Authority law

[
Received \neq Admitted,\quad Candidate \neq Authority,\quad SELECT \neq CONSTRUCT \neq DO
]

No component may gain authority merely because it generated, predicted, observed, validated, replayed or parsed something.

## Closure

Architectural closure requires the positive witness plus each named negative witness on the exact v26.9.18 subject.
