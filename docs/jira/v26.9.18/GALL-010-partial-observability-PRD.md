# PRD v26.9.18 — GALL-010: Partial Observability Planning

**Status:** DRAFT IMPLEMENTATION SPEC
**Release:** v26.9.18
**Repository:** `seanchatmangpt/autofde-lab`
**Owner:** autofde-lab
**Dependencies:** GALL-009 admitted observations where available
**Authority ceiling:** PLAN/SELECT only

## Product outcome

FOND/HDDL planning can operate over explicit belief/knowledge partitions, choose information-gathering actions, and refuse plans whose safety requires unobserved facts.

## Problem

Real environments are not fully observed. Treating missing values as false or guessed facts destroys the distinction between UNKNOWN and admitted state and leads to unsound plans.

## Functional requirements

1. Represent KNOWN_TRUE, KNOWN_FALSE and UNKNOWN separately in planning state.
2. Compile observation actions and information partitions into FOND/HDDL problem representation.
3. Never coerce UNKNOWN into convenient deterministic values.
4. Allow contingent policy branches keyed by future observations.
5. Expose confidence/provenance only as candidate evidence, not admitted facts.
6. Bind produced policy to observation projection and belief-state identity.

## Acceptance criteria

1. A case with missing load-bearing fact produces information-gathering/contingent plan rather than assuming the fact.
2. Mutation that collapses UNKNOWN to false/true fails court.
3. When observation arrives, policy transitions deterministically to correct branch.
4. Unsafe plan dependent on unresolved fact is refused.
5. Replay with same belief state and planner identity yields same bounded policy subject.

## Evidence product

The checkpoint MUST emit a content-addressed machine-readable receipt/artifact binding exact producer SHA, input/predecessor identities, executed court, falsifiers, outputs, standing and evidence ceiling. Source presence or prose is not standing.

## Non-functional requirements

- Deterministic identity for identical admitted inputs.
- Typed UNKNOWN/PARTIAL/REFUSED/BLOCKED states.
- No ambient authority or undeclared dependency.
- Exact-head subject fencing and replayable evidence.
- No promotion of observation, model output, parsing or configuration into stronger standing.

## Definition of done

FOND/HDDL planning can operate over explicit belief/knowledge partitions, choose information-gathering actions, and refuse plans whose safety requires unobserved facts.
