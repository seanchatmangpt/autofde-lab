# RFC — Collective Skill Court Compiler v26.9.24

**Status:** FINAL_SPEC — v26.9.24
**Implementation standing:** exact-head court required

## Subject

Compile procedural knowledge into discriminating executable courts without granting the
source skill, generator, planner, or learned model ambient authority.

## Ownership

`ggen-marketplace` owns the reusable `collective-skill-court-pack` semantic contract.
`autofde-lab` owns exploration, court admission, candidate planning, and MachineExperience
compilation. GymAct remains the bounded executable-world layer. sJira owns WorkOrder identity,
acceptance predicates, falsifiers, dependencies, and evidence ceilings. SA2A carries powerless
candidates and the qualification lifecycle.

## Law

A court is admitted only when all of the following hold:

```text
oracle succeeds
AND no-op fails
AND every declared known-wrong mutation fails
AND authority ceiling == OBSERVE|SELECT|CONSTRUCT
AND grants_do_authority == false
```

The predicates are conjunctive constraints, not scalar reward terms. Task outcome, behavioral
fidelity, cost, latency, and compute may later be optimized inside the admitted feasible set;
standing and authority are never reward.

## Pipeline

```text
skill / runbook / receipt trace / standard
  -> provenance-bound SkillSource
  -> ggen-marketplace collective-skill-court-pack
  -> sJira WorkOrder
  -> Oracle / NOP / mutation observations
  -> court admission
  -> SA2A Candidate (authority=none)
  -> SA2A admission
  -> MachineExperience CANDIDATE
  -> independent qualification
  -> reusable known route only after existing SA2A qualification law
```

## Exact external subjects

- `ggen-marketplace` source base:
  `dafc1d45a02692ed3a18520627f5ad292c2b4b19`
- durable marketplace pack subject (ggen-marketplace PR #484 merge):
  `5eb71f7ed947f705a8d6b145cb9b0be82855d793`
  (pack tree `b9a530850ade6328c8347b1f32b72afd001048d5`, identical to the former staged head
  `02c13c46`, which is no longer pinned)
- upstream Skill2Env reference:
  `NVlabs/Skill2Env@9beb0b64a70290f862c8374bbef21f2ac88992ab`

These identities establish provenance only. They do not establish cross-repository execution
standing.

## First court

The first bounded source is `.claude/skills/chicago-domain-solver/SKILL.md`. The implementation
supports any provenance-bound source, but this RFC does not claim a generated court family has
run against GymAct yet.

## Falsifiers

The architecture is falsified if a source skill is treated as admitted truth merely because it
exists; if a no-op or known-wrong mutation can satisfy admission; if an SA2A Candidate receives
DO authority; if a newly compiled MachineExperience becomes ACTIVE without the existing
qualification path; or if an unpinned marketplace source is accepted as equivalent.

## Evidence ceiling

This change can establish repo-local source/test behavior once the exact-head workflow executes.
It does not establish GymAct execution, external environment fidelity, learned-policy quality,
production consequence, release standing, or cross-repository ALIVE standing.
