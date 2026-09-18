# v26.9.17 concurrency/race stress findings (real, this session)

Real Python `threading` (OS threads under the GIL), real filesystem I/O, real `Episode1Runner`/`Episode2Runner`/`KnownRouteRegistry` objects. Zero mocks. Produced by `tests/sa2a/test_v26_9_17_concurrency_stress_chicago.py`, run this session with `.venv/bin/python -m pytest tests/sa2a/test_v26_9_17_concurrency_stress_chicago.py -v`.

N_THREADS=8, N_TRIALS=5 (5 independent trials, fresh work_dir each).

## 1. Episode1Runner/Episode2Runner sharing journal_path/receipt_store_dir/state_dir

Each thread constructs its OWN `Episode1Runner`/`Episode2Runner` (own `KnownRouteRegistry`, own `ArtifactRegistry`, own `ExplorationMeter`) but all 8 threads in a trial point at the SAME `journal_path`/`receipt_store_dir`/`state_dir` -- the exact sharing pattern `ReleaseRun.run()` itself uses across episode1/episode2 within one run.

| trial | duration_s | attempted_actuations | journal_records_on_disk | lost_journal_records | journal_parse_error |
|---|---|---|---|---|---|
| 0 | 0.033 | 13 | 6 | 7 | (none) |
| 1 | 0.025 | 13 | 5 | 8 | (none) |
| 2 | 0.03 | 15 | 4 | 11 | (none) |
| 3 | 0.031 | 15 | 8 | 7 | (none) |
| 4 | 0.025 | 13 | 6 | 7 | (none) |

**Real numbers across all 5 trials**: 69 total `boundary.execute()` calls that reached actuation (authority+admission passed, fresh idempotency token), 29 records actually present in the shared journal file afterward, **40 lost journal records** (5/5 trials showed at least one lost record).

**CONFIRMED, LIVE RACE**: `RealDiskJournalActuator.actuate()` (`src/autofde_lab/sa2a/conformance/courts/consequence_court.py`) performs an unsynchronized read-modify-write on the shared journal file: `records = json.loads(journal_path.read_text())` then `records.append(entry)` then atomic `os.replace()` of the whole file. The atomic `os.replace()` makes each INDIVIDUAL file write torn-write-safe (no partial/corrupt file is ever visible -- confirmed by `journal_parse_error` being empty in every trial above) but it does **not** make the READ-then-APPEND-then-WRITE sequence atomic as a whole. When two threads' `actuate()` calls interleave: both read the same N-record list, both independently append their own entry to their own in-memory copy, and whichever thread's `os.replace()` lands second silently overwrites the first thread's entry with a file that never contains it -- a classic lost-update race, invisible to both actuator calls (each returns `applied: True`, since neither ever inspects the other's write).

**Consequence for correctness (not just availability)**: the LOST thread's own `IndependentDiskJournalVerifier.verify_postcondition()` call then reads the journal's `records[-1]` and finds a DIFFERENT thread's `action`/`target`/`payload_digest` there, so it correctly returns `False` -- the boundary reports `success=False` / `TerminalReceiptState.UNKNOWN_OUTCOME` for that thread's real, genuinely-happened actuation. This is fail-closed (no false `EXECUTED` was ever observed in these trials -- see the wrong-answer count below), but it is still a real defect: a durably-real disk mutation happened, and the system's own receipt for it reports a state that says it never verifiably happened, because the on-disk EVIDENCE of that mutation was overwritten by a concurrent writer before the verifier could observe it.

**Per-episode outcome counts across 40 total thread-runs (5 trials x 8 threads)**: 29 reached Episode 1 KNOWN/EXECUTED; 11 attempted actuation but the boundary reported failure (the lost-journal-record consequence above, when nonzero); 0 raised an uncaught exception; 0 silent wrong-answer(s) (cross-episode receipt digest collision) observed.

## 2. KnownRouteRegistry concurrent register_route()/lookup() stress

ONE shared `KnownRouteRegistry` instance per trial, N=8 threads each registering a route under its OWN distinct semantic class while ALL 8 threads concurrently call `.lookup()` against every other thread's class (20 lookup passes per thread) -- direct pressure on the plain, unlocked `dict`/`list` structures in `register_route()`/`lookup()`.

| trial | errors | routes_registered | routes_visible | lost_registrations |
|---|---|---|---|---|
| 0 | 0 | 8 | 8 | 0 |
| 1 | 0 | 8 | 8 | 0 |
| 2 | 0 | 8 | 8 | 0 |
| 3 | 0 | 8 | 8 | 0 |
| 4 | 0 | 8 | 8 | 0 |

**No RuntimeError and no lost registration observed across all 5 trials x 8 threads for the register_route()/lookup() access pattern.**

## 3. KnownRouteRegistry.register_route() racing .deactivate() (dict-resize-during-iteration hazard)

`deactivate()`'s `for routes in self._routes_by_class.values(): ...` iterates the SAME outer dict `register_route()`'s `setdefault()` can insert a brand-new key into -- the textbook shape for CPython's `RuntimeError: dictionary changed size during iteration`. 30 independent trials (higher count than scenarios 1-2, since this shape needs a thread switch to land inside a narrow iteration window): 6 threads each calling `register_route()` under a brand-new semantic class while 2 threads concurrently call `deactivate()` 50x each against an already-seeded route.

**Zero errors observed across all 30 trials** (current state: `KnownRouteRegistry` now holds a `threading.RLock` guarding every method -- see 'Fix applied' below). This scenario was ALSO run before the lock was added (same code, same trial count, via a throwaway scratchpad script) and likewise produced zero errors -- so this result does not, by itself, prove the lock closed a live bug; it is consistent with either 'the lock works' or 'this shape needs more contention than 6+2 threads on this machine to trigger under the GIL,' and this findings document does not overclaim which. The lock is retained as correctness-by-construction (no test-scale-dependent race window at all, rather than an empirically unobserved one) since it is a narrow, single-file, low-risk change.

## Fix applied vs. left open

- **`KnownRouteRegistry` (`src/autofde_lab/sa2a/experience/known_route.py`)**: FIXED. Added a `threading.RLock` (`self._lock`) guarding `register_predicate()`, `register_route()`, `deactivate()`, `lookup()`, and `routes_for_class()` -- every method that reads or writes `_routes_by_class`/`_predicates`. `lookup()` snapshots the candidate route list and predicate dict under the lock, then releases it before calling any caller-supplied `predicate(candidate)` (foreign code must never run while holding this registry's own lock). Owned single-file class, no fan-out to other callers' internals -- re-verified safe against the full `tests/sa2a` suite (`.venv/bin/python -m pytest tests/sa2a -q`, exit 0, all passing) after the change.
- **`RealDiskJournalActuator`/`DurableDiskReceiptStore` (`src/autofde_lab/sa2a/conformance/courts/consequence_court.py`): left open, NOT fixed**, per this task's explicit scope guidance. `RealDiskJournalActuator` is constructed at call sites across 5 `src/` modules (`consequence_court.py`, `episode1.py`, `episode2.py`, `conformance/benchmarks/harness.py`, `conformance/runner.py`, `conformance/courts/replay_court.py`) and imported by 20 test files; `DurableDiskReceiptStore` similarly by 4 `src/` modules and 18 test files (full list: `grep -rln "RealDiskJournalActuator\|DurableDiskReceiptStore" src/ tests/`). A lock added inside `actuate()`/`_sync_from_disk()`/`save_prepared`/`save_final` would need to be keyed by the resolved `journal_path`/`store_dir` (since separate instances currently share no Python-level state at all -- each `Episode1Runner.run()`/`Episode2Runner.run()` call constructs a brand-new `DurableDiskReceiptStore`/`RealDiskJournalActuator` instance) to actually close this race, which is exactly the kind of shared-infrastructure internals change this task's ownership boundary excludes. This mirrors the reasoning the AFDE-2604 Lens 4 R1/R2/R3 TOCTOU findings were deliberately left SURVIVED/open for (`docs/jira/v26.9.16/AFDE-2604-admission-fencing-local-closure.md`: "Lens 4's R1/R2/R3 (TOCTOU/concurrency) deliberately left SURVIVED, verified not accidentally masked"). Named here as a NEWLY CONFIRMED instance of that same open concurrency-safety gap, now reproduced against the v26.9.17 crown path specifically (Episode1Runner/Episode2Runner sharing a journal across real OS threads), not just against the older RFC-SA2A-001/AFDE-2604 courts.

## Reproduction

```bash
.venv/bin/python -m pytest tests/sa2a/test_v26_9_17_concurrency_stress_chicago.py -v
```

