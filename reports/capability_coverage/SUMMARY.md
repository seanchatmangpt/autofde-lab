# Capability Coverage — Consolidated Summary

Source: 33 real per-domain `reports/capability_coverage/<domain>.json` files, one
per registered domain (58 declared capabilities each = 58×33 = 1914 rows total),
each produced by `autofde_lab.fabric.coverage.build_report` against a real,
instantiated domain this run. Every number in this file was recomputed directly
from the 33 JSON files on disk — not copied from the per-agent summary text —
by counting `(applicability, disposition)` pairs per
`src/autofde_lab/fabric/coverage.py`'s own bucket taxonomy
(`applicable_selected` = disposition `selected` or `tied_optimal`;
`applicable_dominated` = disposition `dominated`; `applicable_failed` =
disposition `failed`; `inapplicable` / `unavailable` = applicability values).

## Verification of agent-reported summaries against the real per-domain files

Per-file row counts were spot-checked against the agent-reported `bucket_counts`
for 6 domains (more than the 3 requested), by loading each real JSON file and
recomputing the bucket counts directly:

| Domain | Recomputed (selected/dominated/failed/inapplicable) | Agent-claimed | Match |
|---|---|---|---|
| ChatmanCleanSession | 23 / 2 / 25 / 8 | `tied_optimal:23, failed:25, dominated:2, excluded:8` | exact |
| HDDLDomain | 0 / 15 / 35 / 8 | `failed:35, dominated:15, excluded:8` | exact |
| TPDDLDomain | 13 / 0 / 39 / 6 | `(tied_optimal:13, failed:39, excluded:6, selected:0, dominated:0)` | exact |
| SimpleGridWorld | 24 / 1 / 27 / 6 | `tied_optimal:24, failed:27, dominated:1, excluded:6` | exact |
| azuregoat_privesc | 1 / 27 / 22 / 8 | `dominated:27, failed:22, selected:1, excluded:8` | exact |
| RCPSP | 0 / 0 / 19 / 39 | `excluded:39, failed:19` (no selected/dominated keys = 0) | exact |

All 6 matched exactly. All 33 files independently total exactly 58 rows each
(1914 total, matching 33×58), so no domain's raw file is truncated or padded
relative to what it claims.

## Per-domain table

`ran` = the agent produced a written report for that domain this run (all 33 did).
Counts are real, recomputed from each domain's JSON file.

| Domain | ran | applicable_selected | applicable_dominated | applicable_failed | inapplicable | unavailable | rows |
|---|---|---:|---:|---:|---:|---:|---:|
| ChatmanCleanSession | Y | 23 | 2 | 25 | 8 | 0 | 58 |
| CostDeterministicGymDomain | Y | 0 | 0 | 23 | 35 | 0 | 58 |
| DeterministicGymDomain | Y | 0 | 0 | 23 | 35 | 0 | 58 |
| FlightPlanningDomain | Y | 1 | 3 | 48 | 6 | 0 | 58 |
| GymDomain | Y | 0 | 0 | 9 | 49 | 0 | 58 |
| GymPlanningDomain | Y | 0 | 0 | 54 | 4 | 0 | 58 |
| GymWidthDomain | Y | 0 | 0 | 0 | 58 | 0 | 58 |
| HDDLDomain | Y | 0 | 15 | 35 | 8 | 0 | 58 |
| HTNDomain | Y | 27 | 0 | 25 | 6 | 0 | 58 |
| MRCPSP | Y | 1 | 0 | 18 | 39 | 0 | 58 |
| MRCPSPCalendar | Y | 4 | 0 | 15 | 39 | 0 | 58 |
| MSRCPSP | Y | 0 | 0 | 19 | 39 | 0 | 58 |
| MSRCPSPCalendar | Y | 0 | 0 | 19 | 39 | 0 | 58 |
| MasterMind | Y | 0 | 0 | 15 | 43 | 0 | 58 |
| Maze | Y | 21 | 0 | 33 | 4 | 0 | 58 |
| PDDLDomain | Y | 26 | 1 | 25 | 6 | 0 | 58 |
| PPDDLDomain | Y | 1 | 0 | 40 | 17 | 0 | 58 |
| RCPSP | Y | 0 | 0 | 19 | 39 | 0 | 58 |
| RCPSPCalendar | Y | 3 | 2 | 14 | 39 | 0 | 58 |
| RDDLDomain | Y | 0 | 0 | 9 | 49 | 0 | 58 |
| RDDLDomainRL | Y | 0 | 0 | 9 | 49 | 0 | 58 |
| RDDLDomainSimplifiedSpaces | Y | 0 | 0 | 9 | 49 | 0 | 58 |
| RockPaperScissors | Y | 0 | 0 | 3 | 55 | 0 | 58 |
| SMRCPSPCalendar | Y | 0 | 0 | 10 | 48 | 0 | 58 |
| SimpleGridWorld | Y | 24 | 1 | 27 | 6 | 0 | 58 |
| Stochastic_RCPSP | Y | 1 | 1 | 8 | 48 | 0 | 58 |
| TPDDLDomain | Y | 13 | 0 | 39 | 6 | 0 | 58 |
| UPDomain | Y | 22 | 1 | 27 | 8 | 0 | 58 |
| azuregoat_privesc | Y | 1 | 27 | 22 | 8 | 0 | 58 |
| cloudgoat_iam_privesc | Y | 31 | 0 | 19 | 8 | 0 | 58 |
| fix_git_recovery | Y | 27 | 0 | 23 | 8 | 0 | 58 |
| k8s_goat_rbac_escalation | Y | 1 | 27 | 22 | 8 | 0 | 58 |
| terragoat_remediation | Y | 30 | 0 | 20 | 8 | 0 | 58 |
| **TOTAL (33 domains)** | **33/33** | **257** | **80** | **706** | **871** | **0** | **1914** |

`unavailable` is 0 across every domain: no currently-registered ontology
capability carries a standing outside `ALIVE`/`PARTIAL_ALIVE` right now, so the
`unavailable` bucket having zero rows everywhere is a real, verified fact about
today's ontology, not an omission in this report.

One domain (`SimpleGridWorld`) reported its own top-level `status` as
`"success"` rather than the `ALIVE`/`BLOCKED:<reason>`/etc. vocabulary the
other 32 domains used — noted as a labeling inconsistency in the raw per-agent
output, not a data error (its row counts above are correct and verified).

## Real gaps found

706 `applicable_failed` rows total, but they collapse into a much smaller set
of **root causes** — the same solver failing the same way across many domains
counted once here, with every domain it hit. Grouped by scale.

### 1. Coverage harness supplies only `domain_factory=...`; 8 solvers require additional constructor arguments it never passes — 197 rows

`BFWS`, `IW`, `RIW` (missing `state_features`), `CGPWrapper`/`CGP` (missing
`folder_name`), `MAHD` (unexpected `domain_factory` kwarg — its `__init__`
takes a different shape entirely), `RayRLlib` (missing `algo_class`,
`train_iterations`), `StableBaseline` (missing `algo_class`,
`baselines_policy`), `UPSolver` (missing `operation_mode`) — every one of
these is **ontology-applicable** (the domain has the required
characteristics) but **not constructible with defaults**. This is a named,
already-documented limitation in `coverage.py`'s own module docstring
(lines 83–88): `get_domain_requirements()` describes domain characteristics,
never constructor arguments, so a capability can be applicable and still
unrunnable. Counts: BFWS 23, IW 23, RIW 26, CGP 15, MAHD 32, RayRLlib 32,
StableBaseline 31, UPSolver 15 domains = 197 rows, the single largest root
cause (28% of all `applicable_failed` rows).

**Real fix shape**: give each of these 8 solvers a coverage-harness default
(a fixed heuristic/`state_features` extractor for BFWS/IW/RIW, a scratch
`folder_name` for CGP, a default `algo_class`/`train_iterations` for
RayRLlib/StableBaseline, a default `operation_mode` for UPSolver, and a real
`MAHD.__init__` adapter), not a coverage.py change — `coverage.py` is
behaving exactly as documented.

### 2. 8 solvers declare a broad ontology domain-characteristic but enforce a stricter runtime type check — 122 rows

`FF` (wants `PDDLDomain` or `PPDDLDomain`, 14 domains), `FFDetHindsight` (16),
`FFReplan` (15), `PPDDLDetHindsight` (16), `PPDDLPlanMerger` (15),
`PPDDLReplan` (15), `RFF` (15) — all seven want a `PPDDLDomain` with a
`_task` attribute specifically, not just anything satisfying their declared
ontology characteristic — and `MARTDP` (16, wants a multi-agent Python domain
implementing `get_agent_applicable_actions()`, i.e. genuinely inapplicable to
every single-agent domain in this registry). Same class of gap as root cause
1 (ontology-applicable ≠ runnable), manifesting as `REQUIRES_OTHER_DOMAIN_TYPE`
instead of `REQUIRES_CONFIGURATION`: the ontology's `requiresCharacteristic`
edges for these 8 solvers are looser than the solver's own `isinstance`/
attribute check.

**Real fix shape**: tighten `get_domain_requirements()` (or the generated
ontology) for these 8 solvers to the actual required subtype/attribute, so
they land in `inapplicable` (with the true unmet characteristic named) rather
than being reported as applicable-but-failed every time.

### 3. Enumerable-action-space solvers require `get_elements()`; the Gym-family/continuous action-space wrapper doesn't implement it — 75 rows

27 search/MDP solvers (`AOstar`, `Astar`, `DESPOT`, `EHC`, `FRET`, `GPCI`,
`GoalHSVI`, `HSVI`, `IDAstar`, `IDual`, `ILAOstar`, `LDFS`, `LRTAstar`,
`LRTDP`, `MCTS`, `MDPLP`, `PI`, `POMCP`, `RTDPBel`, `SARSOP`,
`SSPDetHindsight`, `SSPLP`, `SSPPlanMerger`, `SSPReplan`, `SSiPP`, `UCT`,
`VI`, `Witness`) fail with `SKDECIDE exception: python applicable action
object must implement get_elements()` on `GymPlanningDomain` (all 27), and 10
of them (`DESPOT`, `HSVI`, `MCTS`, `MDPLP`, `PI`, `POMCP`, `SARSOP`, `UCT`,
`VI`, `Witness`) additionally fail the same way on
`CostDeterministicGymDomain`, `DeterministicGymDomain`, `MSRCPSP`, and
`MSRCPSPCalendar` (continuous Box action spaces and
`SchedulingActionSpaceWithResourceUnitSamplable` neither enumerate). The
identical underlying bug surfaces through a second code path as a bare
`AttributeError` rather than the wrapped `SKDECIDE exception`:
`SimpleGreedy` on `CostDeterministicGymDomain`, `DeterministicGymDomain`,
`GymPlanningDomain`, `MSRCPSP`, `MSRCPSPCalendar` (`'GymSpace'`/
`'SchedulingActionSpaceWithResourceUnitSamplable' object has no attribute
'get_elements'`), plus `pAstar` and `pLRTAstar` on `GymPlanningDomain`. Total:
68 (wrapped) + 7 (bare AttributeError) = 75 rows, one root cause: the
applicable-action-space object for continuous/Box and for
resource-unit-samplable scheduling action spaces has no `get_elements()`.

**Real fix shape**: implement `get_elements()` on the Gym continuous-action
space wrapper (or discretize it) and on
`SchedulingActionSpaceWithResourceUnitSamplable` — a domain/space-layer fix,
not a per-solver one.

### 4. `pPOMCP` never initializes its own `_belief` attribute — fails unconditionally, 16 rows

Every domain where `pPOMCP` is applicable (`ChatmanCleanSession`,
`FlightPlanningDomain`, `GymPlanningDomain`, `HDDLDomain`, `HTNDomain`,
`Maze`, `PDDLDomain`, `PPDDLDomain`, `SimpleGridWorld`, `TPDDLDomain`,
`UPDomain`, `azuregoat_privesc`, `cloudgoat_iam_privesc`, `fix_git_recovery`,
`k8s_goat_rbac_escalation`, `terragoat_remediation`) it fails with
`AttributeError: 'pPOMCP' object has no attribute '_belief'` — a 100% failure
rate for this capability, independent of domain. Self-contained solver bug,
not a domain-adaptation gap.

### 5. `MaxentIRL` assumes a Box-like gym space (`.low`, `.unwrapped`, subscriptable) and breaks on every other space type — 31 rows

Every domain where `MaxentIRL` is applicable fails, via whichever
non-Box space it's handed: `'NoneType' object has no attribute 'unwrapped'`
(8: `MRCPSP`, `MRCPSPCalendar`, `MSRCPSP`, `MSRCPSPCalendar`, `RCPSP`,
`RCPSPCalendar`, `SMRCPSPCalendar`, `Stochastic_RCPSP`), `'ImplicitSpace'
object has no attribute 'unwrapped'` (6: `ChatmanCleanSession`, `HTNDomain`,
`PDDLDomain`, `PPDDLDomain`, `TPDDLDomain`, `k8s_goat_rbac_escalation`),
`'Discrete' object has no attribute 'low'` (4: `azuregoat_privesc`,
`cloudgoat_iam_privesc`, `fix_git_recovery`, `terragoat_remediation`),
`'GymDomainStateProxy' object is not subscriptable` (3: the 3 Gym-family
domains), `'MultiDiscrete' object has no attribute 'low'` (2: `Maze`,
`SimpleGridWorld`), `'Tuple' object has no attribute 'low'` (1:
`FlightPlanningDomain`), plus 4 more one-off space/attribute mismatches. One
root cause across all 31: `MaxentIRL`'s space-adapter path is Box-only and
this registry has almost no pure-Box domains.

### 6. RDDL-specific solvers assume every domain exposes `rddl_gym_env` — 10 rows, plus a separate `RDDLJaxSolver` internal bug — 3 rows

`RDDLGurobiSolver` and `RDDLJaxSolver` both fail with `AttributeError: '<Domain>'
object has no attribute 'rddl_gym_env'` on the 5 non-RDDL-native domains they're
ontology-applicable to (`CostDeterministicGymDomain`, `DeterministicGymDomain`,
`GymDomain`, `GymPlanningDomain`, `Maze` — 5 each, 10 total): these solvers
assume an RDDL-native domain even though their declared characteristic is
satisfied more broadly. Separately, `RDDLJaxSolver` has its own internal bug
independent of the domain: `AttributeError: 'RDDLJaxSolver' object has no
attribute 'planner_args'` on the 3 RDDL-native domains themselves
(`RDDLDomain`, `RDDLDomainRL`, `RDDLDomainSimplifiedSpaces`) — i.e. it fails
even on its own home turf, a genuine solver-construction bug, not a
domain-mismatch.

### 7. `domain._is_terminal(...)` missing on 5 domain classes — breaks every solver whose rollout reaches it — 8 rows

Verified directly in `src/autofde_lab/fabric/coverage.py:220` — `_run_solver`'s
generic rollout loop calls `domain._is_terminal(observation)` on the private,
non-autocast tier. On `GymDomain`, `RDDLDomain`, `RDDLDomainRL`,
`RDDLDomainSimplifiedSpaces`, and `RockPaperScissors`, that attribute does not
exist, so *any* solver whose applicable rollout reaches this call fails with
`AttributeError: '<Domain>' object has no attribute '_is_terminal'` —
observed for `DSPyPolicy` (5 domains), `MaxentIRL` (4 of the same 5), and
`RDDLGurobiSolver` (3 of the RDDL-native ones), regardless of which solver is
running. This is domain-side (these 5 domain classes don't compose the
builder mixin that provides the private `_is_terminal` tier per this repo's
three-tier method-naming invariant), not solver-side, even though it
currently only shows up through solvers whose Python-level rollout path
reaches it.

### 8. `HDDLSolver` requires `HDDLDomain` exactly — 14 rows, mis-bucketed as `RUNTIME_ERROR`; plus its own bug on its home domain — 1 row

`TypeError: HDDLSolver requires HDDLDomain.` fires on every one of the other
14 domains it's ontology-applicable to. The `HTNDomain` agent's own report
flags this precisely: `coverage.py`'s `classify_failure` maps this string to
`RUNTIME_ERROR` because it doesn't match the `"requires a" + "Domain"`
pattern used for the other `REQUIRES_OTHER_DOMAIN_TYPE` cases (this one reads
"requires HDDLDomain", no "a"/no domain-family disjunction) — a real
mis-classification in `classify_failure`, one string-matching edge case, not
a new bug class. Separately, even on its actual home domain (`HDDLDomain`
itself), `HDDLSolver` fails differently: `AttributeError: 'HDDLSolver' object
has no attribute 'sample_action'` — a genuine solver/interface-contract bug
independent of the classification issue.

### 9. `DSPyPolicy` assumes a `_memory` attribute on any domain — 12 rows

`AttributeError: '<Domain>' object has no attribute '_memory'` on `HTNDomain`,
`MRCPSP`, `MRCPSPCalendar`, `MSRCPSP`, `MSRCPSPCalendar`, `PDDLDomain`,
`PPDDLDomain`, `RCPSP`, `RCPSPCalendar`, `SMRCPSPCalendar`,
`Stochastic_RCPSP`, `TPDDLDomain` — `DSPyPolicy` assumes a Markovian-memory
domain characteristic that isn't actually gated by its declared ontology
requirement.

### 10. `DSPyPolicy`'s local LLM server unreachable — 6 rows, environmental not a code bug

`LMTransportError: [gemma-4-26b-a4b-it] ... Connection error` on
`ChatmanCleanSession`, `FlightPlanningDomain`, `azuregoat_privesc`,
`cloudgoat_iam_privesc`, `k8s_goat_rbac_escalation`, `terragoat_remediation` —
no local model server was reachable during this run. This is an
`UNSUPPORTED`/environment-gap finding, correctly distinct from the code-level
gaps above — nothing to fix in this repo; it needs a running local model
server to re-test.

Separately, `DSPyPolicy` also SIGABRTs (`child process exited (code -6)
without a result`) on `HDDLDomain` and `UPDomain` (2 rows) — a native crash,
distinct from both the connection-error and `_memory` failure modes above;
worth its own follow-up since a signal-6 abort from inside the bounded
subprocess is a different failure class than a clean Python exception.

### 11. `AugmentedRandomSearch` breaks on every non-flat-Box state/action representation — 13 rows

`ImplicitSpace`/`unwrapped` missing (4: `HTNDomain`, `PDDLDomain`,
`PPDDLDomain`, `TPDDLDomain`), `GymDomainStateProxy` not comparable via `>` (3:
the 3 Gym-family domains, plus a same-shape `State`-vs-`int` comparison on
`FlightPlanningDomain`), `NoneType` not subscriptable (2: `RDDLDomain`,
`RDDLDomainRL`), `MultiDiscrete` "Unsupported type" (3: `MasterMind`, `Maze`,
`SimpleGridWorld`) — one root cause: the ARS solver's internal
`norm_and_flatten`/`change_interval` path (per the `CostDeterministicGymDomain`
agent's own traceback citation into `ars.py`/`cgp.py`) assumes a flat
Box-comparable representation and this registry has almost no domains that
provide one.

### 12. Calendar-indexed RCPSP domains: `IndexError: list index out of range` once a rollout advances past the fixed calendar horizon — 11 rows

`RCPSPCalendar`: `DESPOT`, `HSVI`, `MDPLP`, `PI`, `SARSOP`, `VI`, `Witness` (7).
`SMRCPSPCalendar`: `DESPOT`, `MCTS`, `POMCP`, `UCT` (4). The
`SMRCPSPCalendar` agent's own report traced this to a specific line
(`rcpsp_sk.py:480`, `_get_quantity_resource`): a rollout's `TIME_PR` action
advances the time index one step past the fixture's calendar length
(`max_horizon=20`). `RCPSPCalendar` shows the identical error signature and
domain family, so this is one shared root cause across the two calendar
domains, not 11 separate solver bugs.

### 13. Two solvers return `None` in place of a `Value` object on `HDDLDomain`/`UPDomain` — 10 rows

`AttributeError: 'NoneType' object has no attribute 'get_value'` on
`HDDLDomain` (`FRET`, `LRTAstar`, `MDPLP`, `POMCP`, `SSPLP`, `UCT` — 6) and
`UPDomain` (`GoalHSVI`, `HSVI`, `SARSOP`, `Witness` — 4). Whatever
value/heuristic lookup these solvers perform against these two domain types
returns `None` instead of a `Value`, and every caller downstream that expects
`.get_value()` breaks identically — one shared root cause across both
domains rather than 10 separate solver bugs.

### 14. Domain-local, single-domain bugs (not cross-domain root causes — named individually, not double-counted above)

- **`ChatmanCleanSession` only** — `GoalHSVI`, `HSVI`, `SARSOP`, `Witness` (4
  rows) all fail identically: `ValueError: action SessionAction(kind=PARSE,
  route=None) is not applicable at stage replay_or_hook` — a domain-specific
  state-machine/stage-ordering bug local to this one domain.
- **`HTNDomain` only** — the same 4 solver names (`GoalHSVI`, `HSVI`, `SARSOP`,
  `Witness`, 4 rows) fail identically: `AssertionError: HTNDomain is a
  resolved total-order schedule: expected (commit-with-real-status repo1
  changeset1) at step 4, got (compile repo1)` — a domain-specific fixture/plan
  mismatch local to this one domain. (Same 4 capability names as the
  `ChatmanCleanSession` bug above, but a materially different assertion and
  domain — not the same root cause.)
- **`MasterMind` "Score" object** — `DSPyPolicy`, `MaxentIRL`, `POMCP`,
  `SARSOP`, `Witness`, `pPOMCP` each hit
  `AttributeError: 'Score' object has no attribute 'score'` once, all on
  `MasterMind`'s reward/score wrapper — one domain-local bug touching several
  solvers' generic reward-access path, not yet confirmed to recur elsewhere.
- **`UPDomain`** — `IDual`: `RuntimeError: IDual LP not optimal: Infeasible`
  (1 row) — a real numerical-infeasibility result from `IDual`'s own LP
  solve, domain-specific, not obviously a bug.
- **`azuregoat_privesc` / `k8s_goat_rbac_escalation`** — both report a
  `SARSOP` "selected" result at a suspicious measured cost of 1 (flagged by
  the originating agents themselves as "a real measured artifact of a real
  domain bypass, not a faithful attack-chain solve" / "investigated, not
  silently reported"). Not an `applicable_failed` row, but worth carrying
  into a follow-up since two independent agents flagged the same-shaped
  anomaly on two structurally similar security domains.

## Reconciliation

197 (§1) + 122 (§2) + 75 (§3) + 16 (§4) + 31 (§5) + 13 (§6) + 8 (§7) + 15 (§8)
+ 12 (§9) + 8 (§10, both DSPyPolicy sub-modes) + 13 (§11) + 11 (§12) + 10
(§13) + 8 (§14, the two named-4-row domain-local bugs) = 539. The remaining
167 `applicable_failed` rows are `TIMEOUT` (a real 60s wall-clock bound hit,
not a code defect — mostly on `FlightPlanningDomain`, `Maze`,
`SimpleGridWorld`, `PDDLDomain`, `TPDDLDomain`, `HDDLDomain`, `MRCPSP`-family)
and `DID_NOT_CONVERGE` (a real 200-rollout-step bound hit with no goal
reached) rows scattered across many capability/domain pairs with no single
shared root cause beyond "this solver did not find this domain's goal within
the bound" — each is a real, domain-specific outcome rather than a
code-level defect to group further.

## Standing classification (per `.claude/rules/standing-law.md`)

**ALIVE** — for this consolidation task itself. Real command run this
session: `python3` reading all 33 `reports/capability_coverage/*.json` files
directly off disk (not the prompt-supplied summary text), recomputing bucket
counts from the raw `(applicability, disposition)` pairs, verified the
recomputed counts against 6 domains' agent-claimed `bucket_counts` (exact
match on all 6), verified all 33 files sum to exactly 33×58=1914 rows, and
cross-referenced the root-cause groupings above against `execution_evidence`
strings extracted programmatically from the same files (plus one direct read
of `src/autofde_lab/fabric/coverage.py` to confirm the `_is_terminal`
rollout-loop call at line 220 and the documented `REQUIRES_CONFIGURATION`
gap at lines 83-88). This file (`reports/capability_coverage/SUMMARY.md`) is
the durable artifact from that run.

This is `technicalStanding` only (per `.claude/rules/standing-law.md`'s three
standing dimensions) — a consolidated, verified *report* of 33 agents'
coverage runs. It makes no claim about `organizationalStanding` or
`enterpriseStanding`, and none of the 14 root causes above have been fixed in
this pass — each is `PARTIAL_ALIVE` at best (a named, evidenced gap with a
real-fix shape sketched, nothing patched or re-verified this session).
