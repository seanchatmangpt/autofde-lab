# v26.9.17 crown -- latency and scaling benchmark (2026-09-17)

QUALIFICATION-mode pass over the v26.9.17 crown machinery
(`src/autofde_lab/sa2a/experience/`, `episode/`, `composition/`, `release/`,
`unknown/router.py`): real, measured (`time.perf_counter()`) performance
characteristics, not estimates. Every number below was produced by running
`tests/sa2a/benchmarks/bench_v26_9_17_crown.py` this session and is reproduced
from its actual stdout (`--full` mode; see the exact command under each
section). Two small Chicago-style pytest smoke tests
(`tests/sa2a/benchmarks/test_perf_smoke_chicago.py`) pin the two real findings
below as fast regression guards -- both pass (`2 passed in 0.74s`).

This pass is read-only of `src/autofde_lab/sa2a/`: it adds a benchmark script
and two smoke tests only, per this phase's ownership scope.

## Headline finding

**The dominant cost of a full `ReleaseRun.run()` crown is not the sa2a
machinery -- it is the `fresh_consumer` subprocess spawn.** Episode 1 and
Episode 2 together cost single-digit milliseconds; the real, separate-process
fresh-consumer verifier subprocess costs 92% of total crown wall-clock time
(measured: 413.6ms of 449.4ms). This is expected given ARD §45's explicit
design requirement (fresh_consumer MUST run in a genuinely separate process,
never in-process, so producer in-memory state cannot leak into the standing
verdict) -- Python interpreter cold-start is the price of that real
independence guarantee, not a bug. Named here because it is the single
largest number in this whole benchmark and anyone tuning crown latency should
look there first, not at the episode logic.

**Second finding, exactly the one this task predicted: `DurableDiskReceiptStore.__init__()`
cost is real and grows roughly linearly (not flat) with the number of
pre-existing receipt files in its `store_dir`** -- 0.06ms at 0 files, 91.2ms
at 1000 files, roughly 0.09ms/file. `Episode1Runner`/`Episode2Runner` each
construct a **fresh** `DurableDiskReceiptStore` per `run()` call
(`episode1.py:344`, `episode2.py:149`), and `__init__` unconditionally calls
`_sync_from_disk()`, which globs and `json.loads()`s **every**
`prep_*.json`/`final_*.json` file in the directory
(`consequence_court.py:130-163`+). Any caller that reuses one `receipt_store_dir`
across many episode runs (the natural pattern for a long-lived crown loop)
pays this cost on every single run, and it gets worse every run since the
file count only grows. At realistic long-run scale (tens of thousands of
episodes sharing one dir) this is an `O(N)`-or-worse per-run tax that never
shows up in a short-lived test but would dominate a production crown loop's
wall-clock time within days. **Left open, not fixed**: this phase is
read-only of `src/autofde_lab/sa2a/` by its own ownership scope (see the
task's "YOUR OWNERSHIP" boundary) -- a real fix (e.g. an index file, lazy
per-token lookup instead of eager full-directory hydration, or a documented
receipt-store-rotation policy) belongs to whoever owns
`conformance/courts/consequence_court.py`, not this benchmark pass.

## Reproduction

```bash
cd /Users/sac/autofde-lab
.venv/bin/python tests/sa2a/benchmarks/bench_v26_9_17_crown.py --full   # ~15s wall-clock
.venv/bin/python -m pytest tests/sa2a/benchmarks/test_perf_smoke_chicago.py -v --import-mode=importlib
```

Environment this run was measured in: `python=3.13.9`, `platform=darwin`,
repo `/Users/sac/autofde-lab`, branch `fix/autofde-lab-v26.9.17-boundary`.
Numbers below are absolute wall-clock on this one machine, not portable
constants -- the *shape* (flat vs. linear vs. dominant-subprocess) is the
real, reproducible finding; the exact millisecond values will differ on other
hardware.

## 1. Single-run latency breakdown

### 1a. Episode1Runner -- per-stage breakdown (manual replication of `run()`'s
internal call sequence against the real sub-pipeline pieces, `n=5` reps, `--full` run)

| Stage | mean (ms) | min (ms) | max (ms) |
|---|---|---|---|
| `route_unknown_to_frontier` | 0.1051 | 0.0289 | 0.3756 |
| `discover` (caller callable) | 0.0188 | 0.0148 | 0.0257 |
| `admit_candidate` | 0.0279 | 0.0194 | 0.0437 |
| `compile_experience` | 0.0320 | 0.0245 | 0.0493 |
| `admit_experience` | 0.0262 | 0.0212 | 0.0330 |
| `qualify_experience` | 0.0355 | 0.0295 | 0.0454 |
| boundary setup + `admit_target_binding` (rdflib TTL parse) | 1.8943 | 0.5988 | 6.5254 |
| `ConsequenceBoundary.execute()` (real disk actuation + receipt commit) | 1.3224 | 1.0522 | 1.9412 |
| **TOTAL (sum of the above)** | **3.4622** | 1.7915 | 9.0393 |

**`admit_target_binding`'s `AdmissionPipeline().admit(ttl, ...)` rdflib TTL
parse + boundary object construction is the largest sa2a-internal stage** --
55% of the manual-replication total, and larger than the real disk-actuating
`ConsequenceBoundary.execute()` call itself. All 6 experience-lifecycle
stages (frontier routing through qualification) combined cost 0.24ms, under
7% of the total -- the experience-compile/admit/qualify pipeline this pass
was built around is not where the time goes.

### 1b. Episode1Runner.run() end-to-end (single call, cross-check against 1a)

`n=5`: mean=4.7733ms, min=4.451ms, max=5.2681ms.

The ~1.3ms gap over 1a's summed 3.46ms is accounted for by what the manual
replication in 1a deliberately does NOT do: `Episode1Runner.run()` calls
`self._checkpoint()` six times (one JSON write to `state_dir` per completed
stage) and drives a real `OcelExecutionTracer` (`declare_object`/
`record_event`/`export_ocel2_json`, one more disk write) that 1a's hand-rolled
replication skips. That gap is real, durable-crash-recovery + OCEL-evidence
cost, not measurement noise.

### 1c. Episode2Runner.run() -- isolated vs. combined-with-setup (`n=5`)

| Measurement | mean (ms) | min (ms) | max (ms) |
|---|---|---|---|
| `Episode2Runner.run()` alone (KnownRoute/experience_store already built) | 3.3152 | 2.4158 | 6.391 |
| Episode1-setup-to-produce-a-KnownRoute + `Episode2Runner.run()` combined | 6.7798 | 5.8352 | 9.6987 |

Episode 2 alone is comparable to Episode 1's total (3.3ms vs. 4.8ms) --
expected, since it runs the same authority/BRCE machinery minus the
discovery/experience-compile stages, replaced by one `KnownRouteRegistry.lookup()`
call (independently confirmed sub-millisecond in section 2 below).

### 1d. Full ReleaseRun.run() crown, including the real fresh_consumer subprocess (`n=3`)

| Measurement | mean (ms) | min (ms) | max (ms) |
|---|---|---|---|
| `ReleaseRun.run()` TOTAL (11-state crown, includes its own internal fresh_consumer call) | 449.419 | 432.198 | 467.053 |
| `fresh_consumer` subprocess spawn, isolated (exact same command re-invoked against the produced `state_dir`) | 413.642 | 380.760 | 432.091 |
| fresh_consumer as % of total crown latency | **92.0%** | | |

The remaining ~36ms (449.4 - 413.6) covers `SubjectResolver.resolve()`,
`Episode1Runner.run()`, `Episode2Runner.run()`, and `ReplayEngine.verify_chain()`
combined -- consistent with 1b/1c's episode-level numbers (4.8 + 3.3 =~ 8ms)
plus TTL/manifest parsing and replay-chain verification overhead.

## 2. KnownRouteRegistry.lookup() scaling

Command: `bench_known_route_registry_scaling([10, 100, 1000, 10000])` inside
`--full`. Routes spread round-robin across 50 `semantic_class_id` values;
`lookup()` is keyed by class first (`_routes_by_class: dict[str, list[KnownRoute]]`),
so it only ever scans routes within the queried class, never all N.

| N total routes | routes/class (approx) | best case (first-in-class hit), mean ms | worst case (last-in-class hit), mean ms | miss (full class scan), mean ms |
|---|---|---|---|---|
| 10 | 1 | 0.0003 | 0.0003 | 0.0002 |
| 100 | 2 | 0.0002 | 0.0003 | 0.0003 |
| 1,000 | 20 | 0.0002 | 0.0019 | 0.0019 |
| 10,000 | 200 | 0.0003 | 0.0309 | 0.0315 |

**Finding: flat in total N, linear in routes-per-class -- exactly what the
dict-of-lists design predicts, confirmed for real up to 10,000 routes.** Best
case stays pinned at ~0.0002-0.0003ms regardless of total registry size
(class lookup is O(1) dict access + the match is the first list element).
Worst case grows with class size: 20 routes/class -> 0.0019ms, 200
routes/class (10x) -> 0.0309ms (~16x) -- consistent with the linear
`for route in self._routes_by_class.get(...)` scan `known_route.py:120`
performs, not evidence of anything worse than O(class_size). At realistic
scale (a semantic class is a bounded operational problem family, not an
unbounded set) this design is sound; it would only degrade if a single class
accumulated an unboundedly large number of ACTIVE routes, which is its own
separate concern (route lifecycle / invalidation hygiene), not a lookup()
defect.

## 3. DiscoveryRouter.route() scaling

Command: `bench_discovery_router_scaling([10, 100, 1000])`. N engines
registered round-robin across the 5 `DiscoveryEngineKind` precedence tiers.

| N engines | best case (engine-0, tier 1, first position), mean ms | worst case (engine N-1, tier 5, last position), mean ms | miss (no engine answers), mean ms |
|---|---|---|---|
| 10 | 0.0029 | 0.0064 | 0.0051 |
| 100 | 0.0028 | 0.0291 | 0.0302 |
| 1,000 | 0.0025 | 0.3401 | 0.2889 |

**Finding: a real, measured, roughly-linear-in-N growth for both the
worst-case hit and the miss path -- confirmed live, not just theorized from
reading the source.** Best case is flat (~0.0025-0.0029ms regardless of N,
since the router returns on the very first engine tried). Worst case grows
~10x per 10x of N (0.0064ms -> 0.0291ms -> 0.3401ms across 10 -> 100 -> 1000),
consistent with `DiscoveryRouter.route()`'s actual implementation
(`unknown/router.py:120-138`): for each of the 5 precedence tiers, it builds
a fresh generator `(e for e in self._engines if e.kind == kind)` over the
**entire** `self._engines` list and iterates it, so locating a match (or
confirming no match) in the last tier requires walking the full engine list
up to 5 times over (once per tier already exhausted before reaching the
answering tier) -- an `O(tiers * N)` = `O(5N)` worst case, not `O(N)`. At
N=1000 this is still sub-millisecond in absolute terms and not a practical
problem at any registry size this system is likely to reach (tens to low
hundreds of discovery engines, not thousands), but it is a real, confirmed
inefficiency relative to what a single `kind -> list[DiscoveryEngine]` index
(mirroring `KnownRouteRegistry`'s own `_routes_by_class` design one file
over) would give: O(N) worst case instead of O(5N), with the same
precedence-order guarantee. **Left open, not fixed**: `unknown/router.py` is
under this phase's read-only-of-source scope.

## 4. DurableDiskReceiptStore construction cost vs. pre-existing file count

Command: `bench_receipt_store_construction_scaling([0, 10, 100, 1000])`.
Each N is a REAL count of `prep_*.json` + `final_*.json` files, produced by N/2
real `ConsequenceBoundary.execute()` actuations against a real
`RealDiskJournalActuator`/`IndependentDiskJournalVerifier`/`DurableDiskReceiptStore`
before the timed construction (seeding time reported separately, not counted
in the measured construction cost).

| N pre-existing files | seeding time (real actuations, not counted) | `DurableDiskReceiptStore(store_dir)` construction, mean ms | min ms | max ms |
|---|---|---|---|---|
| 0 | -- | 0.0619 | 0.0538 | 0.1084 |
| 10 | 8.3ms | 0.7187 | 0.6510 | 0.8737 |
| 100 | 72.0ms | 8.0378 | 6.9512 | 9.2446 |
| 1,000 | 1858.5ms | 91.2259 | 70.7118 | 113.905 |

**Confirmed: real, ~linear (not flat) growth -- roughly 0.06ms base +
~0.09ms/file** (91.2ms / 1000 files =~ 0.091ms/file; 8.04ms / 100 files =~
0.080ms/file; 0.72ms / 10 files =~ 0.072ms/file -- consistent slope across
two orders of magnitude, not noise). This is exactly the scaling bottleneck
named in this task's brief before any number was collected, and the
measurement confirms it rather than merely restating the prediction:
`__init__` -> `_sync_from_disk()` (`consequence_court.py:124-128`) globs and
fully `json.loads()`s every receipt file on **every single construction**,
and `Episode1Runner`/`Episode2Runner` both construct a fresh
`DurableDiskReceiptStore` inside their own `run()` (`episode1.py:344`,
`episode2.py:149`) rather than accepting one as a constructor-injected,
process-lifetime-scoped dependency the way `known_route_registry`/
`artifact_registry` already are. A crown loop that reuses one
`receipt_store_dir` across, say, 10,000 episodes over its lifetime would pay
~910ms of pure re-hydration cost on the 10,000th episode's `run()` call
alone, growing without bound as the directory grows -- a real, unbounded
per-run tax that a short test run never surfaces. **Left open, not fixed**:
`conformance/courts/consequence_court.py` is under this phase's
read-only-of-source scope; the natural fixes (accept an injected,
long-lived `DurableDiskReceiptStore` instance in `Episode1Runner`/
`Episode2Runner.__init__` instead of constructing one per `run()`; or make
`_sync_from_disk()` lazy/indexed instead of eager) both touch files this
phase does not own.

## Regression guards added this phase

`tests/sa2a/benchmarks/test_perf_smoke_chicago.py` -- two real, fast (0.74s
combined), Chicago-style tests (real disk I/O, real `ConsequenceBoundary`
actuation, real `DiscoveryRouter`/`DiscoveryEngine` objects; zero mocks) that
pin findings 3 and 4 above as regression guards with generous (30-150x)
margins over the real measured cost at their tested scale, so they catch a
genuine order-of-magnitude regression without being sensitive to ordinary
machine-load jitter:

```
$ .venv/bin/python -m pytest tests/sa2a/benchmarks/test_perf_smoke_chicago.py -v --import-mode=importlib
...
2 passed in 0.74s
```

Mock-usage verification (required by this repo's `testing-chicago-style.md`
for every test added):

```
$ grep -rn "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" tests/sa2a/benchmarks/*.py
(no output -- grep exit code 1, zero matches)
```

## What this pass did NOT do (named, not papered over)

- Did not benchmark under concurrent/parallel load (multiple `Episode1Runner`s
  writing to the same `receipt_store_dir` simultaneously) -- this repo's
  `DurableDiskReceiptStore` and `RealDiskJournalActuator` have no documented
  concurrency contract, and fabricating one for a benchmark would be
  measuring an assumption, not a real property.
- Did not benchmark `ExperienceCompiler`/`ExperienceAdmissionGate`/
  `ExperienceQualifier` at scale (many thousands of `MachineExperience`
  objects compiled in one process) -- section 1a already shows each of these
  three stages individually costs under 0.04ms per call with the real
  objects used in this session's fixtures; a dedicated at-scale pass would
  need a realistic distribution of candidate/experience payload sizes this
  benchmark does not have grounds to invent.
- Did not fix either of the two real findings above (DiscoveryRouter's O(5N)
  worst case, DurableDiskReceiptStore's O(N) re-hydration) -- both require
  editing `src/autofde_lab/sa2a/unknown/router.py` and
  `src/autofde_lab/sa2a/conformance/courts/consequence_court.py`, outside
  this phase's read-only-of-source ownership boundary. Named precisely here
  per `.claude/rules/absence-is-not-evidence.md` ("a discovered gap is a
  result, not something to paper over") so the next phase that owns those
  files has the exact numbers and line references, not a vague "might be
  slow" note.

## See also

- `tests/sa2a/benchmarks/bench_v26_9_17_crown.py` -- the benchmark script
  these numbers were measured from; run it directly to reproduce.
- `tests/sa2a/benchmarks/test_perf_smoke_chicago.py` -- the two regression
  guards.
- `src/autofde_lab/sa2a/conformance/courts/consequence_court.py:112-163` --
  `DurableDiskReceiptStore.__init__`/`_sync_from_disk`, the section 4 finding.
- `src/autofde_lab/sa2a/unknown/router.py:96-142` -- `DiscoveryRouter.route()`,
  the section 3 finding.
- `src/autofde_lab/sa2a/experience/known_route.py:107-132` --
  `KnownRouteRegistry.lookup()`, the section 2 confirmation.
