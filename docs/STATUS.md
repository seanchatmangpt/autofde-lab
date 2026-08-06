# STATUS — the standing dispatch for WIP closure

Filed at the close of each closure pass. Where this sheet and the code disagree, the code is
the witness that's still alive — the sheet gets corrected to match it, not the other way
around. Every line below is either a measured win (command run, output checked, in this
session) or a recorded negative (attempted, blocked, reason named) — no self-graded claims.

Last update: **pass 2** (2026-08-06) — ecosystem-scope pass; see below. Pass 1 remains as
filed.

Scope note: this sheet ledgers WIP **inside this repository**. Cross-repository standing
(`~/mfw`, `~/ggen`, `~/ggen-create`, `~/ggen-legacy`, `~/bcinr`) is ledgered separately in
`docs/ecosystem-standing.md`, same discipline, wider blast radius. Don't merge the two — a
green row here says nothing about whether a consequence closes across the portfolio.

## Pass 2 — ecosystem closure ledger (2026-08-06)

| Item | State | Witness |
|---|---|---|
| Classical PDDL engine for `~/mfw`'s external-engine seam | **measured win** | `uv run python -m skdecide.fabric.pddl_engine tests/domains/python/pddl_domains/blocks/{domain,probBLOCKS-3-0}.pddl /tmp/blocks.plan` → `plan found, 4 step(s), cost 4`; file contains `(unstack a b) … ; cost = 4 (unit cost)`, matching the shape of the committed `~/mfw/runs/ticket-10/work/candidate.plan`. Satisfies the `classical`+`file` contract in `mfw-planner/src/config.rs`. |
| Refusal of parsed-but-unimplemented PDDL requirements | **measured win** | Engine exits `2` with `UNSUPPORTED_REQUIREMENT: :derived-predicates,:constraints,:preferences` on `~/ggen-legacy/planning/v26.8.1/domains/ggen-v2681-core.pddl`. `grep -rn "derived" cpp/src/hub/domain/pddl/semantics/` → **zero hits**: derived atoms are never true and nothing raises, so the alternative was a confident wrong plan. That corpus's `admit-sunset` is gated on the derived predicate `sunset-safe`, i.e. it would have been silently unreachable. |
| POWL2 projection with real blake3 | **measured win** | `mfwp:domainDigest "blake3:b11c0b44…"` cross-checked against an independent `b3sum` in `tests/ecosystem/`. Projector raises `DigestUnavailable` rather than emitting another algorithm under a `blake3:` label. **Scope: projection, not execution.** |
| Capability ontology, generated not curated | **measured win** | `python -m skdecide.fabric.ontology ontology/skdecide-capabilities.ttl` → 83 capabilities (26 domains, 57 solvers) + 16 PDDL requirements, 4 `UNSUPPORTED`. `tests/ecosystem/` asserts it matches the live registry exactly and that every solver's requirements equal its `get_domain_requirements()` derivation. |
| Capability-coverage completeness | **measured win** | All 57 solvers classified against `CareerAdmission`: 26 `tied_optimal` (cost 3), 8 `excluded` (`UNMET_DOMAIN_CHARACTERISTICS`), 23 `failed` (`REQUIRES_OTHER_DOMAIN_TYPE` 8, `REQUIRES_CONFIGURATION` 7, `DID_NOT_CONVERGE` 5, `RUNTIME_ERROR` 3). Comparison is measured by running them, because `match_solvers(ranked=True)` ignores the flag (`utils.py:126`). |
| Crown + unit suites | **measured win** | `uv run pytest tests/ecosystem/ tests/domains/python/test_career_admission_unit.py` → **27 passed**. |
| Prior "Chicago" career test demoted | **measured win, correction** | `test_career_admission_chicago.py` → `test_career_admission_unit.py` with an explicit scope warning. It exercised one solver against one local in-repo domain and touched no sibling repo; citing it as ecosystem evidence was the error, not the test itself. |
| Whole-suite collection | **recorded negative, unchanged** | `uv run pytest tests --collect-only -q` still errors on the same 4 files (`tests/solvers/python/test_pomcp.py` basename collision + 3 `_dspy_*_chicago.py` import failures). Re-verified 2026-08-06; the new suites collect and pass by path. |
| `~/mfw` engine admission end-to-end | **recorded negative** | `cargo build -p mfw-planner` → `BUILD_BROKEN`. Chain: `mfw-planner → mfw-shacl → praxis-graphlaw → bcinr-powl-receipt`, and `/Users/sac/bcinr/crates/bcinr-powl-receipt` does not exist (the dir has `bcinr-powl`). Referenced by absolute path at `praxis-graphlaw/Cargo.toml:41`. Diagnosed further in `docs/ecosystem-standing.md` RP-2: the crate was **renamed** into `bcinr-powl::receipt` (commit `251f3af5`), `26.7.28` is still unyanked on crates.io, so this is a one-line dep fix — but the durable defect is the absolute `/Users/sac/...` path, which is why CI never saw it. Consequence: the engine's *contract conformance* is tested; its *admission through mfw's own gate* is not. Weaker, and labelled as such. |
| Planning over `~/ggen-legacy`'s corpus | **recorded negative** | `UNSUPPORTED:derived-predicates,constraints,preferences`. Parsing that corpus for the first time also surfaced two latent defects its only checker (a paren-balance/substring script) cannot detect: `ggen-v2681-core.pddl@50:29` `?x` unknown inside a `:derived` body, and `10-legacy-sunset.pddl@5:3` redeclaring `preserved`, which the domain already declares in `(:constants …)`. |

Pass 2 commit: `7972046` on `chore/close-wip-chicago-tests`, not pushed.

## Pass 1 — closure ledger

| Item | State | Witness |
|---|---|---|
| `core.py` `DiscreteDistribution` population dedup | **measured win** | `uv run pytest tests/test_core_distribution.py -v` → 4 passed. Duplicate members now aggregate weight instead of one silently winning. |
| `graph_domain` dedicated test | **measured win** | `uv run pytest tests/domains/test_graph_domain.py -v` → 19 passed. Module previously had no test of its own — only touched incidentally via scheduling/GNN solver tests. |
| `pddl.py` stale "TODO: finish work in progress" | **measured win, comment removed** | `uv run pytest tests/solvers/python/test_pddl_ff.py tests/solvers/python/test_pddl_determinization.py tests/domains/python/test_pddl_domain.py -v` → 59 passed. The module is a functioning `__all__` re-export around the bound C++ parser; the comment predated evidence of the gap it claimed. |
| Solver-callback blanket skip (`test_python_solvers.py:205`) | **measured, no change needed** | `uv run pytest tests/solvers/python/test_python_solvers.py -k with_cb -v` → 3 passed, 1 failed. All 4 parametrized solvers (pAstar, pLRTAstar, RayRLlib, StableBaseline) already implement `callback` in `__init__`; the skip never fires. The 1 failure is a pre-existing Ray/DQN incompatibility (`TypeError: argument of type 'ABCMeta' is not iterable` inside ray's own `algorithm.py`) — unrelated to callback wiring, left unfixed, named here rather than silently absorbed into "done." |
| Flight-planning propulsion acceleration (`_poll_schumann_propulsion_service.py:69`) | **recorded negative** | `AircraftState` carries no velocity history or previous-state reference, and `compute_total_net_thrust_n`'s signature takes only a single snapshot — `dv/dt` cannot be computed without threading a new state/velocity-history contract through the interface and both implementations first. `dv_dt=0.0` also matches Poll-Schumann's published quasi-steady-flight assumption, so the TODO may be describing an intentional simplification rather than an oversight. No code changed, no test written — a passing test here would have been fabricated. Two real unblocking paths (confirm-and-document the quasi-steady assumption, or extend the interface) are recorded, neither taken without a maintainer decision. |

Commit: `585144d` on `chore/close-wip-chicago-tests`, not yet pushed/PR'd.

## Deferred — not measured, only scoped

Four categories too large for a single closure pass got scoped follow-up plans (dependency
clusters, execution order, decision points named) written to `docs/wip-followup-plans.md`, but
**no code was run against them** — nothing in that file is a claim, only a plan:

- Scheduling mixin architecture (`builders/domain/scheduling/`, ~15 TODOs, 4 dependency
  clusters A–D)
- GNN/autoregressive vectorized-env support (`hub/solver/stable_baselines/`)
- plado/PDDL IR unimplemented branches (~15 `NotImplementedError` dispatch gaps)
- Remote-branch triage (8 `origin/*` branches not yet diffed against master — the existing
  entry in `docs/wip-followup-plans.md` is itself unmeasured, drafted from `git log` summaries
  rather than a real `git fetch` + per-branch diff)

## Intentionally out of scope, permanently

Not deferred-for-later — structurally not WIP:

- `builders/domain/*` / `builders/solver/*` abstract override points (~60+ `raise
  NotImplementedError` locations) — these are the mixin extension points concrete
  domains/solvers implement, by design (`CLAUDE.md`'s three-tier method-naming pattern).
  "Finishing" one means inventing a new concrete domain/solver nobody asked for.
- Skipped tests gated on unavailable dependencies (`z3-solver`, `optuna`, `plado`, Node.js,
  macOS `libomp` segfault) — environment gates, not incomplete work.

## How to read this

- **measured win**: a command was actually run this session, its output is quoted above, and
  it passed.
- **recorded negative**: an attempt was made, it's genuinely blocked, and the blocker is named
  precisely enough that the next pass doesn't re-discover it from zero.
- **deferred / scoped**: a plan exists; nothing under it has been executed or verified yet.
  Treat every claim inside `docs/wip-followup-plans.md` as unverified until it appears in this
  ledger with a witness.

## See also

- `docs/ecosystem-standing.md` — the cross-repository ledger (same discipline, wider scope):
  per-stage standing across `~/mfw`, `~/ggen`, `~/ggen-create`, `~/ggen-legacy`, `~/bcinr`;
  the per-transition proof that **no component executes a POWL plan end to end**; and repair
  plans RP-1…RP-7. A green row in *this* file never implies a closed cross-repo consequence.
- `.claude/rules/standing-law.md` (status vocabulary) and
  `.claude/rules/ecosystem-boundary.md` (why this repo may claim candidate plans and
  nothing further).
- `ontology/skdecide-capabilities.ttl` — generated capability graph; regenerate with
  `python -m skdecide.fabric.ontology`, never hand-edit.
