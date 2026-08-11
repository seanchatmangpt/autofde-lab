# Van der Aalst-style OCEL/process-mining audit — 2026-08-11

5 parallel Explore agents (`mcp__lumen__semantic_search`-first) audited
this repo across van der Aalst's own analytical dimensions: process
discovery completeness, conformance checking coverage, object-centric data
integrity, decision-mining/enhancement wiring, predictive monitoring.

## Closed this session, real and OCEL-v2-validated

1. **`build_level4_ocel` silently persisted an unvalidated, structurally
   invalid OCEL log to disk.** Agent 3's audit found `OcelLog.validate()`
   was never called anywhere in `build_level4_ocel`'s own call chain, and
   its real production caller (`_persist_level4_ocel`,
   `hub/domain/gym_procedure/crown_reconstruct.py`) wrote
   `built.log.to_ocel2_json()` straight to disk unchecked. Adding the real
   `.validate()` call surfaced a genuine, pre-existing latent bug: two
   independent loops constructing `PostconditionObservation` objects had
   **zero deduplication guard** — a real receipt/goal-consequence pair
   sharing one `verification_id` (a legitimate, real case) silently
   double-declared the same object id, which `OcelLog.validate()`'s
   `DUPLICATE_ENTITY_ID` law (OCPQ Definition 2, law 3) now catches. Fixed
   with one shared `seen_postcondition_ids` set threaded through both
   loops; `.validate()` now runs for real before every return.
2. **`execute_with_ocel` had no `max_workers`/`context` passthrough**,
   which is why 4 real, `validate_model`-admitted, concurrent POWL
   executions (Agent 1's finding: `planner_federation_ensemble.py`,
   `breed_ensemble.py`, `breed_ensemble_loop.py`, `gymact_dspy_react.py`)
   produced zero OCEL trace — wiring them in would have silently dropped
   their real concurrency. Extended `execute_with_ocel` (additive,
   backward-compatible: existing 5 tests unaffected) and wired
   `planner_federation_ensemble.federate_concurrently`'s new, optional
   `recorder` parameter through it — real OCEL 2.0 events now produced for
   concurrent PDDL solver federation, validated by
   `check_object_centric_conformance` in a new test:
   `all_conform=True`, `overall_fitness=1.0`.

## A second, real gap the first fix unmasked

Fixing the `PostconditionObservation` duplicate-id bug turned 32 real test
**errors** (an `OcelError` exception bubbling up through log construction)
into 35 passes and exactly **1 real, honest failure**:
`tests/ecosystem/test_producer_witness_chicago.py::test_a_fresh_verifier_reconstructs_the_whole_chain`
— `VERDICT: UNKNOWN:CHAIN_INCOMPLETE:replay->receipt` ("no Replay binds a
receipt that participates in the receipt DAG"). This is a genuinely
separate, real, pre-existing gap the duplicate-id crash was previously
masking (by preventing the log from ever being constructed far enough to
reach this check) — not a regression introduced by this session's fix, and
not attempted further this session given the time already spent
reproducing it (a real ~21-minute subprocess-trial test run). Named here,
not silently dropped, per this repo's own discipline.

## Real, closeable gaps found, not yet closed (named, not silently dropped)

- `breed_ensemble.py`, `breed_ensemble_loop.py`, `gymact_dspy_react.py`:
  same real gap as `planner_federation_ensemble.py` had — real admitted
  POWL executions, zero OCEL trace. The `execute_with_ocel`
  `max_workers`/`context` extension built this session makes wiring these
  in mechanical follow-on work, not yet done.
- `OcelSessionRecorder` (MCP instrumentation) and
  `receipts/ocel_adapter.py::trajectory_to_ocel_log`: never run through
  either real conformance mechanism (`check_object_centric_conformance`
  or the older token-replay `level4_process_fitness.py` path).
  `trajectory_to_ocel_log` additionally constructs an entirely different,
  same-named `OcelLog` type from `reasoning.wasm4pm_types` — a real
  dual-bookkeeping violation this repo's own law forbids, pre-existing,
  not introduced this session.
- `decision_mining.py`/`enhancement.py`/`resource_perspective.py`: real,
  tested, callable — zero real `src/` call sites. Agent 4 confirmed a
  real, honest wiring point exists (the sqlite store
  `mcp_instrumentation.py` already populates), distinct from
  `togaf_loop_demo.py`'s in-memory `OcelLog` — connecting them requires
  opening that sqlite connection from a real orchestrator, not fabricating
  new input shape.
- `wasm4pm_bridge.py`'s `predict_remaining_duration()`/`detect_drift()`:
  real, tested, callable (shells out to a real `wpm` binary) — zero
  callers outside their own test file.
  `laboratory.ArchitectureChangeTrigger.confidence` is always a
  hand-typed literal in the one place it's ever constructed (a unit test)
  — never computed from `detect_drift()`'s real output. The typed seam
  for this (`ProcessObservation.drift_indicator_refs`,
  `ArchitectureChangeTrigger.confidence`) already exists in `laboratory.py`;
  only `UnsupportedProcessScienceProvider` exists as a real implementation.
- No real case-level throughput/cycle-time/waiting-time computation
  anywhere in this repo (confirmed by exhaustive grep, zero matches).
  `enhancement.py::bottleneck_ranking` is a real, narrower, orphaned
  activity-gap-duration primitive — not case-level performance analysis.
- `OcelSink`/`OcelSessionRecorder`/`OcelExecutionRecorder` all expose an
  unvalidated `.log` property a caller can read directly instead of the
  validating `.validated()`/`.close()` method — opt-in validation, not
  enforced by the type system. Named as a real, general design gap, not
  fixed this session (would need a real API redesign, not a one-line fix).

## See also

- `docs/2026-08-11-autonomic-loop-gap-ledger.md` — the broader autonomic-
  loop standing ledger this file is scoped narrower than.
- `src/autofde_lab/ocel/object_centric_conformance.py` — the real,
  independent conformance mechanism used to validate this session's
  closures.
