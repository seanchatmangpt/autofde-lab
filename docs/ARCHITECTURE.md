# Architecture

AutoFDE Lab is the planner laboratory and governed execution proving ground for the AutoFDE ecosystem.

## Foundational order

```text
Preserve -> Fence -> Calculus -> Exclusions -> Falsifier -> Extension -> Operationalization
```

The operational pipeline is:

```text
parse -> route -> admit/refuse -> diagnose/repair -> construct -> actuate -> receipt -> replay/hook -> standing
```

## Objects and morphisms

Primary objects include worlds, observations, planners, roles, policies, intents, authority envelopes, effects, verifiers, receipts, and replay capsules. Failed edges are topology information; they are not permission to bypass admission or declare unrelated graph regions failed.

## Three planes

**SELECT** searches, optimizes, routes, and chooses candidate policies. **CONSTRUCT** manufactures plans, intents, graphs, proofs, ggen projections, and test worlds. **DO** performs an admitted effect. SELECT and CONSTRUCT carry no ambient DO authority.

## Authority

Capability is not authority. Authority must be explicit, scoped to the admitted subject, and checked at the DO boundary. Raw input, planner/model output, proof objects, hooks, and generated files cannot self-grant execution authority. Hooks manufacture intents only.

## Planner plane

A planner supplies an algorithm. A role supplies objectives, projections, information partitions, constraints, cost, termination, and authority semantics. A policy is an admitted composition, not an alias for an agent.

## Construction plane

Where RDF/ontology, queries, and templates are canonical, ggen renders projections. A generated projection is not an independent editing surface.

## Execution plane

GymAct executes bounded world transitions. Brokered DO is the exclusive irreversible actuation path. The execution contract distinguishes acknowledgement, observed effect, verification, score, receipt, and standing.

## Production boundary

Lab execution proves only the exact admitted world/configuration captured by its evidence. Benchmark or rehearsal authority never implies production authority; production deployment requires a separate admission and authority envelope.
