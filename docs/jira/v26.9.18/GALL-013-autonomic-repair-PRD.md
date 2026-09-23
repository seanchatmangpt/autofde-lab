# PRD v26.9.18 — GALL-013: Autonomic Repair

**Status:** DRAFT IMPLEMENTATION SPEC
**Release:** v26.9.18
**Repository:** `seanchatmangpt/autofde-lab`
**Owner:** autofde-lab lead; ash_a2a performs authorized DO; beam4pm verifies
**Dependencies:** GALL-003, GALL-004, GALL-008..012
**Authority ceiling:** PLAN/SELECT; repair DO delegated to ash_a2a

## Product outcome
A seeded fault or drift is detected, diagnosed, mapped to bounded repair alternatives, preflighted, authorized through ash_a2a, executed once, and independently verified as restored without autofde-lab acquiring DO authority.

## Problem
Detection without lawful recovery is monitoring, not autonomics. Conversely, automatic repair without explicit admission, preflight, authority and independent verification is unsafe actuation.

## Functional requirements
1. Admit fault/drift evidence and preserve uncertainty from GALL-008/009/010.
2. Generate multiple bounded repair candidates and preserve DfCM option geometry until exclusions apply.
3. Use GALL-012 predictor only as a candidate-ranking heuristic.
4. Preflight candidates against FOND/HDDL/constraints and GALL-011 falsifier corpus.
5. SELECT one repair without executing it locally.
6. Delegate exact repair capability + authority request to GALL-003 CommandBus.
7. Require GALL-004 independent postcondition/conformance evidence after repair.
8. Rollback/escalation remains explicit when postcondition is not verified.

## Acceptance criteria
1. Injected fault is detected from admitted evidence, not a hard-coded direct call.
2. At least two lawful repair alternatives exist before selection where fixture permits.
3. Unsafe repair candidate is eliminated by preflight/falsifier.
4. Selected repair crosses ash_a2a prepared-receipt authority boundary.
5. External repair consequence count is exactly one.
6. Independent observer proves restored state; actuator self-report alone cannot close ticket.
7. Failed verification results in rollback/escalation candidate, not invented success.

## Evidence product
Emit a content-addressed checkpoint artifact/receipt binding exact repository SHA, predecessor identities, inputs, courts/falsifiers, outputs, standing and evidence ceiling.

## Release rules
Source presence, configuration, hosted workflow definitions and model scores are not runtime standing. UNKNOWN, PARTIAL, REFUSED, BLOCKED and UNSUPPORTED remain typed. Changed identities are changed subjects.

## Definition of done
A seeded fault or drift is detected, diagnosed, mapped to bounded repair alternatives, preflighted, authorized through ash_a2a, executed once, and independently verified as restored without autofde-lab acquiring DO authority.
