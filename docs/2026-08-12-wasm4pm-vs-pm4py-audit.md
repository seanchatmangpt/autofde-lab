# wasm4pm vs. pm4py — a claim-by-claim correctness audit

Requested directly: check `wasm4pm`'s process-mining claims in this repo
against `pm4py` (the reference open-source process-mining library) and the
real academic literature it cites. This is a documentation/definition-level
audit, not a code-execution audit — `autofde-lab` deliberately never
imports `pm4py` (confirmed: zero `pyproject.toml`/`uv.lock` hits; every
real mention in this repo is either an explicit "excluded per license" note
or a citation to pm4py's tutorial fixture data), so the algorithms this
audit checks run in `~/wasm4pm`'s external Rust binary, not in this repo's
Python. Where a real, independent pm4py cross-check does exist, it lives in
the sibling `~/gymact` repo (which has no license conflict there) and is
cited, not duplicated.

## Method

Three parallel research passes this session: (1) every wasm4pm-attributed
claim in `autofde-lab`, with file:line citations; (2) pm4py's real, primary-
source definitions for the corresponding concepts; (3) this repo's own
prior docs on wasm4pm's standing, plus a directly relevant precedent found
in `~/gymact`. Six claims are checked below, each given one verdict:

- `CONSISTENT` — claim and real definition match at the level checkable here.
- `CONSISTENT_BUT_EXTERNALLY_COMPUTED` — the formula matches on paper; the
  actual computation runs in `~/wasm4pm`'s Rust source and was not
  independently re-run this session.
- `DIVERGENT` — a real, material difference was found.
- `NO_DIRECT_PM4PY_EQUIVALENT` — different discovery/analysis paradigm, not
  directly comparable formula-for-formula.

## 1. ILP-based Petri-net discovery

- **Claim** — `src/autofde_lab/ocel/wasm4pm_bridge.py:17-18`, `discover_petri_net()`
  (lines 230-256): `wpm mining discover --algo ilp-petri-net` mines a Petri
  net via ILP-based discovery (`wasm4pm/src/ilp_discovery.rs`).
- **Real reference** — pm4py's own discovery algorithms are Alpha Miner,
  Inductive Miner, and Heuristics Miner (`pm4py.discover_petri_net_{alpha,
  inductive,heuristics}`) — none of which is ILP-based. ILP (integer linear
  programming) formulations for Petri-net discovery are a real, separate
  branch of the process-discovery literature (e.g. van der Werf et al.,
  "Process Discovery using Integer Linear Programming", 2008) that pm4py
  does not implement as a first-class discovery algorithm.
- **Verdict: `NO_DIRECT_PM4PY_EQUIVALENT`.** wasm4pm's ILP approach is a
  real, differently-sourced discovery paradigm from pm4py's three miners —
  not comparable formula-for-formula, and not evidence of an error either.
- **Evidence** — `tests/ocel/test_wasm4pm_bridge.py::test_real_discover_and_conformance_round_trip`
  and `test_real_conformance_against_mcp_user_simulation_log` (both real
  subprocess calls against the `wpm` binary, asserting `places>0`,
  `transitions>0`).

## 2. Token-based-replay conformance / fitness

- **Claim** — `wasm4pm_bridge.py:19-21`, `check_conformance()` (lines
  327-370), `ConformanceReport.avg_fitness` (line 108): real token-based
  replay, citing van der Aalst 2016.
- **Real reference** — pm4py's confirmed, exact formula (from pm4py source,
  `pm4py.algo.evaluation.replay_fitness.variants.token_replay`):

  ```
  log_fitness = 0.5 * (1 - total_m/total_c) + 0.5 * (1 - total_r/total_p)
  ```

  where `c` = tokens consumed, `p` = tokens produced, `m` = tokens missing
  (artificially inserted), `r` = tokens remaining after replay. This is the
  standard formula from Rozinat & van der Aalst's original token-replay
  conformance paper (cited in pm4py's own docs and independently confirmed
  via Wikipedia's token-based-replay article, which cites the same source).
- **Verdict: `CONSISTENT_BUT_EXTERNALLY_COMPUTED`.** The formula wasm4pm
  claims to compute matches the real, standard definition at the level
  checkable here (the citation and the described consumed/produced/missing/
  remaining accounting are consistent with the real literature). The actual
  arithmetic runs in `~/wasm4pm/src/conformance.rs`, not re-verified
  line-by-line against this repo's own execution this session — naming this
  limit rather than claiming a full independent re-derivation.
- **Evidence** — same two tests as claim 1, asserting `0.0<=avg_fitness<=1.0`.

## 3. ETConformance precision

- **Claim** — `wasm4pm_bridge.py:112-116`, `ConformanceReport.precision`:
  "ETConformance precision (Muñoz-Gama & Carmona)."
- **Real reference** — Muñoz-Gama & Carmona's ETConformance ("A Fresh Look
  at Precision in Process Conformance", BPM 2010) is a real, named,
  published precision metric in the process-mining literature and a real
  precision-checking family pm4py itself implements variants of
  (`pm4py.algo.evaluation.precision`, `align_etconformance` variant).
- **Verdict: `CONSISTENT_BUT_EXTERNALLY_COMPUTED`.** The citation is real
  and correctly attributed; the computation is external
  (`wasm4pm::etconformance_precision::compute_precision`), not re-derived
  here.
- **Evidence** — `test_real_conformance_against_mcp_user_simulation_log`
  asserts `precision is not None` and `0.0<=precision<=1.0`.

## 4. Token-based generalization

- **Claim** — `wasm4pm_bridge.py:117-124`, `ConformanceReport.generalization`:
  "Token-based generalization (Buijs et al. 2012)," and that fitness +
  precision + generalization together close 3 of van der Aalst's 4
  process-mining quality dimensions (fitness, precision, generalization,
  simplicity).
- **Real reference** — Buijs, van Dongen & van der Aalst, "On the Role of
  Fitness, Precision, Generalization and Simplicity in Process Discovery"
  (2012) is a real, correctly-named paper, and the fitness/precision/
  generalization/simplicity quartet is exactly the real, standard
  four-dimension framing from that paper and van der Aalst's book.
- **Verdict: `CONSISTENT_BUT_EXTERNALLY_COMPUTED`.** Citation and framing
  are both real and correctly attributed; computation is external
  (`wasm4pm::generalization::compute_quality`).
- **Evidence** — same test as claim 3, asserting `0.0<=generalization<=1.0`.

## 5. Concept-drift detection — `DIVERGENT` (corrected this session)

- **Claim** — `wasm4pm_bridge.py:25-27` (prior to this session's
  correction), `detect_drift()` (lines 265-295), `DriftPoint`: "windowed
  Jaccard + total-variation distance over consecutive trace windows,"
  citing Bose/van der Aalst/Žliobaitė/Pechenizkiy 2011/2014.
- **Real reference** — the correctly-identified paper is Bose, van der
  Aalst, Žliobaitė & Pechenizkiy, "Handling Concept Drift in Process
  Mining." Its real method: extract windowed features from the
  directly-follows relation — notably the **J-measure** (an
  information-theoretic measure of how predictive one activity's
  occurrence is of another's) — then compare the feature *distributions* of
  adjacent windows using a non-parametric two-sample statistical test, most
  commonly the **Kolmogorov-Smirnov (KS) test**, flagging a drift point
  where the test statistic crosses a significance threshold.
- **What was actually found**: wasm4pm's real, implemented method (Jaccard
  distance over trace-activity vocabulary overlap, plus total-variation
  distance) is **not** the same pipeline as the cited paper — no J-measure
  feature extraction, no KS test. The general idea (compare windowed
  distributions across a log to find a distributional-shift point) is
  faithful in spirit to the paper's problem framing, but the specific
  statistical machinery differs. pm4py itself has no first-class public
  concept-drift API to cross-check against (confirmed this session — no
  `pm4py.discover_concept_drift`-style function exists in its current
  top-level API; this remains literature/plugin territory).
- **Verdict: `DIVERGENT`, now disclosed.** Fixed this session (not an
  algorithm rewrite — a docstring correction, matching this repo's own
  "name it, don't silently reimplement or hide it" pattern already used for
  the CLI metric-swap defect in `level4_process_fitness.py`, see §7 below):
  `wasm4pm_bridge.py`'s module docstring and `DriftPoint`'s class docstring
  now both state plainly that the implemented method is inspired by, not a
  reproduction of, the cited paper's exact pipeline.
- **Evidence** — `tests/ocel/test_wasm4pm_bridge.py::test_real_drift_detects_vocabulary_shift`
  (real, vocabulary-disjoint trace groups, asserts a real drift point with
  `jaccard_distance≈1.0`, `tv_distance≈1.0`, `method=="both"`) — this test
  verifies wasm4pm's *actual* implemented signal detects a real
  distributional shift, which it does; it does not (and was never claimed
  to) verify conformance with the cited paper's specific statistical test.

## 6. `object_centric_conformance.py`'s edit-distance fitness — `DIVERGENT` (corrected this session)

- **Claim** — `src/autofde_lab/ocel/object_centric_conformance.py`,
  `check_object_centric_conformance()`: per-object normalized Levenshtein
  edit distance between observed and intended traces. This module is
  adjacent to wasm4pm (pure Python, no external binary), not itself a
  wasm4pm claim, but its name ("object-centric conformance") directly
  invokes the real, named academic term.
- **Real reference** — "object-centric conformance" in the real literature
  (van der Aalst & Berti, "Discovering Object-centric Petri Nets",
  Fundamenta Informaticae 175(1-4), 2020, arXiv:2010.02047; extended more
  rigorously by Adams et al., "Object-Centric Conformance Alignments with
  Synchronization", arXiv:2312.08537) means **per-object-type token-based
  replay (or alignment) against a discovered object-centric Petri net, plus
  explicit event-to-object relationship-cardinality checking** — e.g. does
  an activity consume exactly one order and one-or-many items, matching the
  model's declared cardinality. This is a materially different and
  stronger notion than a single edit-distance number per object.
- **External validating precedent, already executed (not by this audit,
  cited as evidence)**: `~/gymact` independently pip-installed real pm4py
  (`2.7.22.1`) and ran `pm4py.discover_oc_petri_net` against a real gymact
  OCEL fixture this week (`~/gymact/docs/2026-08-12-gymact-ocel-analysis-implementation-plan-part2.md`,
  lines 49-80) — real object types (`episode`, `environment`, `capability`)
  and real events were recovered, and real per-object-type Petri nets were
  discovered. This confirms the real mechanism is genuinely heavier than a
  string-edit-distance heuristic — a live, independent data point, not an
  assumption.
- **What was found**: `object_centric_conformance.py`'s own module
  docstring already honestly described its method (per-object Levenshtein
  distance) at the paragraph level — it never overclaimed to *be* the
  literature's method. But nothing in the file cross-referenced or
  contrasted against the real, named academic definition its own module
  name otherwise invokes.
- **Verdict: `DIVERGENT` naming, now disclosed.** Fixed this session (docstring
  addendum only, no algorithm change): the module docstring now explicitly
  names the real academic definition, cites both papers, cites the
  `~/gymact` pm4py precedent, and states plainly that this module's
  Levenshtein heuristic is a deliberately simpler, real, useful check (it
  genuinely catches crossed-identity-link gaps a flattened check would
  miss) but is not an implementation of the stronger literature definition.
- **Evidence** — `tests/ocel/test_object_centric_conformance_chicago.py`
  (4 tests, all still passing after the docstring correction — no behavior
  changed).

## 7. Cross-reference: the already-disclosed CLI metric-swap defect

Not a new finding — recorded here because it's exactly the kind of defect
this audit's method is designed to catch, and it was already caught and
fixed forward before this audit ran. `src/autofde_lab/ocel/level4_process_fitness.py`
(lines ~45-58) documents that `wpm mining discover`'s own CLI mislabels its
printed metrics — the row printed "Simplicity" is really token-replay
fitness, and "Fitness (self)" is really precision, a tuple-destructuring
bug in `wasm4pm-cli/src/commands/mining.rs:111` — already pinned by
`golden_model_metric_swap_witness()` (lines 289-304) as a permanent
regression fixture. Confirmed still present and still correctly named,
unchanged by this audit.

## 8. "wasm4pm" as a term

`"wasm4pm"` is this user's own private, local sibling repository
(`~/wasm4pm`), not a term with independent existence in the public pm4py or
process-mining literature (confirmed via web search this session — no
hits). This is expected, not a defect; noted so a future reader doesn't go
looking for it externally. The real, public WASM-in-process-mining project
that does exist is **Rust4PM** (CEUR-WS Vol-3758), a separate, unrelated
Rust process-mining library that exposes functions via WebAssembly for
in-browser use; pm4py optionally uses a Rust4PM-based importer (`rustxes`)
for fast XES/OCEL 2.0 import. `wasm4pm` (this user's repo) is not derived
from or related to Rust4PM as far as this audit found.

## Summary table

| # | Claim | Verdict |
|---|---|---|
| 1 | ILP Petri-net discovery | `NO_DIRECT_PM4PY_EQUIVALENT` |
| 2 | Token-replay fitness formula | `CONSISTENT_BUT_EXTERNALLY_COMPUTED` |
| 3 | ETConformance precision | `CONSISTENT_BUT_EXTERNALLY_COMPUTED` |
| 4 | Token-based generalization | `CONSISTENT_BUT_EXTERNALLY_COMPUTED` |
| 5 | Concept-drift detection | `DIVERGENT` — corrected this session |
| 6 | Object-centric conformance naming | `DIVERGENT` — corrected this session |
| 7 | CLI metric-swap defect | Already disclosed, confirmed unchanged |
| 8 | "wasm4pm" as a public term | Not applicable — private repo name |

Standing (per `.claude/rules/standing-law.md`): the correctness of claims
1-4 and 7-8 is `PARTIAL_ALIVE` — checked at the citation/definition level
this session, with the actual computation running in an external binary
never independently re-run here. Claims 5 and 6 were `DIVERGENT` and are
now corrected in place (docstring-only changes, no algorithm rewritten) —
their standing after correction is `ALIVE` for "the documentation now
accurately describes what the code does," not for "the underlying
algorithm was proven correct," which remains out of scope for a
documentation audit.

## Addendum (2026-08-12, same day) — real upstream fixes landed in `~/wasm4pm`

Following this audit, the user asked for wasm4pm itself to be corrected
where real, bounded defects were found. Real, committed changes in
`~/wasm4pm` (all built and tested there — `cargo check`/`cargo test`
across `wasm4pm`, `wasm4pm-cli`, and `algorithm_paper_grounded`, 939 lib +
15 CLI + 97 paper-grounded tests, 0 failures at time of writing):

- **Fixed**: `conformance.rs`'s stale doc comment now matches the real,
  already-correct executed fitness formula.
- **Fixed**: `prediction_drift.rs`'s `DriftPoint.position` — was
  `idx * window_size` against an overlapping sliding window, now the
  correct `idx`.
- **Fixed**: `detect_drift.json`'s false `"extraction": "verbatim"`
  provenance claim, corrected to `"computed"` with an honest note.
- **Fixed**: `ilp_discovery.rs`'s real, live version of the CLI
  fitness/precision/simplicity metric-swap defect `level4_process_fitness.py`
  already disclosed (confirmed live in `crates/wasm4pm-cli/src/commands/mining.rs`
  at its current line numbers, not the original stale reference) — the CLI
  now reports three real, distinct, correctly-labeled values.
- **Built (new)**: `detect_drift_ks_native` — a real, separate
  implementation of Bose et al. (2011)'s actual Section 3 method (windowed
  J-measure feature extraction + two-sample Kolmogorov-Smirnov test, Massey
  1951 critical values), exposed via `wpm mining drift --method ks-test`,
  additive alongside the existing Jaccard/TV heuristic.
- **Built (new)**: a real 0/1 ILP solve (`ilp_exact_cover`, via
  `good_lp`'s pure-Rust `microlp` backend) replacing the greedy heuristic
  as `discover_ilp_petri_net`'s primary selection path — genuinely finds
  the minimum-cardinality cover now, with the greedy heuristic kept as a
  disclosed fallback.
- **Built (new)**: `oc_conformance_check_inner` now does real
  per-object-type token-based replay (`conformance::token_replay_pure`,
  reusing the corrected formula above) plus a real, new event-to-object
  cardinality-deviation check — replacing the old "activity name merely
  present in the discovered net" membership check with something closer to
  the real academic definition audited in §6 above. Still a self-referential
  (discovered-then-checked) baseline, not independently validated — named
  as such in the module's own docstring, matching this crate's established
  disclosure pattern.

**Not done, named as a real, bounded gap**: this repo's own
`wasm4pm_bridge.py` was **not** extended to call the new
`--method ks-test` CLI path — its `detect_drift()`/`_DRIFT_ROW` regex
targets the old Jaccard/TV table shape only. A `detect_drift_ks` bridge
function with its own parser/dataclass is real, useful follow-up work, not
yet built.

An unrelated, real environmental finding from this pass, worth recording:
`~/wasm4pm`'s `main` branch had concurrent, unrelated PR merges landing
during this session (visible in `git log`), and something in that
environment periodically hard-resets the working tree to match — silently
discarding uncommitted edits. Every fix above was committed to git
immediately after being written and verified, specifically to survive
that; anyone continuing this work in `~/wasm4pm` should commit
frequently rather than batching changes.

## See also

- `src/autofde_lab/ocel/wasm4pm_bridge.py` — the corrected module.
- `src/autofde_lab/ocel/object_centric_conformance.py` — the corrected module.
- `src/autofde_lab/ocel/level4_process_fitness.py` — the pre-existing,
  already-disclosed CLI metric-swap defect this audit's correction style
  matches.
- `~/gymact/docs/2026-08-12-gymact-ocel-analysis-implementation-plan-part2.md`
  — the real, already-executed pm4py cross-check cited as evidence in §6,
  including its own real self-correction of an earlier overstated doctrine
  claim about wasm4pm's scope.
- `.claude/rules/standing-law.md` — the status vocabulary this audit uses.
