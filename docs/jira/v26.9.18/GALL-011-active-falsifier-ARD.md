# ARD v26.9.18 — GALL-011: Active Falsifier

**Status:** DRAFT ARCHITECTURE SPEC
**Release:** v26.9.18
**Repository:** `seanchatmangpt/autofde-lab`
**Owner:** autofde-lab
**Dependencies:** GALL-010 belief-state semantics, existing GALL mutation corpus
**Authority ceiling:** TEST/QUALIFY only

## Architecture objective
The system searches for invariant-breaking executions, minimizes any discovered counterexample, and promotes it into a permanent deterministic falsifier/corpus update without gaining operational authority.

## Components
- invariant registry
- bounded adversarial candidate generator
- sandbox/simulation executor
- counterexample minimizer
- permanent corpus writer/receipt emitter
- court-revision runner

## Data/control flow
`Invariant + bounded world -> adversarial candidates -> sandbox execution -> violation witness -> minimization -> permanent falsifier -> revised court`

## Invariants
1. Represent release invariants as executable predicates over bounded state/action traces.
2. Generate adversarial candidates using symbolic search, mutation, property-based exploration or bounded learned heuristics.
3. Execute candidates only in admitted test/simulation environments.
4. Minimize a discovered failure to a stable MinimalCounterexample.
5. Emit `Defect -> MinimalCounterexample -> NewFalsifier -> PermanentCorpus -> CourtRevision` receipt chain.
6. Re-run the revised court and prove the original defect class is now rejected.
7. Generated adversarial candidates remain CANDIDATE until execution evidence confirms the defect.

## Failure/refusal boundaries
- Search budget exhausted => UNKNOWN/no-finding, not PASS
- Candidate cannot execute safely => REFUSED
- Counterexample cannot replay => not admitted to permanent corpus
- Production authority required => BLOCKED

## Qualification court
- seeded mutation/property test
- counterexample minimization test
- permanent corpus replay test
- court-revision regression test

## Standing law
[
Observed \neq Admitted,\quad Prediction \neq Fact,\quad Candidate \neq Authority,\quad SELECT \neq DO
]

PASS requires exact-subject positive execution plus the required negative witnesses. No missing layer may be synthesized in this repository merely to satisfy the crown.
