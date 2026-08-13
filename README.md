# AutoFDE Lab

AutoFDE Lab is the planner laboratory and governed execution proving ground for the AutoFDE ecosystem. It combines the inherited scikit-decide decision/planning substrate with planner federation, formal admission, GymAct world execution, verification, receipts, replay, and standing.

The canonical flow is:

```text
world -> observation -> planner federation -> admission -> intent -> GymAct -> brokered DO -> execution -> verification -> receipt -> replay -> standing
```

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

## Documentation

Current documentation is rooted in `docs/README.md`. Historical Markdown is archived separately so prior evidence remains auditable without competing with current doctrine.

## Provenance

AutoFDE Lab is forked from Airbus AI Research's scikit-decide. Upstream copyright and license provenance remain intact; see `NOTICE` and `LICENSE`.
