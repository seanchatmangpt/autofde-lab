# PRD v26.9.18 — GALL-008: Semantic Telemetry

**Status:** DRAFT IMPLEMENTATION SPEC
**Release:** v26.9.18
**Repository:** `seanchatmangpt/autofde-lab`
**Owner:** autofde-lab lead; beam4pm consumes observational output
**Dependencies:** GALL-003 consequence identity, GALL-004 observation model
**Authority ceiling:** OBSERVE only

## Product outcome

A consequence can be profiled across AgentPProf/AgentSight-style runtime sampling, eBPF/OTel/OTLP and BEAM/edge measures while retaining exact semantic attribution and an observational evidence ceiling.

## Problem

Runtime telemetry is useful only if it preserves exact semantic/capability/receipt identity across processes and resource measurements. Generic profiling without attribution cannot feed lawful MachineExperience or process conformance.

## Functional requirements

1. Propagate opaque semantic subject, capability, command, receipt, role and runtime identities into supported telemetry carriers.
2. Bind profiler/kernel/runtime measurements to the exact consequence subject without leaking credentials or authority secrets.
3. Support additive resource measures where valid: CPU/reductions, memory, latency, energy/radio where available.
4. Produce canonical semantic telemetry artifact consumable by beam4pm/OCEL projection.
5. Telemetry validation or performance correlation never grants DO or postcondition standing.
6. Preserve source/tool version and sampling uncertainty.

## Acceptance criteria

1. Same consequence identity is correlated across at least two runtime observation layers.
2. Dropping/changing capability or receipt identity causes refusal/unattributed result rather than silent join.
3. Credentials/authority tokens are absent from telemetry artifact.
4. Additive measurements reconcile within declared measurement semantics.
5. Artifact is deterministic in schema/identity for same captured evidence while measurements retain their observed values.

## Evidence product

The checkpoint MUST emit a content-addressed machine-readable receipt/artifact binding exact producer SHA, input/predecessor identities, executed court, falsifiers, outputs, standing and evidence ceiling. Source presence or prose is not standing.

## Non-functional requirements

- Deterministic identity for identical admitted inputs.
- Typed UNKNOWN/PARTIAL/REFUSED/BLOCKED states.
- No ambient authority or undeclared dependency.
- Exact-head subject fencing and replayable evidence.
- No promotion of observation, model output, parsing or configuration into stronger standing.

## Definition of done

A consequence can be profiled across AgentPProf/AgentSight-style runtime sampling, eBPF/OTel/OTLP and BEAM/edge measures while retaining exact semantic attribution and an observational evidence ceiling.
