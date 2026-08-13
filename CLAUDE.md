# AutoFDE Lab — repository doctrine

AutoFDE Lab is the planner laboratory and governed benchmark-world proving ground for the AutoFDE ecosystem.

## Canonical flow

```text
parse -> route -> admit/refuse -> diagnose/repair -> construct -> bounded transition -> receipt -> replay -> standing
```

Planning and world transition are separated by explicit authority, not by pretending the laboratory never executes. GymAct may perform constrained benchmark/rehearsal transitions when the episode carries the required authority. That authority is scoped to the admitted subject and does not imply production authority.

## Invariants

- Preserve reversible possibilities before irreversible selection.
- Planner != policy != role != agent.
- SELECT != CONSTRUCT != DO.
- Raw input, planner/model output, proofs, hooks, and generated artifacts have no ambient execution authority.
- Hooks manufacture intents; they do not directly perform world transitions.
- A transition request may be typed `REFUSED`.
- Acknowledgement != observed effect != verification != score.
- `UNKNOWN` is not admitted fact; `UNSUPPORTED` is not `REFUSED`.
- `ALIVE` requires observed execution against the exact admitted subject and the required verifier.
- Generated projections are regenerated from canonical sources rather than hand-edited.

## Planner federation

Treat the planner catalog as a league. A planner supplies an algorithm. A role supplies objectives, observation/action projections, constraints, information partitions, costs, termination, and authority. A policy is an admitted composition of those elements.

An LLM can be a compiler or novelty oracle at a boundary; it is not automatically the planner, player, policy, role, or authority source.

## Evidence

Use `UNKNOWN`, `PARTIAL_ALIVE`, `ALIVE`, `BLOCKED`, `BUILD_BROKEN`, `UNSUPPORTED`, and typed `REFUSED`. Track observed, admitted, executed, changed, verified, inferred, refused, blocked, and unsupported separately.

Inspection is not execution. A workflow definition is not a successful run. A connector object is not a mounted tree. A named receipt is not automatically a valid receipt.

## Source authority

Respect ontology/ggen ownership. Where RDF, queries, and templates are canonical, ggen renders projections. Generated trees are not independent editing surfaces.

## Verification

Use the narrowest existing verifier first and expand as required: unit -> integration -> end-to-end -> chaos/stress/benchmark. Do not substitute queued CI, status metadata, mocks, or static inspection for requested execution evidence.

```bash
uv sync --extra=all -v
just test
```

Use `just test-full` when the branch's claims require the broader suite.

## Documentation authority

Current documentation starts at `docs/README.md`. The previous Markdown corpus is preserved under `archive/markdown/` as historical evidence. Historical wording remains auditable but is not present-tense authority.
