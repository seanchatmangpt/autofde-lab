# Ecosystem standing — scikit-decide inside the Chatman manufacturing chain

Companion to `docs/STATUS.md`, same discipline, wider scope. `STATUS.md` ledgers WIP inside
this repository; this file ledgers the **cross-repository chain** —
`ggen-create → ggen → ggen-legacy`, with `mfw` supplying admission/receipt/replay law and
scikit-decide supplying the search graph.

Every row is a **measured win** (command run this session, output quoted, passed), a
**recorded negative** (attempted, genuinely blocked, blocker named precisely), or
**deferred/scoped** (a plan exists, nothing under it executed). Where this sheet and the code
disagree, the code is the witness.

Last update: **pass 1** (2026-08-06) — first session to actually execute across the chain
rather than describe it. Corresponds to `docs/STATUS.md` pass 2.

## Why this file exists

An earlier attempt this session built an isolated domain + A* test inside scikit-decide and
reported it `ALIVE` as a "Chicago test." That test passes, but it *encodes an analogy to* the
manufacturing law rather than exercising it — no sibling repo was touched, nothing was
manufactured, nothing independently verified. It has been demoted to
`tests/domains/python/test_career_admission_unit.py` with an explicit scope warning. The crown
is `tests/ecosystem/test_chatman_chain_chicago.py`, which drives real binaries and real
corpora. It went red on a real defect the moment it was written (EV-1) and is green now only
because that defect was actually fixed — not because the assertion was relaxed.

## Standing by stage

| # | Stage | Owner | Standing | Witness |
|---|---|---|---|---|
| S1 | exemplar → candidate authority | ggen-create | `UNSUPPORTED` | Reverse compiler is **0 lines**; `ontology/` holds only `.keep`. Repo self-declares it: `scan_ontology` → `bootstrap_empty_surface: True`, claim ceiling `ONTOLOGY_SURFACE_INTEGRITY_ONLY`. Its CI/GALL harness *is* real (25/25 tests, 0.26s, real git fixtures) — governance, not payload. |
| S2 | candidate authority → admitted | mfw | `BUILD_BROKEN` | `cargo build -p mfw-planner` fails. See RP-2. |
| S3 | plan computation (search graph) | **scikit-decide** | `ALIVE` | Engine runs, produces VAL-format plans. Quoted below. |
| S3b | plan → POWL2 **projection** | **scikit-decide** | `ALIVE` *(projection only)* | Real blake3 digests, mfw's committed vocabulary. Quoted below. **Scope**: this manufactures a document. It is NOT execution — see the decisive question. |
| S3c | admitted POWL → **executed** workflow | mfw + **bcinr** (RP-7) | `PARTIAL_ALIVE` | A real POWL executor exists in `~/bcinr` (`execution_v2.rs:129` tick loop, OCEL, BLAKE3, deadlock refusal) — but it is **symbolic** (in-memory state only) and **not wired** to mfw's actuating broker. Three POWL representations, zero converters. Blocks the crown. |
| S4 | manufacture (μ) | ggen | `PARTIAL_ALIVE` | `sync run` executes and self-verifies in CI; `Root Dogfood` 8/8 red at the closure gate. See RP-4. |
| S5 | independent verification | ggen / ggen-legacy | `BUILD_BROKEN` | **Verifier builds disagree about identical bytes.** See EV-1 / RP-1. |
| S6 | replay / equivalence / sunset | ggen-legacy | `PARTIAL_ALIVE` | 3 compiled verifier binaries execute and emit typed fail-closed refusals; `decision-engine.py` is a real 3-report + customer-flag gate defaulting to REFUSED. Root LSP crate never built, no CI builds it. |
| S7 | recursive bootstrap controller | — | `UNSUPPORTED` | `Blocked → spawn child → manufacture → verify → admit → resume parent` exists **nowhere in code** across all five repos (`mfw`, `ggen`, `ggen-create`, `ggen-legacy`, `bcinr`). Primitives real; orchestration absent. Asserted absent by a test so the claim cannot drift silently. |

**The chain does not close.** `ALIVE` is not claimable for the end-to-end path. S3/S3b are
genuinely `ALIVE`; S1, S2, S3c and S7 each independently prevent closure — **S3c is the
decisive one**, because a plan that is never executed makes every downstream stage moot.

### The crown condition, stated correctly

The crown is **not** `PDDL → A* → plan file → POWL Turtle`. That path is real and now works,
but it stops one step before the thing that matters. The crown is:

```
ontology-governed capability discovery
  → complete applicable-capability coverage (selected / compared / excluded-with-reason)
  → candidate-plan computation
  → POWL manufacture
  → MFW admission
  → brokered EXECUTION of the whole plan
  → OCEL + receipts at execution time
  → replay
  → verified plan-level standing
```

Measured against that, this session moved the first four steps and proved the fifth-to-ninth
absent. Reporting the crown as anything other than `BLOCKED` would require a projector to
stand in for an executor, which is the specific error this file exists to prevent.

## Measured wins

### S3 — classical PDDL engine (new capability, fills a real vacancy)

`src/skdecide/fabric/pddl_engine.py`. Satisfies mfw's *existing* external-engine contract
(`mfw-planner/src/config.rs`: roles are a closed set; `classical` + `output_mode="file"`
requires exactly `{domain} {problem} {plan}`) — the reference case mfw already registers is
`fast-downward.py`, so a Python engine in this slot is the norm, not a novelty.

```
$ uv run python -m skdecide.fabric.pddl_engine --help
usage: skdecide-classical-engine <domain.pddl> <problem.pddl> <plan-file>

$ uv run python -m skdecide.fabric.pddl_engine \
    tests/domains/python/pddl_domains/blocks/domain.pddl \
    tests/domains/python/pddl_domains/blocks/probBLOCKS-3-0.pddl /tmp/blocks.plan
skdecide-classical-engine: plan found, 4 step(s), cost 4 -> /tmp/blocks.plan

$ cat /tmp/blocks.plan
(unstack a b)
(put-down a)
(pick-up b)
(stack b c)
; cost = 4 (unit cost)
```

Format matches the real committed artifact `~/mfw/runs/ticket-10/work/candidate.plan`.

### S3b — POWL2 projection

`src/skdecide/fabric/powl.py`. PDDL selects among admitted transitions; POWL is the process
geometry that transition becomes (`CHATMAN-EQUATION.md`, "Recursive Process Manufacture").
Emits the vocabulary of the real committed `~/mfw/runs/ticket-10/plan.powl.ttl`:

```turtle
<urn:skdecide:plan/plan> a powl2:Model, powl2:PartialOrder ;
    mfwp:domainDigest "blake3:b11c0b44765957b790404ec9c8ec5e8e5b590353dcc98a50f794a469314406e2" ;
    mfwp:problemDigest "blake3:8a43b3cd62188ce5f366de4f2175825ae3d5c10f69a908115a26ef579ba7e143" ;
    mfwp:projection "total-order" ;
    mfwp:activityCount "4"^^xsd:integer .
```

Digests are **real blake3** via `b3sum`. The projector raises `DigestUnavailable` rather than
emitting another algorithm under a `blake3:` label — a forged identity would mismatch mfw's
`PLANNER_ENVIRONMENT_DRIFT` check with a misleading reason.

### S3c — silent-wrong-answer refusal (the most important behavior added)

scikit-decide's PDDL backend **parses** `:derived-predicates`, `:constraints` and
`:preferences` and then does not implement them. Verified: `grep -rn "derived"
cpp/src/hub/domain/pddl/semantics/` → **zero hits**. Derived atoms are never true, so any
action gated on one is silently never applicable. `GoalChecker::is_goal` never reads
`problem->get_constraints()`. `Preference::holds` returns the inner formula, making a *soft*
preference a *hard* constraint. **None of these raise.**

Without a gate, the engine would emit a confident, plausible, wrong plan — strictly worse than
refusing, because a wrong plan can be admitted downstream. The engine now refuses:

```
$ uv run python -m skdecide.fabric.pddl_engine \
    ~/ggen-legacy/planning/v26.8.1/domains/ggen-v2681-core.pddl \
    ~/ggen-legacy/planning/v26.8.1/problems/01-governance.pddl /tmp/gl.plan
skdecide-classical-engine: REFUSED: UNSUPPORTED_REQUIREMENT:
:derived-predicates,:constraints,:preferences declared by .../ggen-v2681-core.pddl.
scikit-decide's PDDL backend parses these but does not implement them; planning would
silently return an incorrect plan. Refusing rather than emitting one.
$ echo $?
2
```

This matters concretely for that corpus: `admit-sunset`'s precondition is the derived predicate
`sunset-safe`. Under the unimplemented semantics it would be unreachable — a planner would
report "no sunset possible" with total confidence and no error.

### S3d — two latent defects found in ggen-legacy's corpus

Parsing that corpus **for the first time** surfaced defects `verify_planning.py`'s
paren-balance-and-substring check cannot detect:

1. `ggen-v2681-core.pddl@50:29` — `variable '?x' unknown to the current parsing context`,
   inside the `(:derived (fully-evidenced ?x - object) ...)` body. The `:derived` head's
   parameters are not bound into body scope. Attribution is genuinely ambiguous between a
   corpus bug and a scikit-decide parser gap; consistent with derived-predicate support being
   absent end-to-end. **Unresolved — needs a second parser to disambiguate (RP-3).**
2. `10-legacy-sunset.pddl@5:3` — `object 'preserved' already existing in problem`.
   **Unambiguously a corpus bug**: the domain declares `preserved` in
   `(:constants ... preserved subsumed replaced archived refused unknown-disposition -
   disposition)`, and the problem redeclares it in `(:objects ...)`. PDDL forbids this.

### S8 — ontology-governed capability discovery and coverage

`ontology/skdecide-capabilities.ttl`, generated by `src/skdecide/fabric/ontology.py` from
entry points + a live import probe + `get_domain_requirements()` MRO derivation. **83
capabilities** (26 domains, 57 solvers, all `ALIVE` here) plus 16 PDDL requirements, 4 of them
`UNSUPPORTED` — encoding the silent-wrong-answer hazard as a first-class fact rather than a
constant in one module.

`src/skdecide/fabric/coverage.py` classifies **every** declared solver against a concrete
domain. Measured over `CareerAdmission`, all 57 accounted for:

| disposition | n | detail |
|---|---|---|
| `tied_optimal` | 26 | ran, all reached cost 3 — a tie is reported as a tie, not 26 "wins" |
| `excluded` | 8 | `UNMET_DOMAIN_CHARACTERISTICS`, naming the exact missing characteristic |
| `failed` | 23 | `REQUIRES_OTHER_DOMAIN_TYPE` 8, `REQUIRES_CONFIGURATION` 7, `DID_NOT_CONVERGE` 5, `RUNTIME_ERROR` 3 |

Applicability is derived (ontology requirements evaluated by `isinstance`), and comparison is
**measured** — necessary because `match_solvers(..., ranked=True)` accepts the flag and
ignores it, so an unmeasured "dominated" verdict would be an empty claim.

**Limitation this surfaced.** `get_domain_requirements()` describes the *domain
characteristics* a solver needs but says nothing about its *constructor* requirements. Seven
solvers are ontology-applicable yet not runnable with defaults (`IW`, `RIW`, `RayRLlib`,
`StableBaseline`, `UPSolver`, `MAHD`, …). That is a distinct, actionable category —
`REQUIRES_CONFIGURATION` — not the same as inapplicable, and it is now machine-readable.

### Crown test

```
$ uv run pytest tests/ecosystem/ tests/domains/python/test_career_admission_unit.py
27 passed
```

EV-1 was red here earlier in the session and is now green because the defect it found was
actually fixed (see below), not because the assertion was weakened.

## What this session changed epistemically

Not "the project looks more achievable." The change is that an **undefined architectural
absence became a bounded integration problem with one genuinely hard component**.

Before: *"implement recursive multifractal workflow manufacture"* — a description that bundled
six unresolved questions (does a scheduler exist? a broker? can anything actuate? is there an
execution receipt model? can standing close at plan level? how does a parent resume?). Bundled,
it read as research-scale.

After, the gaps separate and their characters differ sharply:

| Gap | Condition | Character |
|---|---|---|
| **G1 representation** | Turtle / JSON / Rust model reps disconnected, zero converters | conventional integration |
| **G2 scheduling** | `bcinr-powl` already supplies the bounded loop | existing capability, needs composition |
| **G3 actuation** | symbolic scheduling causes no real effect at plan scale | **genuine architecture** |
| **RP-6 recursion** | no child manufacture / admission / attachment / resumption | higher-order orchestration |

The accurate diagnosis is **not** "mostly unbuilt." It is **densely implemented but
operationally discontinuous**: planners without execution, scheduling without actuation,
actuation without plan traversal, POWL projections without canonical ingestion, receipts
without complete plan coverage, standing without N-of-N closure, capability implementations
without an ecosystem-wide capability authority.

That is **connective-tissue debt**, and it is the failure mode component-centric architecture
structurally cannot see: every repository can truthfully demonstrate a local capability while
the enterprise-level consequence remains impossible. The relevant unit of correctness is not
the component, it is the closed causal chain.

Honest current claim:

> The core planning, scheduling, manufacturing, authorization, evidence, and replay primitives
> exist. The remaining work is canonical representation, brokered plan-scale actuation,
> complete standing closure, and recursive parent-child orchestration. **The system is
> closable; the crown is not yet closed.** The unknown was whether the machinery existed — it
> does. The open question is whether it can be lawfully connected without collapsing planning,
> authority, actuation, and verification into self-attestation.

### Why the ontology is an epistemic control, not documentation

This session produced a false ecosystem-wide claim — *"no POWL executor exists"* — from a
search that had never looked at `~/bcinr`, which contains one. The error was not carelessness
about a single repo; it is structural. **Any architecture conclusion drawn from "whichever
repositories the investigator happened to inspect" is unsound by construction.**

An ontology makes such a claim mechanically falsifiable. The question stops being "have I
looked everywhere?" (unanswerable) and becomes "which admitted capability implements POWL
scheduling?" (a query). The ecosystem-level ontology this implies must model repositories,
crates, capabilities, **renamed or absorbed components** (`bcinr-powl-receipt` →
`bcinr-powl::receipt` is exactly the case that broke a build and hid an executor),
implementations, interfaces, I/O, standing, evidence, dependencies, compatible and
incompatible representations, authoritative owners, available actuators, planners, schedulers,
and verification rails.

`ontology/skdecide-capabilities.ttl` is the first instalment — scoped to this repo, generated
from entry points, and asserted against the live registry so it cannot drift. The
ecosystem-wide graph is not yet built and is recorded here as scoped, not done.

## Capability surface (measured, for the ontology)

Inventoried from `pyproject.toml` entry points — the authoritative registry — and verified by
importing every one in this environment:

- **26 registered domains**, all import OK. `ChatmanCleanSession` is the only one with **no
  extras marker** (pure core). `TPDDLDomain` sits behind the `pddl` extra (needs `z3`).
- **57 registered solvers**, **all 57 import OK** — none `UNSUPPORTED` here. The compiled hub
  is present (`.venv/.../__skdecide_hub_cpp.cpython-313-darwin.so`), which is what makes the
  ~35 C++-backed solvers live.
- Applicability is **programmatically derivable**, not a matter of opinion:
  `Solver.get_domain_requirements()` (`src/skdecide/solvers.py:85`) derives the requirement set
  from the solver's `T_domain` MRO, and `check_domain` (`solvers.py:123`) tests
  `all(isinstance(domain, req) ...)` plus the `_check_domain_additional` hook.
  `match_solvers(domain, candidates, ranked)` (`src/skdecide/utils.py:126`) applies it across
  the whole registry.

Two findings that constrain how a coverage report may be built:

1. **`ranked` is accepted but ignored** — `utils.py:126` carries `# TODO: implement ranking
   heuristic` and always returns a plain list. So "compare alternatives where several
   capabilities solve the same subproblem" cannot be delegated to `match_solvers`; comparison
   must be genuinely measured (run them, compare plans/costs) or the claim is empty.
2. **Failed solver loads surface as `None`, never as an exception** —
   `_load_registered_entry` (`utils.py:94`) swallows and `logger.warning`s. A coverage report
   must therefore treat `None` as positive `UNSUPPORTED` evidence rather than as absence, or a
   silently-unloadable solver would simply vanish from the tally.

These are the mechanisms the ontology must be generated *from*. A hand-written Python list of
capabilities would not be ontology-backed, it would be a decorative catalog that happens to
sit next to one.

## Recorded negatives

### EV-1 — ggen verifier builds disagreed about identical bytes — **FOUND, DIAGNOSED, FIXED**

Found by the crown test (this is what a test that can fail is for). Three binaries, all
self-reporting `26.8.6`, on the same git-tracked, unmodified
`/Users/sac/ggen/.ggen-v2/receipt.json`:

| binary | verdict (before fix) |
|---|---|
| `/opt/homebrew/bin/ggen` | **INVALID** — chain hash mismatch, recomputed `23386d67ba4fe290…` |
| `/Users/sac/ggen/target/debug/ggen` | `{"valid":true,"chain_hash":"918c5b0980…","signature_valid":true}` |
| `/Users/sac/.cargo/bin/ggen` | `{"valid":true,"chain_hash":"918c5b0980…","signature_valid":true}` |

Severity: not a normal test failure. If which build sits on `PATH` determines whether an
artifact is admitted, "independently verified" is not a property of the artifact. The stale
build additionally **misattributed** the cause — *"the receipt's own record fields … were
tampered with — restore from `receipt history`/git"* — which would send an operator chasing a
tampering incident that did not occur. The receipt was unmodified; the verifier differed.

**Root cause — corrected after checking git state.** An earlier draft of this entry called the
homebrew build "stale/out of date." That was wrong and is retracted. `v26.8.6` is the correct
version, and the released binary is a faithful `v26.8.6`:

```
$ cd ~/ggen && git tag -l '*26.8.6*'   -> v26.8.6
$ git rev-list --count v26.8.6..HEAD   -> 37
$ git log --oneline -1                 -> ebb16b657 (branch feat/hygen-parity-e2e)
$ grep -m1 '^version' Cargo.toml        -> version = "26.8.6"
```

HEAD is **37 unreleased commits past tag `v26.8.6`**, on a feature branch, still declaring
`26.8.6` — normal mid-development CalVer practice. The chain-hash computation changed
somewhere in those 37 commits, and `.ggen-v2/receipt.json` was written by that newer code.

So the released verifier is **not malfunctioning**: it correctly rejects a receipt produced by
an algorithm it predates. The real defect is narrower and more serious than "stale install":

> **An unreleased breaking change to the receipt chain-hash algorithm is carried on a feature
> branch with no version discriminator.** Any receipt written by that branch is unverifiable
> by the released tool, and the resulting error blames tampering.

`brew outdated` reports nothing and `brew upgrade` refuses, correctly — the formula's `stable`
genuinely *is* the latest release. There is nothing for homebrew to fix.

**Fix applied** (source rebuild + unlink stale Cellar copy — the receipt was never touched):
```
$ cargo install --path crates/ggen-cli --force     # Replacing /Users/sac/.cargo/bin/ggen
$ brew unlink seanchatmangpt/ggen/ggen             # 1 symlinks removed
$ which -a ggen
/Users/sac/.cargo/bin/ggen
$ cd ~/ggen && ggen receipt verify --format json
{"valid":true,"chain_hash":"918c5b09...","outputs":46,"signed":true,"signature_valid":true}
```
Both reachable builds now return byte-identical verdicts; the crown test went 15p/1f → **17
passed**. `git status --porcelain .ggen-v2/receipt.json` empty — evidence untouched.

**Residual risk, not closed.** The stale binary still exists at
`/opt/homebrew/Cellar/ggen/26.8.6/bin/ggen` and still fails. Any `brew link` or an unrelated
`brew upgrade` could relink it and silently reintroduce the disagreement. RP-1 below is
therefore **still open** — the machine is fixed, the *class of defect* is not.

### RP-2 — `BUILD_BROKEN`: `cargo build -p mfw-planner`

```
error: failed to get `bcinr-powl-receipt` as a dependency of package
       `praxis-graphlaw v26.7.9 (/Users/sac/praxis/crates/praxis-graphlaw)`
    ... which satisfies path dependency `praxis-graphlaw` (locked to 26.7.9)
        of package `mfw-shacl v0.1.0 (/Users/sac/mfw/mfw-runtime/mfw-shacl)`
Caused by: unable to update /Users/sac/bcinr/crates/bcinr-powl-receipt
Caused by: failed to read /Users/sac/bcinr/crates/bcinr-powl-receipt/Cargo.toml
Caused by: No such file or directory (os error 2)
```

Chain: `mfw-planner → mfw-shacl → praxis-graphlaw → bcinr-powl-receipt (absent)`.
`/Users/sac/bcinr/crates/` exists and contains `bcinr-powl`, but **not** `bcinr-powl-receipt`,
referenced by absolute path at `/Users/sac/praxis/crates/praxis-graphlaw/Cargo.toml:41`.
Consequence: mfw's solve → OCEL → receipt path cannot be re-run, so the skdecide engine cannot
be admitted through mfw's own admission gate this session. Its *contract conformance* is
tested instead (S3), which is weaker and labelled as such.

## Repair plans

Format per the correction that prompted this file: missing capability, evidence + exact
blocker, owning repo, required I/O, proposed interface, implementation steps, negative
fixtures, acceptance test, falsifiers, resume condition.

### RP-1 — reconcile ggen verifier builds  *(owner: `~/ggen`)*

Status: **local symptom fixed this session; the underlying defect class is open.**

- **Missing capability**: a version identity that actually identifies a build, so that two
  binaries claiming `26.8.6` cannot compute different chain hashes.
- **Blocker**: EV-1 above. Fixed on this machine by rebuilding from source and unlinking the
  Cellar copy, but the stale binary remains on disk and any `brew link` reintroduces it. The
  formula cannot be upgraded — its `stable` *is* `26.8.6`; upstream must cut a new tag.
- **Required I/O**: in → `.ggen-v2/receipt.json` + `receipt-log.jsonl`; out → identical
  `{valid, chain_hash, payload_hash, signature_valid}` from every build.
- **Interface**: no new interface. Version string must become a real identity — a build whose
  chain-hash computation differs must not report the same version.
- **Steps**: (1) diff the homebrew formula's pinned rev against `~/ggen` HEAD; (2) rebuild /
  reinstall from source (`cargo install --path`), or unlink the stale Cellar copy;
  (3) add the chain-hash algorithm version to the receipt schema so a mismatch is reported as
  *version skew*, not as *tampering*; (4) correct the misattributing remediation text.
- **Negative fixtures**: a genuinely tampered receipt must still be rejected; a receipt written
  by build A must verify under build B.
- **Acceptance test**: `test_all_verifier_builds_agree_on_the_same_receipt` (already written,
  currently red).
- **Falsifier**: a fourth build disagreeing with the reconciled majority.
- **Resume condition**: S5 leaves `BUILD_BROKEN` when all builds agree.

### RP-2 — restore `bcinr-powl-receipt`  *(owner: `~/bcinr`, consumed by `~/praxis` → `~/mfw`)*

**Diagnosis complete — the crate was RENAMED, not deleted. This is a one-line fix.**

- **Missing capability**: none, actually. The dependency target moved.
- **Root cause**: commit `251f3af5` in `~/bcinr` — *"refactor(powl): collapse
  bcinr-powl-receipt into bcinr-powl::receipt"*. The successor is
  `~/bcinr/crates/bcinr-powl/src/receipt/` (14 files), whose `mod.rs:7` states outright:
  *"This was the standalone `bcinr-powl-receipt` crate through 26.7.28."* It shipped —
  `release/v26.7.24.toml:10,23` lists it — and per `~/bcinr/CHANGELOG.md:29`,
  **`bcinr-powl-receipt 26.7.28` is still on crates.io and is NOT yanked.**
- **Why it breaks anyway**: `praxis-graphlaw/Cargo.toml:41` uses an absolute **path** dep
  (`path = "/Users/sac/bcinr/crates/bcinr-powl-receipt"`) into a directory that the rename
  removed. A registry dep on `26.7.28` would still resolve; the path dep dangles.
- **Steps** (either closes it):
  - **(a) preferred** — `bcinr-powl = "26.7.29"` in `praxis-graphlaw/Cargo.toml` and update
    imports to `use bcinr_powl::receipt::…`. Moves onto the maintained successor.
  - **(b) minimal** — `bcinr-powl-receipt = "26.7.28"` from the registry. Unblocks the build
    immediately but pins a crate its own repo has retired.
  - **In both cases**, replace the absolute path with a registry or workspace-relative dep.
    An absolute `/Users/sac/...` path is why this was invisible to CI and unreproducible on
    any other machine — that is the durable defect, not the rename.
- **Negative fixture**: build must fail loudly if the crate is missing again — never silently
  feature-gate it away.
- **Acceptance test**: `cargo build -p mfw-planner` succeeds; then `cargo test -p mfw-planner`.
- **Falsifier**: build succeeds locally but not from a clean clone (absolute paths remain).
- **Resume condition**: S2 → at least `PARTIAL_ALIVE`; the skdecide engine can then be
  registered in `engines.toml` with a blake3 pin and admitted through mfw's real gate,
  upgrading S3 from *contract-conformant* to *admitted*.

### RP-3 — planner for ggen-legacy's orphan corpus  *(owner: `~/ggen-legacy`, needs `~/scikit-decide`)*

- **Missing capability**: anything that plans over `planning/v26.8.1/`. Today only
  `verify_planning.py` touches it — a paren-balance + substring checker. Its justfile runs
  `cargo test -p bcinr-pddl`, and that package does not exist in that repo (0 hits in any
  `Cargo.toml`; it lives in `~/bcinr/crates/bcinr-pddl`).
- **Blocker**: `UNSUPPORTED:derived-predicates,constraints,preferences` (S3c) — scikit-decide
  cannot correctly plan this domain, and now says so instead of guessing.
- **Two independent paths**, either sufficient:
  - **(a) Implement derived-predicate expansion in scikit-decide's C++ semantics.** Largest
    work, widest payoff. Steps: expand derivation rules to fixpoint during grounding in
    `cpp/src/hub/domain/pddl/semantics/`; wire `problem->get_constraints()` into
    `GoalChecker`; make `Preference` soft with a violation counter feeding `:metric`. Negative
    fixture: a domain where a derived atom gates the only goal-reaching action must go from
    unsolvable → solvable, proving expansion actually fires.
  - **(b) Rewrite the corpus to the supported subset.** Compile derived predicates away by
    inlining their bodies. Cheaper, but loses expressiveness and must be justified per domain.
- **Also fix regardless**: the two defects in S3d, and the dangling `-p bcinr-pddl` reference.
- **Acceptance test**: `test_unimplemented_requirements_are_refused_not_planned` inverts —
  a plan is produced *and* independently validated by VAL.
- **Falsifier**: a plan is produced whose steps VAL rejects — meaning expansion is wrong rather
  than absent, which is the S3c hazard reintroduced.
- **Resume condition**: S3 extends from `blocks`-class domains to the governance corpus.

### RP-4 — close ggen's root-regeneration gate  *(owner: `~/ggen`)*

- **Missing capability**: byte-identical re-manufacture; `Root Dogfood` 8/8 red.
- **Blocker**: `verify_root_regeneration.py` reports `generated_output_paths: []` and 5 of 21
  declared `output_file` values are un-expanded Tera placeholders
  (`crates/{{ crate_name }}/Cargo.toml`, `.specify/gates/{{ gate_id }}.rq`, …). The verifier
  compares them as literal paths. Fails *after* `sync run` succeeds.
- **Steps**: (1) decide whether those 5 rules are per-row fan-out (then the verifier must
  expand bindings before comparing) or authoring errors (then fix the manifest); (2) make the
  "unchanged: content identical" admission path still register ownership, so a clean checkout
  does not report zero generated outputs; (3) only then enable the byte-identical second-run
  step.
- **Falsifier**: gate goes green while `generated_output_paths` is still empty — that would be
  the gate being disabled, not satisfied.
- **Resume condition**: S4 → `ALIVE`; receipt `standing_ceiling` should rise above
  `LegacyObserved` and obligations above 5/9.

### RP-5 — exemplar → candidate authority  *(owner: `~/ggen-create`)*

- **Missing capability**: the reverse compiler. 0 lines.
- **Blocker**: not a bug — unbuilt, and the repo says so honestly in code.
- **Required I/O**: in → an exemplar (repo/service/document set); out → candidate
  `ontology.ttl` + templates + `ggen.toml` that `ggen sync run` can consume unmodified.
- **Interface note**: the output contract is already pinned by what `ggen` consumes —
  `[ontology] source/imports`, `[[generation.rules]]{query,template.file,output_file,mode}`.
  Build against that, not a new schema.
- **Negative fixtures**: an exemplar with no recoverable structure must REFUSE, not emit an
  empty ontology; a candidate ontology failing the SPARQL gates must not be admitted.
- **Acceptance test**: reverse-compile a small known project, run real `ggen sync run` on the
  output, and verify the receipt — with the exemplar and the regenerated artifact compared by
  `ggen-legacy`'s existing `equivalence_runner.py`.
- **Resume condition**: S1 → `PARTIAL_ALIVE`; the chain gains its front end and the career
  payload can enter as an exemplar rather than as hand-authored authority.

### RP-7 — wire bcinr's executor to mfw's broker  *(owner: `~/mfw` + `~/bcinr`)* — **the crown capability**

**Revised after discovering `~/bcinr`.** This was originally written as "build a POWL execution
controller." That was wrong — the driver already exists in `bcinr-powl`. The job is
composition, not construction, and it is materially smaller than first stated.

- **Missing capability**: the connection between bcinr's *symbolic* plan driver (walks the
  partial order, emits OCEL + BLAKE3, refuses on deadlock) and mfw's *actuating* broker
  (authorizes against model/proof digests, performs confined writes, chains receipts). Each
  half is real; neither is useful alone.
- **Evidence / exact blockers**: the two disjoint gaps proven above.
  - **G1 (ingestion)**: planner emits Turtle (`solve_rdf.rs:459`); runtime ingests JSON
    (`mfw-rmcp/src/config.rs:86`). Nothing reads `.powl.ttl` outside the planner's own tests.
  - **G2 (driver)**: `broker.actuate` (`broker.rs:118`) takes a singular `node_id`;
    `ready_actions`/`maximal_cohort` (`powl/validation.rs:156-158`) compute the next legal set
    but their only callers are read-only MCP advisory tools (`server.rs:145`, `:160`). The
    client is the scheduler.
- **Required I/O**: in → a validated POWL model + its `model_digest`/`proof_digest` + an
  authorization context; out → an ordered receipt chain covering **every** activity, an
  execution-time OCEL log, and a plan-level standing verdict.
- **Proposed interface** (composes only what already exists; invents no new primitive):
  ```
  loop:
    ready := ready_actions(model, completed)      # powl/validation.rs:156 — exists
    if ready.is_empty(): break
    for node in ready:
      receipt := broker.actuate(ActuationRequest{ # broker.rs:118 — exists
                    model_digest, proof_digest, node_id: node, occurrence, operation })
      completed.insert(node)
      emit_ocel_event(node, receipt)              # DOES NOT EXIST at execution time
  standing := close_standing(bundle, records, ...) # mfw-pcp-standing:106 — exists but
                                                   # compares digests only; must be extended
                                                   # to assert full activity coverage
  ```
  The loop body is three existing calls. What is missing is the loop itself, execution-time
  OCEL emission, and a coverage check inside `close_standing`.
- **Implementation steps** (revised — reuse, don't rebuild):
  1. **Close G1 (format) first — this is now the critical path.** Three representations exist
     with zero converters: mfw Turtle, mfw-runtime JSON, bcinr `Pddl8Tape`/`PowlModel`. Write
     **one** converter and declare **one** canonical form. Cheapest defensible option: a
     Turtle→`PowlModel` reader in `bcinr-powl` (it already owns the model types), making mfw's
     existing `plan.powl.ttl` the interchange format instead of a dead end.
  2. **Do not write a new scheduler.** Use `execute_and_seal_v2_with_selector`
     (`bcinr-powl/src/receipt/execution_v2.rs:129`) — it already provides the tick loop,
     `max_ticks` bound, deadlock refusal, and BLAKE3 chaining that step 5 of the original plan
     asked for.
  3. **G3 — brokered plan-scale actuation. This is NOT a matter of calling
     `broker.actuate()` inside the loop, and an earlier draft of this plan said it was.**
     That framing is retracted: G1 and G2 are integration work, but G3 crosses from symbolic
     state into *authorized consequence*, and that boundary carries design questions no
     amount of wiring answers. The contract needed is:

     ```
     POWL activity becomes ready
       → scheduler selects an occurrence
       → activity maps to a canonical operation
       → broker validates model, proof, pre-state, authority, occurrence
       → actuator causes a bounded external effect
       → observed POST-state is captured
       → receipt and OCEL event refer to the SAME consequence
       → scheduler advances only after accepted evidence
     ```

     Open architecture questions, each of which must be answered before code:
     - What maps a POWL activity to an executable operation? (Today mfw has 3 file-write ops;
       bcinr has PDDL add/del effects. Neither is a general mapping.)
     - What external effects are *legally* available, and who decides?
     - What proves an effect **occurred** rather than merely being **requested**? A receipt
       for a request is not a receipt for a consequence.
     - Does failed actuation leave symbolic scheduler state unchanged? (bcinr ORs into
       `done_mask` immediately — that is correct for symbolic firing and wrong for actuation.)
     - Retries and duplicate occurrences — idempotency semantics.
     - What constitutes terminal completion of an activity?
     - How are compensating or irreversible actions represented?
     - How does the broker stay an authority boundary instead of becoming the scheduler?
     - How does plan-level standing prove N-of-N required consequences?

     Keep scheduling and authorization in separate components. The single most likely failure
     here is collapsing planning, authority, actuation, and verification into one component
     that then attests to itself.
  4. Execution-time OCEL: bcinr already emits `OCELEvent` per step (`execute.rs:128`). Route
     that through mfw's receipt store so the OCEL log and the receipt chain describe the same
     run. Today mfw's OCEL logs only the *solve* (`solve_rdf.rs:67`), never execution.
  5. Extend `close_standing` (`mfw-pcp-standing/src/lib.rs:106`) to compare bcinr's
     `state.done_mask` against the model's full activity set and refuse unless every required
     activity has a terminal receipt. Today it compares `goal_digest` only, so N=1 closes.
- **Negative fixtures** (each must refuse, not pass):
  - A POWL model where one activity's predecessor never completes → standing must NOT close.
  - A model whose `model_digest` disagrees with the proof → broker must refuse before any
    actuation (this path already works; the test guards against regression).
  - An execution that completes N-1 of N activities → must report `PARTIAL_ALIVE`, never
    `ALIVE`. This is precisely the N=1 hole in `demo()`.
  - Two activities in an exclusive choice both executing → must refuse.
- **Chicago acceptance test**: a multi-activity POWL model, executed end to end, where the
  resulting receipt chain replays (`mfw-pcp-replay::verify`) AND covers every activity in the
  model — asserted against the model, not against a digest.
- **Falsifiers**:
  - Standing closes `ALIVE` while some activity has no terminal receipt → the coverage check
    is not actually walking the model.
  - The driver executes activities in an order the partial order forbids → `ready_actions` is
    being bypassed.
  - Execution "succeeds" using `RecordingActuator` (`mfw-pcp-broker/src/lib.rs:499`), which
    pushes a digest onto a `Vec` and has zero world effect. A green run on that actuator is
    theater; the acceptance test must assert a real workspace effect.
- **Resume condition**: crown leaves `BLOCKED`. Only then is RP-6 (recursion) coherent.

### RP-6 — the recursive controller  *(owner: undecided — see note)*

- **Missing capability**: `Blocked → derive prerequisite → spawn child workflow → manufacture
  → independently verify → admit → resume parent`.
- **Blocker**: absent everywhere. `GallStatus::Blocked` exists as a *status label*; nothing
  consumes it to spawn anything.
- **Ownership is genuinely undecided and should be decided before implementation.** It cannot
  live in scikit-decide (planning must not authorize), and putting it in `ggen` would make one
  component infer, generate, evaluate and certify — the circular self-attestation the
  architecture exists to prevent. `mfw` is the doctrine owner and the only component already
  holding broker + receipt + replay, so it is the least-bad home, but it is `BUILD_BROKEN`
  (RP-2) today.
- **Prerequisite**: **RP-7 above, first and hardest** — plus RP-2, RP-1, and at least one of
  RP-3/RP-5. The controller composes stages that must each work alone first, and a recursive
  controller that spawns child workflows is incoherent while nothing executes a single
  workflow to completion.
- **Falsifier for any future claim**: a controller that resumes a parent without re-admitting
  the child's output is not the doctrine — *"A child's claim of completion is raw observation
  until re-admitted."*
- **Resume condition**: S7 leaves `UNSUPPORTED` only when a bounded, terminating loop is
  demonstrated on a real blocked workflow, with the child's admission independently receipted.

## THE DECISIVE QUESTION — ANSWERED

**Which implemented component executes the complete POWL plan today?**

> **`~/bcinr` does — symbolically. `~/mfw` does not. They are not wired together.**

**Correction, recorded rather than quietly edited.** An earlier version of this section answered
"None. Definitively none." That was **wrong**: the search was scoped to `~/mfw` and the
conclusion was stated over the whole ecosystem. `~/bcinr` — a fifth repo, surfaced only when
the user asked about it — contains a real POWL executor. The prior claim is retracted, and the
lesson is recorded because it is the same failure mode this file exists to catch: a negative
finding is only as broad as the search that produced it.

The corrected picture is sharper and more actionable than the wrong one. **mfw and bcinr are
complementary halves of one executor, and nothing connects them:**

| | plan driver (walks the model, fires activities) | world effect (actuation) |
|---|---|---|
| `~/mfw` | **ABSENT** — `broker.actuate` takes a singular `node_id` | **REAL** — confined atomic writes under a workspace root |
| `~/bcinr` | **PRESENT** — partial-order tick loop + OCEL + BLAKE3 | **ABSENT** — mutates an in-memory `BTreeSet<Pddl8GroundAtom>` |

### The executor that does exist (`~/bcinr`)

`crates/bcinr-powl/src/receipt/execution_v2.rs:129` `execute_and_seal_v2_with_selector`:

```rust
for _ in 0..max_ticks {
    match scheduler_tick_v2(tape, &mut state, selector, guards) {
        PowlV2TickOutcome::Fired(mask) => fired_masks.push(mask),
        PowlV2TickOutcome::Complete => break,
        PowlV2TickOutcome::Deadlock { remaining_mask } =>
            return Err(PowlV2ReceiptError::Deadlock { remaining_mask }),
    }
    if state.is_complete(tape) { break; }
}
let chain_root = digest_chain(&tape_root, &guard_root, &fired_masks, state.done_mask);
```

The tick body (`scheduler_v2.rs:67`) computes `ready_mask`, applies a pluggable selector, and
ORs the fired set into `done_mask`. `crates/bcinr-pddl/src/execute.rs:128` `execute_tape` is
the full BRCE loop — Prolog8 `may_fire` gate (`Pddl8Error::StepDenied` on refusal) → apply
add/del effects → BLAKE3 chain step → push `OCELEvent` → returns
`(Pddl8ExecutionLog, Pddl8ExecutionReceipt, OCEL)`.

Note the architectural contrast: mfw's broker returns to the caller after authorizing one
action; bcinr puts the admission gate *inside* the loop. Both are defensible; they are not
composable as-is.

### The three gaps that remain (revised)

**G1 — format/ingestion.** mfw emits POWL as **Turtle** (`solve_rdf.rs:459`); mfw's runtime
ingests **JSON** (`config.rs:86`); bcinr consumes **Rust structs / `Pddl8Tape`**. There is no
Turtle→`PowlModel` reader **in either repo**. Three representations, no converters. This is now
confirmed from both ends rather than inferred from one.

**G2 — driver placement.** mfw has no plan loop. But bcinr *has* one, so RP-7 changes from
"build an executor" to "**wire the existing executor to the existing broker**" — a materially
smaller and better-specified job.

**G3 — actuation, and this one is genuinely open.** Neither repo closes it. bcinr fires masks
and mutates in-memory state — zero external effect. mfw actuates for real but only through 3
file-write operations, and its PCP lane's sole `Actuator` (`RecordingActuator`,
`mfw-pcp-broker/src/lib.rs:499`) pushes a digest onto a `Vec`. **The step where a fired POWL
activity causes an effect in the world is absent from both.**

### Caveats that bound the above

- `~/bcinr` has **no `target/`** — nothing compiled locally. The executor is CI-tested code;
  there is no local build artifact to cite as a run this session. Requires nightly Rust.
- `bcinr-powl` is an **optional** dependency of `bcinr-pddl`, behind the `mfw-planner` feature
  (`bcinr-pddl/Cargo.toml`, `lib.rs:16-18`). So `cargo test -p bcinr-pddl` — the line in
  `ggen-legacy`'s justfile — does **not** compile the POWL execution path by default. Anyone
  citing that command as proof of execution is citing the wrong thing.
- bcinr's own `CLAUDE.md` is stale (documents `bcinr-api`, `bcinr-mcp`, `bcinr-pddl-lsp`,
  `bcinr-bench`; those directories are gone, removed as out-of-scope per `Cargo.toml:7-25`).

The crown remains **`BLOCKED`** — but for a corrected reason: not "no executor exists," rather
"an executor exists, it is symbolic, and it is not connected to the actuating half."

### Per-transition ownership

| # | Transition | Standing | Evidence |
|---|---|---|---|
| 1 | receive selected plan | **ABSENT** | `mfw-planner/src/solve_rdf.rs:459` writes `plan.powl.ttl`. Repo-wide, the only readers are the planner's own tests (`tests/solve_rdf.rs:45`, `ticket11_fixture.rs:26`, `ticket11_jira_bundle.rs:53`). **No executor, broker, or runtime crate parses Turtle POWL.** Write-only export format. |
| 2 | project/admit as POWL | OWNED (planner-internal) | `mfw-planner/src/projection/powl_rdf.rs:132` `emit_powl_ttl`. Runtime-side admission is `mfw-rmcp/src/proof.rs:309`, fed by a *different* source (see gap G1). |
| 3 | SHACL-validate POWL | **OWNED, genuinely invoked** | `solve_rdf.rs:27` `include_str!("../shapes/powl2.shacl.ttl")`, called at `solve_rdf.rs:457` `shacl_validate(&powl_ttl, POWL_SHAPES, ...)`. A real call, not a file on disk. Validates at *write* time; nothing re-validates at execution time. |
| 4 | bind model/proof digests | OWNED, per single node | `mfw-rmcp/src/broker.rs:24-33`, enforced ~`:239-260`. Bound to one node, never to a plan. |
| 5 | authorize **each** action | OWNED, **one per request** | `mfw-rmcp/src/broker.rs:118` `pub async fn actuate(&self, request: ActuationRequest) -> Result<Receipt>` — `node_id: String`, singular. The broker never iterates a model's activities. PCP lane同: `mfw-pcp-broker/src/lib.rs:234` takes one `CanonicalAction` and `:216` rejects concurrency outright. |
| 6 | execute the actions | OWNED but trivial | "Closed native operation algebra" = 3 variants (`mfw-rmcp/src/powl.rs:8-25`): `WriteLevel5Pack`, `RecordLevel5Evidence`, `GenerateRmcpModule`. Runtime tree likewise 3 (`CreateDirectory`, `WriteFile`, `MaterializeLevel5Pack`). **No spawn, no process exec, no network.** Effect = bytes appear under a canonicalized workspace root. In the PCP lane the only `impl Actuator` is `RecordingActuator` (`lib.rs:499`, `actuate` at `:505`) which pushes a digest onto a `Vec` — **zero world effect**. |
| 7 | OCEL + hash-chained receipts | **SPLIT ACROSS LANES** | Receipts real: `broker.rs:122/154/186` via `ReceiptStore::append`, chain verify `:109`. But OCEL exists **only in the planner** (`projection/ocel_rdf.rs`, `solve_rdf.rs:67`) and logs the *solve*, not execution. **Execution emits no OCEL at all.** |
| 8 | verify / replay | OWNED (PCP lane only) | `mfw-pcp-replay/src/lib.rs:45` `verify(records)`, `:60` `records.chunks_exact(2)`. Replays *receipts*; has no POWL model in scope. |
| 9 | **plan** completed with standing | **STRUCTURALLY ABSENT** | `mfw-pcp-standing/src/lib.rs:106` `close_standing(...)` compares `goal.goal_digest != bundle.plan.body.goal_digest` — "plan" is only a **digest**. The POWL structure is never walked, so **nothing checks that every required activity ran**. Standing can close on a single action, and in its only caller it does: `mfw-pcp-cli/src/main.rs:94` `demo()` builds ONE hard-coded `CanonicalAction` (`:97-118`), one `open`, one `actuate`, then `close_standing` (`:154`) prints `ALIVE`. Plan-completion over N=1. |

### The two disjoint gaps

**G1 — ingestion gap.** The planner emits POWL as **Turtle**; the runtime ingests POWL from
**hand-authored JSON** (`mfw-rmcp/src/config.rs:86` `load_json_files(&config.powl_models)`,
field at `config.rs:28`). These are two unconnected pipes. A plan computed by any planner
cannot reach the broker without a human retyping it as JSON.

**G2 — driver gap.** No loop anywhere walks a plan and drives execution. The only
POWL-topology-aware functions are `ready_actions` / `maximal_cohort`
(`mfw-rmcp/src/powl/validation.rs:156-158`), and their only non-test callers are the
**read-only MCP advisory tools** `server.rs:145` (`powl_ready_set`) and `:160`
(`powl_maximal_cohort`). They compute what *could* run next and return it. Nothing consumes
that answer and actuates it — **the client (a human, or an LLM) is the scheduler.**

Architecturally: `planner → plan.powl.ttl → (dead end)`. Separately and unconnected:
`JSON POWL → broker → one authorized file-write per request → receipt`.

This does not diminish what is real — SHACL validation, digest binding, receipt chaining,
replay, and confined atomic writes are all genuinely implemented. It locates precisely what is
not: **the connective tissue that turns a validated plan into an executed workflow.**

## How to read this

- **measured win** — command run this session, output quoted above, passed.
- **recorded negative** — attempted, genuinely blocked, blocker named precisely enough that
  the next pass does not rediscover it from zero.
- **deferred / scoped** — a plan exists; nothing under it executed. Every repair plan above is
  in this category until it appears as a measured win.

## See also

- `docs/STATUS.md` — the in-repo WIP ledger this file extends across repositories.
- `tests/ecosystem/test_chatman_chain_chicago.py` — the crown test.
- `tests/domains/python/test_career_admission_unit.py` — the demoted unit checkpoint; carries
  a scope warning so it is not cited as ecosystem evidence.
- `.claude/rules/standing-law.md` (status vocabulary), `.claude/rules/actuation-boundary.md`,
  `.claude/rules/ecosystem-boundary.md` (why this repo claims candidate plans and nothing more).
