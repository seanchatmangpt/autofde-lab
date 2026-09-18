# Planner League

AutoFDE Lab treats its heterogeneous planner catalog as a **population**, not support code behind one privileged agent.

```text
Planner != Policy != Role != Agent
```

A policy is:

```text
Policy = Planner x Parameters x Objective x ObservationProjection x ActionProjection
```

An episode composes world, roles, policies, information partitions, and authority.

## Admission

Not every planner is valid for every role or world:

```text
Compatible(planner, role, world) -> ADMITTED | REFUSED(reason)
```

Only admitted combinations execute. Incompatibility is evidence and must not be hidden by coercing observations/actions into unsupported shapes.

## Cross-play

For each manufactured world, admitted planner-role combinations generate plan portfolios. GymAct executes bounded candidate trajectories. Receipts produce empirical payoffs rather than speculative rankings:

```text
M[(planner_i, role_a), (planner_j, role_b), world_k]
```

This supports portfolio routing, adversarial falsification, mixture selection, PSRO-style population growth, scheduling, and role-specific evaluation.

## LLM boundary

An LLM can compile ambiguity into typed problems, propose novelty, or explain evidence. It is not automatically the player, planner, policy, role, or authority source.

## Falsification

Refutation requires the same admitted subject and boundary. Failure in an adjacent world/role is new topology, not a refutation of an unrelated receipt.
