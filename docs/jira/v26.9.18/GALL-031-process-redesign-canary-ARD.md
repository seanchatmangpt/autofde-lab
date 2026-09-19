# ARD v26.9.18 — GALL-031: Process Redesign Canary

**Status:** DRAFT ARCHITECTURE SPEC  
**Release:** v26.9.18  
**Repository:** `seanchatmangpt/autofde-lab`  
**Owner:** autofde-lab lead; ex4pm models, ash_a2a actuates, beam4pm observes  
**Dependencies:** GALL-016 POWL, GALL-019 predictor, GALL-026..030 feedback/intervention  
**Authority ceiling:** PROPOSE/SELECT; canary DO delegated to GALL-030

## Architecture objective
Measured process inefficiency produces one or more candidate POWL redesigns, each is formally checked and falsified, one bounded canary is explicitly authorized, independently compared against baseline, and then either proposed for admission/promotion or rolled back.

## Components
- slow-horizon evidence bundle
- POWL redesign candidate generator
- formal validation/falsifier adapter
- DfCM redesign frontier
- canary envelope/planner
- GALL-030 intervention adapter
- beam4pm before/after comparator
- promotion/rollback candidate receipt

## Data/control flow
`Slow evidence -> candidate POWL redesigns -> formal/falsifier court -> SELECT canary -> explicit authority/DO -> independent OCEL/conformance/attribution -> compare baseline -> promotion candidate or rollback`

## Invariants
1. Require SLOW-horizon evidence from GALL-028 plus exact conformance/attribution/prediction evidence.
2. Generate redesign candidates as candidate POWL subjects; normative process law remains unchanged.
3. Run structural/formal validation through GALL-016 and relevant OCPQ/conformance/falsifier courts before selection.
4. Preserve multiple lawful alternatives under DfCM until evidence excludes them.
5. Construct a bounded canary envelope defining population/scope, duration/event budget, authority, rollback condition and success metrics.
6. Execute canary only through GALL-030 bounded intervention/authority path.
7. Observe canary independently via GALL-024/026/027 and compare with exact baseline evidence.
8. Promotion is a separate admission decision; `Prediction != Promotion`. Failed/ambiguous canary triggers rollback or more observation.

## Failure/refusal boundaries
- Evidence horizon insufficient => remain observation
- No lawful redesign => BLOCKED
- Canary authority missing => REFUSED
- Metrics ambiguous/no improvement => no promotion
- Rollback postcondition unverified => escalation

## Qualification court
- candidate POWL validation fixture
- falsifier-elimination fixture
- bounded-canary authority test
- baseline/canary independent comparison test
- prediction-not-promotion mutation test
- rollback witness

## Crown laws
[
Prediction \neq Promotion,\quad Agent \neq Authority,\quad Plan \neq Authority,\quad Proof \neq Authority
]

[
UNKNOWN \rightarrow VerifiedExperience \rightarrow KNOWN
]

is valid only when the first transition contains independent consequence evidence and the second transition positively executes from fresh state.

## Final standing
The composition runtime may emit evidence. It MUST NOT self-issue final cross-repository ALIVE; the released bundle is evaluated by the affidavit/standing court.
