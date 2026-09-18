# AutoFDE Lab Project Contract

## Mission

Build a compositional laboratory in which heterogeneous decision/planning algorithms can be admitted into roles, exercised against bounded worlds, compared empirically, and handed downstream with replayable evidence.

## System object model

```text
Planner != Policy != Role != Agent

Policy =
  Planner
  x Parameters
  x Objective
  x ObservationProjection
  x ActionProjection

Episode =
  World
  x Roles
  x Policies
  x InformationPartitions
  x Authority
```

Compatibility is explicit:

```text
Compatible(planner, role, world) -> ADMITTED | REFUSED(reason)
```

Only admitted combinations execute.

## Required properties

- heterogeneous planner federation rather than one privileged solver;
- formal compatibility/admission before bounded execution;
- GymAct worlds for empirical validation;
- explicit authority envelopes;
- receipted transitions and replay evidence;
- ontology-backed capability claims;
- generated projections derived from canonical graph/template sources;
- typed refusal and transparent failure states;
- standing bounded to exact source, subject, configuration, toolchain, and environment.

## Architecture correspondence

Preserve this correspondence where applicable:

```text
graph -> query -> ggen -> formal admission -> runtime -> bounded transition -> receipt -> replay -> release
```

ggen renders. Formal admission establishes the allowed shape. Runtime acts only on admitted intent. Receipts bind what was actually observed.

## Non-goals

AutoFDE Lab does not manufacture production authority, treat an LLM response as an executable command, equate workflow definitions with successful runs, or rewrite historical evidence to make current claims stronger.

## Success criterion

A planner/role/world claim should be replayable from identified inputs and either reproduce its bounded evidence or fail with a typed, diagnosable transition.
