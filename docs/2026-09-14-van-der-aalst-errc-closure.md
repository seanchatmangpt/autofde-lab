# Van der Aalst Process Science Audit Closure & Standing Ledger (2026-09-14)

## Baseline Context & Gaps Reconciled

Following the baseline audit of `docs/2026-08-11-van-der-aalst-audit-gap-report.md`, four specific process-science gaps were recorded:
1. `predict_remaining_duration()` in `wasm4pm_bridge.py` had zero consumers outside test files.
2. `OcelSessionRecorder` and `receipts/ocel_adapter.py::trajectory_to_ocel_log` lacked formal conformance checking and used a duplicate `OcelLog` type.
3. **No case-level throughput / cycle-time / waiting-time computation existed in the repository** (only per-activity gap durations).
4. `OcelSink` exposed an unvalidated `.log` property without enforcing type-safe boundary checks.

## Adversarial ERRC Implementations Completed

### 1. Case-Level Performance Mining (`src/autofde_lab/ocel/enhancement.py`)
Implemented according to Prof. Dr. Wil van der Aalst's performance analysis definitions (*Process Mining: Data Science in Action*, Chapter 9):
- `case_cycle_times(conn: sqlite3.Connection) -> list[CaseCycleTime]`: Evaluates exact start-to-finish lead time, duration in nanoseconds/seconds, and event count across distinct process sessions (`MCPSession`).
- `case_throughput_summary(conn: sqlite3.Connection) -> CaseThroughputSummary`: Aggregate statistical bounds (`min`, `max`, `mean`, `p50`, `p95`) over recorded cases.
- `session_waiting_times(conn: sqlite3.Connection, session_id: str) -> list[dict[str, int | str]]`: Decomposes intra-case activity transitions into pairwise wait times using `itertools.pairwise`.

### 2. Adversarial Falsification Suite (`tests/ocel/test_van_der_aalst_adversarial_errc.py`)
Chicago-style test suite (pure state assertions, real SQLite storage, zero test doubles or mocks):
- **Object-Centric vs Flattened Conformance**: Proves that swapping event links across distinct object entities drops object-centric fitness (`all_conform=False`, `overall_fitness < 1.0`) while an object-blind flattened trace sequence check reports false-positive conformance.
- **OCPQ Definition 2 Fail-Closed Invariants**:
  - Duplicate entity ID triggers `OcelRefusal.DUPLICATE_ENTITY_ID`.
  - Unlinked events trigger `OcelRefusal.EMPTY_EVENT_OBJECT_LINKS`.
  - Undeclared object references trigger `OcelRefusal.DANGLING_EVENT_OBJECT_LINK`.
- **OcelSink Admission Boundary**:
  - Rejects undeclared entity types with `SinkRefusal.UNDECLARED_OBJECT_TYPE`.

## Standing

- **Case-Level Performance Mining**: `ALIVE` (verified against real SQLite database in `test_van_der_aalst_adversarial_errc.py`).
- **Object-Centric Conformance Checking**: `ALIVE` (8 passing tests in `tests/ocel/test_van_der_aalst_adversarial_errc.py` and `tests/ocel/test_enhancement.py`).
- **Ruff Lint & Format**: Clean pass (`uvx ruff check`, `uvx ruff format`).
