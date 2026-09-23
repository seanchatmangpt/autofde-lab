# ARD v26.9.18 — GALL-013: Autonomic Repair

**Status:** DRAFT ARCHITECTURE SPEC
**Release:** v26.9.18
**Repository:** `seanchatmangpt/autofde-lab`
**Owner:** autofde-lab lead; ash_a2a performs authorized DO; beam4pm verifies
**Dependencies:** GALL-003, GALL-004, GALL-008..012
**Authority ceiling:** PLAN/SELECT; repair DO delegated to ash_a2a

## Architecture objective
A seeded fault or drift is detected, diagnosed, mapped to bounded repair alternatives, preflighted, authorized through ash_a2a, executed once, and independently verified as restored without autofde-lab acquiring DO authority.

## Components
- fault admission adapter
- diagnosis/causal candidate builder
- DfCM repair frontier
- FOND/HDDL preflight
- repair selection envelope
- ash_a2a capability/authority adapter
- beam4pm independent recovery verifier

## Data/control flow
`Observed fault -> admitted defect subject -> diagnosis -> repair candidates -> falsifier/preflight -> SELECT -> GALL-003 authorized DO -> GALL-004 independent verify -> restored/refused/escalate`

## Invariants
1. Admit fault/drift evidence and preserve uncertainty from GALL-008/009/010.
2. Generate multiple bounded repair candidates and preserve DfCM option geometry until exclusions apply.
3. Use GALL-012 predictor only as a candidate-ranking heuristic.
4. Preflight candidates against FOND/HDDL/constraints and GALL-011 falsifier corpus.
5. SELECT one repair without executing it locally.
6. Delegate exact repair capability + authority request to GALL-003 CommandBus.
7. Require GALL-004 independent postcondition/conformance evidence after repair.
8. Rollback/escalation remains explicit when postcondition is not verified.

## Failure/refusal boundaries
- Diagnosis underdetermined => UNKNOWN/observe more
- No lawful repair => BLOCKED/escalate
- Authority missing => REFUSED before DO
- Postcondition not restored => no success; rollback/escalation

## Qualification court
- seeded fault end-to-end fixture
- unsafe repair falsifier
- authority refusal witness
- single-DO recovery witness
- independent postcondition witness

## Standing law
[
Observed \neq Admitted,\quad Prediction \neq Fact,\quad Candidate \neq Authority,\quad SELECT \neq DO
]

PASS requires exact-subject positive execution plus the required negative witnesses. No missing layer may be synthesized in this repository merely to satisfy the crown.
