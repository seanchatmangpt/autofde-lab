# AutoFDE Lab

AutoFDE Lab is the foundation layer of the **Chatman Ecosystem**'s Forward Deployment OS: the
canonical decision, planning, hypothesis, and integration control plane between admitted
operational state and candidate plans. See `FORWARD_DEPLOYMENT.md` for the portfolio role and
ownership boundaries this repository operates inside.

**It computes candidate plans. It does not actuate.** A planner selects; a broker authorizes;
an executor performs; a verifier evaluates. Nothing here carries ambient authority to change
the world, and nothing here is given receipt, admission, or actuation semantics — that path
runs through OpenClaw and the portfolio's `BRCE.DO` boundary, never directly from this repo.

It is forked from [Airbus scikit-decide](https://github.com/airbus/scikit-decide), an AI
framework for Reinforcement Learning, Automated Planning and Scheduling, and inherits its full
domain/solver catalog, C++ solver core, and API surface unchanged (`autofde_lab.*`, with a
deprecated `skdecide` compatibility alias — see `docs/migration/from-scikit-decide.md`).

This repository establishes **AutoFDE Lab technical standing only** — what the code in this
tree demonstrably does, evidenced by a test run in the current session (see
`.claude/rules/standing-law.md`). It establishes none of: AutoFDE product standing (a separate,
future repository — see `docs/autofde/EXPLORE.md`), organizational standing (accountable
customer acceptance), or legal standing (this repository confers none; see `NOTICE` and
`LICENSE`).

The original framework was initiated at [Airbus](https://www.airbus.com) AI Research and
notably received contributions through the [ANITI](https://aniti.univ-toulouse.fr/en/) and
[TUPLES](https://tuples.ai/) projects, and also from [ANU](https://www.anu.edu.au/). Renaming
this fork does not transfer that copyright — see `NOTICE`.

## What's new

**v26.9.28** — independent plan and formal-method admission courts:

- **Graphlaw plan-admission court** — `guarded_candidate(..., court=...)` in the fabric
  guardrails accepts an independent court callable backed by the published graphlaw WASM
  module; a typed `PlanRefused` (structured index/action/unmet N-Quads details) becomes
  `REFUSED_OUTPUT` while protocol faults re-raise. `src/autofde_lab/fabric/graphlaw_court.py`,
  merges `55266bde`, `12ab0552`.
- **TLA+ TLC court** — `python -m autofde_lab.iec tlc-court --model brce|mutant:<KIND> --out DIR`
  model-checks the BRCE reference and its mutants with the digest-pinned tla2tools 1.7.4
  (typed refusals `JAR_DIGEST_MISMATCH`, `UNBOUND_CONSTANT`); `AUTOFDE_TLC_REQUIRED=1` turns
  the toolchain-absent skip into a failure. `src/autofde_lab/iec/tlc_court.py`, merge `2df06f46`.

**v26.9.25** — the ALOOP autonomous-loop-courts cycle, per `docs/rfcs/RFC-ALOOP-v26.9.25.md`
(ALOOP-001 implemented at court `aloop-001/v26.9.25-r9`):

- **Doctrine boundary lab** — a boundary-respecting lab over the Fortune-5 twin:
  `python -m autofde_lab.simulation.doctrine_lab` runs and verifies a sealed doctrine
  matrix (seal key from `AUTOFDE_DOCTRINE_LAB_KEY`, hex ≥ 32 bytes); `verify_run`
  enforces authority NONE, ceiling ≤ CONSTRUCT and no selection independently of
  replay. `src/autofde_lab/simulation/doctrine_lab/`, merge `91678ab5`.
- **OSIRIS bounded companion control kernel** — typed companion kernel
  (`autofde_lab.companion`, `__all__` exports) with independent speech and action
  policy gates. `src/autofde_lab/companion/`, merges `631419d7`, `7208c041`.

**v26.9.1** — Two additive capabilities merged this cycle, per `docs/jira/v26.9.1/PLAN.md` (that plan's own
"Last Updated" section carries the full merge closure record):

- **Fortune-5 SAFe DfCM digital twin simulation** — a simulatable full SAFe backlog hierarchy
  (portfolios, value streams, ARTs, teams, epics/features/stories) for validating DfCM
  decision-making at Fortune-5 SAFe-portfolio scale. `src/autofde_lab/simulation/fortune5_safe/`,
  `docs/fortune5-safe-simulation.md`.
  PR [#94](https://github.com/seanchatmangpt/autofde-lab/pull/94), merge `2bf2871f`.
- **APS AutoFDE protocol semantic profile** — an RDF/OWL ontology profile with SHACL shape
  constraints giving cross-agent planning artifacts a verifiable, SHACL-constrained semantic
  contract, plus a PR-qualifying CI gate. `ontology/aps-autofde-profile.ttl`,
  `ontology/shapes/aps-autofde-profile.shacl.ttl`,
  `.github/workflows/aps-protocol-profile.yml`. PR
  [#95](https://github.com/seanchatmangpt/autofde-lab/pull/95), merge `d2242c39`.

Both verified this session with real, currently-passing commands (Chicago-style — real
collaborators, no mocks): `.venv/bin/python -m pytest tests/test_aps_protocol_profile_chicago.py
-v` → 5 passed; independent `pyshacl.validate()`
of the new ontology profile against its own shapes → `Conforms: True`.

## Documentation map

- `FORWARD_DEPLOYMENT.md` — this repository's role and ownership boundaries in the portfolio.
- `docs/STATUS.md` — the in-repo standing ledger (measured wins / recorded negatives / scoped
  work, per `.claude/rules/standing-law.md`).
- `docs/ecosystem-standing.md` — the cross-repository standing ledger.
- `docs/diataxis/README.md` — Diataxis-framework documentation (tutorial / how-to / reference /
  explanation) for individual capabilities, starting with the autonomic life-planning case
  study.
- `docs/jira/v26.9.1/PLAN.md` — the DMEDI plan and merge record for this cycle's two additive
  capabilities above.
- `docs/migration/from-scikit-decide.md` — what changed / didn't for anyone with existing code
  against `pip install scikit-decide`.
- `NOTICE` / `LICENSE` — provenance and legal terms; renaming this fork did not transfer
  upstream Airbus copyright.

Docs never establish standing on their own (`docs/CLAUDE.md`) — every "works" claim above
points at a real command and its real output, not prose alone.

## Core boundaries

- Planner, policy, role, and agent are distinct objects.
- SELECT, CONSTRUCT, and DO are distinct operations.
- Planner/model output, proofs, hooks, and generated files have no ambient execution authority.
- GymAct may execute bounded benchmark and rehearsal worlds when authority is explicitly admitted.
- Benchmark authority does not imply production authority.
- Irreversible DO requires a brokered path and receipt evidence.
- Acknowledgement, effect, verification, score, and standing are distinct evidence stages.

## Planner league

The planner catalog is treated as a population. A policy composes a planner, parameters, objective, observation projection, and action projection. A role supplies game semantics, constraints, information, cost, termination, and authority. Only compatible planner-role-world combinations are admitted for execution.

Cross-play inside manufactured worlds yields empirical payoff and receipt evidence rather than speculative planner rankings.

## Evidence vocabulary

Claims use `UNKNOWN`, `PARTIAL_ALIVE`, `ALIVE`, `BLOCKED`, `BUILD_BROKEN`, `UNSUPPORTED`, and typed `REFUSED`. `ALIVE` requires observed execution against the exact admitted subject and the required verifier.

## Source authority

Where the repository declares RDF/ontology, queries, and templates canonical, ggen renders projections from those sources. Generated files are not independent editing surfaces.

## Installation

```bash
pip install autofde-lab[all]
```

For development:

```bash
uv sync --extra=all -v
just test
```

Run the broader applicable suite before publishing a broad behavioral change:

```bash
just test-full
```

## Provenance

AutoFDE Lab is forked from Airbus AI Research's scikit-decide. Upstream copyright and license provenance remain intact; see `NOTICE` and `LICENSE`.
