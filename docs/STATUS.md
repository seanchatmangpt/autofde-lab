# STATUS — the standing dispatch for WIP closure

Filed at the close of each closure pass. Where this sheet and the code disagree, the code is
the witness that's still alive — the sheet gets corrected to match it, not the other way
around. Every line below is either a measured win (command run, output checked, in this
session) or a recorded negative (attempted, blocked, reason named) — no self-graded claims.

Last update: **pass 4** (2026-08-06) — the FDE authority boundary named; a three-dimension
standing axis introduced; a second crown question added; RP-8 opened. Two rows in pass 4 were
executed (one measured win, one recorded negative); everything else is **deferred/scoped**.
Passes 1–3 remain as filed, with rows corrected in place rather than rewritten.
**The crown remains `BLOCKED`** — and pass 4 adds a second, independent reason it is not closed.

Scope note: this sheet ledgers WIP **inside this repository**. Cross-repository standing
(`~/mfw`, `~/ggen`, `~/ggen-create`, `~/ggen-legacy`, `~/bcinr`) is ledgered separately in
`docs/ecosystem-standing.md`, same discipline, wider blast radius. Don't merge the two — a
green row here says nothing about whether a consequence closes across the portfolio.

## Pass 4 — the FDE authority boundary (2026-08-06)

Full evidence in `docs/ecosystem-standing.md` pass 3 (that file's pass numbering trails this
one by one, as it has since pass 2). Two rows were executed; the rest is scoped only.

| Item | State | Witness |
|---|---|---|
| The sunset gate already separates technical from organizational standing | **measured win** | `~/ggen-legacy/appliance/bin/decision-engine.py` driven directly (not simulated) over four manifests with technical evidence held constant and green (`verifier.standing=ALIVE`, `replay.status=REPLAY_MATCH`, `cross_check.standing=ALIVE`, seven `capability_closure` counters zero). `release_admitted: true` in **all four**; `sunset_admitted` `true` only for boolean `true`, `false` for ABSENT / string `"true"` / `false`. Fail-closed is real: `is True` rejects a truthy string, so a config that *looks* approved is refused. **Row 1 is a control, not a success** — it shows a boolean satisfies a boolean check, not that organizational admission works. |
| autofde_lab engine admission through mfw's own gate | **recorded negative — `BLOCKED:VALIDATOR_ABSENT`** | A local, uncommitted `engines.toml` in a temp dir registered the engine in the `classical` role (venv python + `-m autofde_lab.fabric.pddl_engine`; no console script needed). `mfw-planner probe classical` → `Error: InvalidEngineConfiguration("exactly one independent validator role is required; observed 0")`. No `Validate`/`val`/`VAL` binary on this machine. mfw refuses a **planner-only** config at *config load* — anti-self-attestation is structurally enforced, not conventional. `~/mfw/mfw-planner/engines.toml` was **not** modified; the blake3 pin was never exercised (config refuses before any digest); no predicted pass is recorded. |
| RP-2's resume condition ("register in `engines.toml` with a blake3 pin") | **correction, in place** | **Necessary but not sufficient** — it omits the validator requirement. Corrected in `docs/ecosystem-standing.md` RP-2 rather than silently edited. Narrow remaining gap: obtain or build a VAL-compatible validator, register it in the `validator` role, re-probe. S2 stays `PARTIAL_ALIVE`; "the build works" must not drift into "the engine is admitted." |
| The FDE boundary is a newly-**named** gap, not a newly-**solved** one | **deferred/scoped** | Technical closure ≠ enterprise closure. Even with G1/G2/G3 closed, six customer-relative predicates stay unanswerable by the system: material completeness of the observation; whether this person holds authority; whether this system may touch that production environment; whether the implementation satisfies the actual operating obligation; whether the predecessor may be retired; whether the organization will adopt. Nothing executed. |
| New standing axis: `technicalStanding` / `organizationalStanding` / `enterpriseStanding` | **deferred/scoped** | Enterprise standing closes only when both others are admitted. **Every existing standing claim in this file and in `docs/ecosystem-standing.md` is a `technicalStanding` claim** and must not be re-read as enterprise standing — same error class as a green row here implying a closed cross-repo consequence. No component computes `organizationalStanding`; `enterpriseStanding` is unreachable by construction today. |
| Second crown question | **deferred/scoped** | Existing question is technical (blocked parent → child planned, executed, manufactured, verified, admitted, resumed without unreceipted actuation). Added: *did accountable customer authority validate the model, grant the bounded transition, accept the verified consequence, assign operating ownership, and explicitly authorize any irreversible sunset?* **Crown closed only when BOTH are yes.** The second is currently **no, and not yet even askable** — no organizational-authority rail has run. |
| RP-8 — give `customer_authorized_retirement` a referent | **deferred/scoped** | New repair plan in `docs/ecosystem-standing.md`. Scoped as *"give the existing boolean a referent"*, **not** "build an authority system" — the gate's shape is right, must be preserved and invoked, never replaced by a local simulation. Ownership note: the rail **cannot live in scikit-decide** (search graph only); this repo may at most COMPILE and CHECK an authority envelope, never mint or enforce one. Enforcement belongs to mfw's broker. RP-7 was oversized the same way in an earlier pass and had to be retracted; the correction is applied in advance. |
| New file `ontology/fde-authority-schema.ttl` | **deferred/scoped** | Hand-authored **T-Box**: 12 entities, 8 capabilities, 12 relations, 3 standing dimensions. Different **in kind** from the **generated** A-Box `ontology/skdecide-capabilities.ttl`, and its header says so — hand-authoring a *vocabulary* is legitimate; hand-authoring a *standing claim* is what the generator exists to prevent. **Nothing in it is `ALIVE`**: every capability is `UNSUPPORTED` (nothing implements it) or `UNKNOWN` (genuinely unobserved), each with an evidence string. A term existing there is not evidence anything implements it. |

Pattern worth stating once, because it changes the framing: independent verification is already
enforced at **both ends** of the chain — engine admission refuses a planner without an
independent validator, and sunset admission refuses without customer authorization. The FDE
authority boundary is the **third instance of an existing pattern**, not new architecture being
imposed.

No pytest was run in this pass (concurrent agents were editing `src/` and `tests/`); no row
above claims a test result. Pass-4 changes to this repo are documentation and one new
hand-authored ontology file.

## Pass 3 — cross-repo repair ledger (2026-08-06)

| Item | State | Witness |
|---|---|---|
| RP-2 `bcinr-powl-receipt` dangling dep — **CLOSED** | **measured win** | `cd ~/mfw && cargo build -p mfw-planner -p mfw-pcp-cli` → `Finished dev profile [unoptimized + debuginfo] target(s) in 47.23s`, exit `0`. Binaries exist and run: `target/debug/mfw-planner` (54 MB, *"Receipted external planner runner"*; `probe`/`run`/`export-powl`/`solve-rdf`/`solve`) and `target/debug/mfw-pcp-cli` (6.8 MB, *"Proof-carrying plan lifecycle verifier"*; `demo`/`verify-bundle`/`verify-replay`/`render-rdf`). |
| Pass-2 claim "this is a one-line dep fix" | **correction, retracted** | Wrong. Actual scope: **four** `bcinr-powl-receipt` declarations (`~/praxis/Cargo.toml:100`, `crates/multifractal-workflow/Cargo.toml:111`, `crates/praxis-core/Cargo.toml:20`, `crates/praxis-graphlaw/Cargo.toml:41`) plus **26 import sites across 12 files**. A one-line edit would have relocated the error. The wrong estimate stays visible in `docs/ecosystem-standing.md` RP-2. |
| RP-2 fix committed / admitted through mfw's gate | **recorded negative** | Fix lives on `fix/bcinr-powl-receipt-rename` in `~/praxis` and is **NOT COMMITTED** — that repo carried 47 pre-existing dirty files, some in files also edited, so committing would entangle unrelated work. The engine is still not registered in `engines.toml` with a blake3 pin. So S2 moves `BUILD_BROKEN` → `PARTIAL_ALIVE` and no further: the build is repaired, admission is not demonstrated, and the "clean clone" falsifier is live. |
| Second dangling absolute-path dep (`ggen-core`) | **recorded negative** | `~/praxis/crates/rust-fable-testbed/Cargo.toml:11` path-deps `../../../ggen/crates/ggen-core`; `ls ~/ggen/crates/ggen-core` → `No such file or directory`. `~/ggen-legacy/ontology/v26.8.1/legacy-capabilities.ttl:21-28` **already records the deletion** (`legacy:legacy_ggen_core_pipeline`, commit `9cef6e40f (delete) / cbf173f82 (disconnect, PR #255)`, disposition `REPLACED`, standing `UNKNOWN`). Connective-tissue debt demonstrated live. Does **not** block mfw — mfw pulls `praxis-graphlaw` only, and `cargo metadata --format-version 1` in `~/mfw` exits `0`. Scoped to `~/praxis`. |
| blake3 digests cross-checked by an independent implementation | **measured win** | `mfw-planner export-powl` (run from `~/mfw/mfw-planner`, where `engines.toml` lives) computed `domain_digest blake3:b11c0b44…06e2` and `problem_digest blake3:8a43b3cd…e143` for the blocks domain — **byte-identical** to what `src/autofde_lab/fabric/powl.py` produced independently (quoted in `docs/ecosystem-standing.md` S3b). Two implementations, two languages, same identity. Minor mismatch recorded: mfw writes `"projection": "total_order"`, `powl.py` writes `"total-order"`. |
| Pass-2 row "POWL2 projection with real blake3 — measured win" | **correction, demoted to PARTIAL_ALIVE** | The digests hold (row above). The **Turtle does not validate**: `project_plan_to_powl` never emits `mfwp:implementsAction`, which `~/mfw/mfw-planner/shapes/powl2.shacl.ttl` `powl2:ActivityLeafShape` requires `minCount 1` — so this repo's POWL would be **rejected by the shapes it is projected against**. It also hardcodes `mfwp:projection "total-order"` and emits zero `powl2:precedes` edges, making a declared `powl2:PartialOrder` a chain. A concurrent agent is repairing the writer; **that fix is not claimed here** — nothing was run against a repaired `powl.py`. |
| G1 (ingestion) and G3 (actuation) are the same gap | **measured win, supersedes the pass-2 split** | `export-powl` emits JSON schema `urn:mfw:powl:document:v2` (nested `model.children[]` + `order:[{before,after}]`), a string present only in `mfw-planner` (`solve_rdf.rs:407`, `plan.rs:173`, `powl.rs:439`) and never in `mfw-rmcp`. `mfw-rmcp/src/powl.rs:38-105` ingests a **flat** `nodes: BTreeMap` + `root`, each node carrying `authorization_class`, `read_set`, `write_set`, and a `NativeOperation` from a closed 3-variant algebra. Those fields are **authorization decisions no planner can produce** — so a converter cannot close G1 without answering G3's "what maps an activity to an executable operation?". One gap. |
| Which POWL representation is canonical | **open decision, evidence recorded, NOT decided** | `mfw-rmcp`'s `NodeKind` has `ChoiceGraph{…, edges: Vec<ChoiceEdge>}` with a `guard_digest`, plus `Cycle{body, invariant_theorem, variant_theorem}` and `CommutationWitness`. Choice and guards are representable in runtime JSON, **not** in Turtle (`powl2.shacl.ttl` has 3 shapes, none for choice) and **not** in bcinr's `PowlModel` (no choice variant, `~/bcinr/crates/bcinr-powl/src/model/mod.rs:148`). **Turtle is the weakest of the three, not the canonical one** — which contests RP-7 step 1. Flagged, not resolved. |
| Search-scope failure reproduced inside this session | **recorded negative, epistemic** | Two of this session's own agents disagreed on `EvaluateSunsetStanding`: one reported "no executable, only prose in three docs" having searched scikit-decide's `docs/` only; the other found `~/ggen-legacy/appliance/bin/decision-engine.py` (38 lines, confirmed) implementing the real gate — `release = verifier.standing=="ALIVE" and cross_check.standing=="ALIVE" and replay.status=="REPLAY_MATCH"`, a 7-field zero-closure check, then `sunset = release and closed and m.get("customer_authorized_retirement") is True` (fail-closed; `is True` rejects a truthy string). Same failure mode as the earlier `~/bcinr` miss, one pass after it was written down. |
| Phase 0 — rules files load conditionally | **measured win** | `.claude/rules/*.md` now carry YAML `paths:` front-matter, loading only when a matching file is read. Previously all six loaded unconditionally — verifiable from this session's own system prompt, which contained all six in full. An `@` import expands at session start, so the earlier `CLAUDE.md` split reorganised text without reducing context. Root `CLAUDE.md` now also documents that cross-repo work needs `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` alongside `--add-dir` — `--add-dir` grants file access but **not** instruction loading, the exact condition behind the `~/bcinr` miss. |

| S4 — real bounded `ggen sync run` in a clean temp workspace | **measured win** | `~/ggen/examples/star-toml-verify` copied to a temp workspace, `[packs]` repointed at an absolute `~/ggen/packs/star-toml-pack`, pre-existing outputs deleted, then real `ggen sync run --format json` (**not** `--dry-run`) → `written: 7`, `skipped: 0`, `graph_hash a3b0b66476ef6c5afcfeddb8…`, exit `0`. All 7 files confirmed on disk. Determinism cross-check: the same workspace with outputs present returned `written: []`, all 7 `"skipped: unchanged: content identical"`, and an **identical** `graph_hash_hex a3b0b664…`. |
| RP-4's zero-generated-outputs defect reproduced off-root | **recorded negative, RP-4 stays open** | The no-op run above is exactly RP-4's shape: `sync run` succeeds while reporting zero generated outputs, because the "unchanged: content identical" admission path never registers ownership. Reproduced in a clean temp workspace, so it is **not** specific to `~/ggen`'s root. Strengthens RP-4's evidence; does **not** close it. |
| S5 — independent verification of a receipt manufactured this session | **measured win** | That manufacture wrote `.ggen-v2/receipt.json` (4784 B) + `receipt-log.jsonl` (56675 B). `ggen receipt verify --format json` from the temp workspace: `~/.cargo/bin/ggen` → `valid=True chain=98e756627c789118 sig_valid=True outputs=7`; `~/ggen/target/debug/ggen` → identical. **The verifying build is not the writing build** — genuine independent verification, and a fresh receipt distinct from the pre-existing one EV-1 concerned. S5 moves `BUILD_BROKEN` → `PARTIAL_ALIVE`. |
| EV-1 residual / RP-1 | **recorded negative, still open** | `/opt/homebrew/bin/ggen` **no longer exists on this machine**, so only two builds were reachable. EV-1's residual risk — a `brew link` reintroducing the stale Cellar binary and restoring the disagreement — is **untested here, not disproven**. Two-of-two agreeing is weaker than three-of-three; RP-1 stays open. |
| Stale docstring in the crown test | **recorded negative, not fixed here** | `tests/ecosystem/test_chatman_chain_chicago.py:364` still reads *"Left deliberately failing rather than xfail-ed or skipped."* Stale since EV-1 was fixed and the suite reached 27 passed. The test is *conditionally* red: it hard-fails only if two reachable ggen builds disagree, and skips `BLOCKED:INSUFFICIENT_VERIFIER_BUILDS` below two. Needs a one-line correction. Not edited — `tests/` is owned by a concurrent agent this session; recorded so the inconsistency is visible rather than silent. |

No pytest was run in this pass (concurrent agents were editing `src/` and `tests/`); no row
above claims a test result. Pass-3 changes to this repo are documentation only.

## Pass 2 — ecosystem closure ledger (2026-08-06)

| Item | State | Witness |
|---|---|---|
| Classical PDDL engine for `~/mfw`'s external-engine seam | **measured win** | `uv run python -m autofde_lab.fabric.pddl_engine tests/domains/python/pddl_domains/blocks/{domain,probBLOCKS-3-0}.pddl /tmp/blocks.plan` → `plan found, 4 step(s), cost 4`; file contains `(unstack a b) … ; cost = 4 (unit cost)`, matching the shape of the committed `~/mfw/runs/ticket-10/work/candidate.plan`. Satisfies the `classical`+`file` contract in `mfw-planner/src/config.rs`. |
| Refusal of parsed-but-unimplemented PDDL requirements | **measured win** | Engine exits `2` with `UNSUPPORTED_REQUIREMENT: :derived-predicates,:constraints,:preferences` on `~/ggen-legacy/planning/v26.8.1/domains/ggen-v2681-core.pddl`. `grep -rn "derived" cpp/src/hub/domain/pddl/semantics/` → **zero hits**: derived atoms are never true and nothing raises, so the alternative was a confident wrong plan. That corpus's `admit-sunset` is gated on the derived predicate `sunset-safe`, i.e. it would have been silently unreachable. |
| POWL2 projection with real blake3 | **measured win — SUPERSEDED by pass 3, demoted to `PARTIAL_ALIVE`; the Turtle fails mfw's own SHACL shapes** | `mfwp:domainDigest "blake3:b11c0b44…"` cross-checked against an independent `b3sum` in `tests/ecosystem/`. Projector raises `DigestUnavailable` rather than emitting another algorithm under a `blake3:` label. **Scope: projection, not execution.** |
| Capability ontology, generated not curated | **measured win** | `python -m autofde_lab.fabric.ontology ontology/skdecide-capabilities.ttl` → 83 capabilities (26 domains, 57 solvers) + 16 PDDL requirements, 4 `UNSUPPORTED`. `tests/ecosystem/` asserts it matches the live registry exactly and that every solver's requirements equal its `get_domain_requirements()` derivation. |
| Capability-coverage completeness | **measured win** | All 57 solvers classified against `CareerAdmission`: 26 `tied_optimal` (cost 3), 8 `excluded` (`UNMET_DOMAIN_CHARACTERISTICS`), 23 `failed` (`REQUIRES_OTHER_DOMAIN_TYPE` 8, `REQUIRES_CONFIGURATION` 7, `DID_NOT_CONVERGE` 5, `RUNTIME_ERROR` 3). Comparison is measured by running them, because `match_solvers(ranked=True)` ignores the flag (`utils.py:126`). |
| Crown + unit suites | **measured win** | `uv run pytest tests/ecosystem/ tests/domains/python/test_career_admission_unit.py` → **27 passed**. |
| Prior "Chicago" career test demoted | **measured win, correction** | `test_career_admission_chicago.py` → `test_career_admission_unit.py` with an explicit scope warning. It exercised one solver against one local in-repo domain and touched no sibling repo; citing it as ecosystem evidence was the error, not the test itself. |
| Whole-suite collection | **recorded negative, unchanged** | `uv run pytest tests --collect-only -q` still errors on the same 4 files (`tests/solvers/python/test_pomcp.py` basename collision + 3 `_dspy_*_chicago.py` import failures). Re-verified 2026-08-06; the new suites collect and pass by path. |
| `~/mfw` engine admission end-to-end | **recorded negative — build CLOSED in pass 3; admission still open. The "one-line dep fix" claim below is RETRACTED (it was four declarations and 26 import sites).** | `cargo build -p mfw-planner` → `BUILD_BROKEN`. Chain: `mfw-planner → mfw-shacl → praxis-graphlaw → bcinr-powl-receipt`, and `/Users/sac/bcinr/crates/bcinr-powl-receipt` does not exist (the dir has `bcinr-powl`). Referenced by absolute path at `praxis-graphlaw/Cargo.toml:41`. Diagnosed further in `docs/ecosystem-standing.md` RP-2: the crate was **renamed** into `bcinr-powl::receipt` (commit `251f3af5`), `26.7.28` is still unyanked on crates.io, so this is a one-line dep fix — but the durable defect is the absolute `/Users/sac/...` path, which is why CI never saw it. Consequence: the engine's *contract conformance* is tested; its *admission through mfw's own gate* is not. Weaker, and labelled as such. |
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
- `ontology/skdecide-capabilities.ttl` — generated capability graph (A-Box of standing claims);
  regenerate with `python -m autofde_lab.fabric.ontology`, never hand-edit.
- `ontology/fde-authority-schema.ttl` — hand-authored T-Box for the FDE authority vocabulary and
  the three standing dimensions. Legitimately hand-authored **because it is a vocabulary, not a
  standing claim**; nothing in it is `ALIVE`.
- `.claude/rules/fde-authority-boundary.md` — the organizational-layer boundary rule.
