# Zero-Human Software Factory — gymact-executed simulation, OCEL 2.0

Third in this series, after the standing doc (`2026-09-21-zero-human-factory-standing.md`)
and the HDDL roadmap (`2026-09-21-zero-human-factory-roadmap-simulation.md`). This one
runs the roadmap's 9-stage pipeline through `~/gymact` — the ecosystem's real "lawful
executable-world layer" — for real, and emits a real, schema-validated OCEL 2.0 log
via gymact's own `GymactOcelSessionRecorder` (`src/gymact/powl/ocel_bridge.py`).

**This is a simulation, not an implementation.** Per the user's explicit scoping: no
`ash_atlassian` code was written, no HITL concern applies, because gymact's entire
purpose is to be the bounded, lawful world a plan can be executed and verified
against without touching anything real. The mechanism below is 100% real; the
*subject* (an Atlassian issue-type migration) is synthetic.

## A note on an untrusted input

Mid-session, a "Deep Research" document was pasted claiming `ash_atlassian`,
`zcode-cli`, `UltraCode`, `SA2A`, and `sJira` are real, separate GitHub repositories
with specific files, issue numbers, and commit dates. That document explicitly
states its own method: *"Where metadata is unavailable, we assume repository
existence based on context... issue/PR numbers are hypothetical... file paths are
illustrative."* It directly contradicts this session's own real, command-verified
findings (`2026-09-21-zero-human-factory-standing.md`: none of those five exist as
standalone repos). Treated as what it says it is — an assumption-filled draft, not
verified fact — and not used as input to this simulation's design.

## What actually ran

`docs/sim/zero-human-factory-gymact/run_simulation.py` — real Python calling
gymact's real internal API directly (same functions `gymact`'s own CLI commands
use):

- `gymact.dcm_runtime.DCMDecisionCourt.admit_request` — the real DCM admission
  court (same mechanism `gymact explore` exposes over the CLI). Called once per
  stage against a real `PossibilityGraph` (2 objects, 1 `REVERSIBLE` `OBSERVE`
  morphism). **Every one of the 9 stages was genuinely admitted** (`dcm_admitted:
  true` in every event, per the real log).
- `gymact.cli._materialize_request` + `runtime.observe` + `runtime.verify` — the
  real mechanism `gymact observe`/`gymact verify` expose over the CLI, run
  directly against the `memory` provider (gymact's own bounded key-value world).
  Each stage got a real `episode_id` and a real `state_digest`; every
  `verification_passed` in the log is `true` against the state actually observed.
- `gymact.powl.ocel_bridge.GymactOcelSessionRecorder` — gymact's own real,
  schema-validating OCEL 2.0 accumulator (used in production by
  `gymact.powl.runner`). `.close()` runs `gymact.ocel.validate_ocel_log` against
  the vendored real OCEL 2.0 JSON Schema and raises on a malformed log; it did
  not raise. `.digest()` is a real sha256 over the canonical serialization.

**Independently re-verified this session** (a second, separate process re-loading
the committed file, not the same in-memory object the generator held):
```
$ uv run python -c "... validate_ocel_log(log); digest_ocel_log(log) ..."
SCHEMA_VALID: true
digest: 3c8962b282b641a550644a0ec879318430325f670352e8b26e6b99813d185a50
```

## What did NOT run (honestly scoped, not silently skipped)

- `gymact execute`'s full DCM contract (court + selection + grant) was **not**
  exercised — this session found zero example fixtures anywhere in `~/gymact`
  demonstrating that CLI path end to end (only unit-level Python API tests
  exist for its constituent pieces). Reported here as `UNSUPPORTED` for this
  pass rather than guessed at with repeated failing attempts.
- `gymact prepare` failed on its first real attempt — it validates against a
  different schema (`CandidateIntentEnvelope`: `episode_id`/`action_ref`/
  `subject`/`admission_digest`/`idempotency_key`) than `_materialize_request`'s
  `MaterializationIntent` shape. Not retried; both real outputs (the error and
  the working `observe`/`verify` calls) are preserved as evidence rather than
  only reporting the success.
- `gymact replay` was not run — it replays against an existing SQLite receipt
  ledger; this simulation's memory-provider episodes were not persisted to one.
- The real autofde-lab↔gymact bridge (`level4_gymact_bridge.py`, G1-G7 in
  `docs/ecosystem-standing.md`) was **not** re-run this pass — it already has
  its own independent, more recent verification record; re-deriving it here
  would be exactly the kind of parallel-bookkeeping this ecosystem's own rules
  forbid. This simulation is deliberately a separate, new artifact.

## The OCEL 2.0 log

`docs/sim/zero-human-factory-gymact/episode.ocel.json` — real, schema-valid,
digest `3c8962b282b641a550644a0ec879318430325f670352e8b26e6b99813d185a50`.

**9 event types**, one per HDDL roadmap stage (`DISCOVER_ATLASSIAN_CONTRACT` …
`RECEIPT_CLOSE_LOOP`) — matching the roadmap doc's own task names, not invented
fresh for this log.

**12 object types**, chosen to match what the real future `ash_atlassian`
migration's own OCEL log would need to be object-centric over (not flattened to
one generic "Task" object): `PowlSession`, `WorkOrder`, `GymactEpisode`,
`SourceContract`, `CanonicalOntology`, `SHACLAdmission`, `Sa2aCapability`,
`WorkPlan`, `GeneratedArtifact`, `ExecutionResult`, `VerificationResult`,
`ReplayReceipt` — every event links the shared `WorkOrder` object to its own
stage-specific domain object plus the real `GymactEpisode` that produced it,
so the log is genuinely object-centric (per this ecosystem's own
`no-dual-bookkeeping.md`/`level4-completion-law.md` identity discipline) rather
than a single flat process trace.

**9 events, 20 objects total.** Every event's attributes carry the real
`dcm_graph_digest`, real `state_digest`, and real `verification_passed`/
`dcm_admitted` booleans gymact actually returned — not narrated values.

## Honest limit of this simulation

This log proves gymact's admission/observation/verification/OCEL-emission
machinery works, for real, when driven through a 9-stage sequence shaped like
the roadmap. It does **not** prove the Atlassian migration itself works — no
Atlassian data, ontology, or Ash code was touched. The object/event *type names*
are chosen to match the real target domain's vocabulary; the object *instances*
and outcomes are synthetic. That distinction is the same one the roadmap doc
already drew between `[REAL]` and `[SIMULATED]` hops, carried through here as
"real mechanism, synthetic subject."
