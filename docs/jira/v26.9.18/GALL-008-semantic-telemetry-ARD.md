# ARD v26.9.18 — GALL-008: Semantic Telemetry

**Status:** DRAFT ARCHITECTURE SPEC
**Release:** v26.9.18
**Repository:** `seanchatmangpt/autofde-lab`
**Owner:** autofde-lab lead; beam4pm consumes observational output
**Dependencies:** GALL-003 consequence identity, GALL-004 observation model
**Authority ceiling:** OBSERVE only

## Architecture objective

A consequence can be profiled across AgentPProf/AgentSight-style runtime sampling, eBPF/OTel/OTLP and BEAM/edge measures while retaining exact semantic attribution and an observational evidence ceiling.

## Components

- semantic correlation envelope
- runtime profiler adapter(s) including AgentPProf/AgentSight integration point
- eBPF/eunomia/OTel adapter
- normalizer to semantic telemetry evidence
- artifact/receipt emitter

## Control/data flow

`GALL-003 consequence -> runtime/kernel/OTel observations -> identity correlation -> semantic telemetry normalization -> observational receipt -> beam4pm/GALL-004 or GALL-009 feedback`

## Invariants

1. Propagate opaque semantic subject, capability, command, receipt, role and runtime identities into supported telemetry carriers.
2. Bind profiler/kernel/runtime measurements to the exact consequence subject without leaking credentials or authority secrets.
3. Support additive resource measures where valid: CPU/reductions, memory, latency, energy/radio where available.
4. Produce canonical semantic telemetry artifact consumable by beam4pm/OCEL projection.
5. Telemetry validation or performance correlation never grants DO or postcondition standing.
6. Preserve source/tool version and sampling uncertainty.

## Failure/refusal boundaries

- Identity lost => UNATTRIBUTED/REFUSED
- Profiler unavailable => partial evidence only
- Authority secret observed => hard failure
- Sampling uncertainty omitted => evidence ceiling reduced

## Qualification court

- focused semantic-correlation tests
- real runtime/profile fixture
- negative identity-loss fixture
- secret-leakage scan
- integration export consumed by beam4pm test fixture

## Evidence boundary

Every PASS binds exact producer and predecessor identities. A changed SHA, mapping, model, lockfile, observation projection or runtime subject is a changed subject. A gate is PASS only from observed execution and its required falsifier, never from absence of evidence.

## Authority law

[
Received \neq Admitted,\quad Candidate \neq Authority,\quad SELECT \neq CONSTRUCT \neq DO
]

No component may gain authority merely because it generated, predicted, observed, validated, replayed or parsed something.

## Closure

Architectural closure requires the positive witness plus each named negative witness on the exact v26.9.18 subject.
