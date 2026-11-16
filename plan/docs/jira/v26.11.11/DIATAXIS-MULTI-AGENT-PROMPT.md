# DIATAXIS-MULTI-AGENT-PROMPT: test-backed Diataxis suite for Rules and Plans

/teamwork [skip-interview]

Standing: UNVERIFIED (prompt text, nothing executed)

## 0. MISSION

Build `docs/diataxis/` in `/Users/sac/plan`. It is a four-quadrant Diataxis documentation
suite for commercial founders and operations leaders. It explains and proves how **Rules**
(central guardrails) and **Plans** (automated playbooks) run a multi-vertical
facilities-fulfillment business. Together they protect gross-margin spread and let leadership
change runtime discretion without editing code.

Every tutorial step, how-to recipe, reference row and explanation claim must be backed by a
real, non-vacuous test. The tests use Chicago-style real collaborators: `factory_boy`/Faker,
TOML bounds, the real solvers, the real ledger, real headless Chromium, and `pm4pytest`
conformance. A fail-closed gate, `just diataxis-check`, enforces all of it.

Operator instruction: write and update code. When something cannot be done as specified, do
the closest lawful thing and record the gap as `UNSUPPORTED[<exact_gap>]` in the doc and in
the receipt. Do not stub it, fake it, or pass it off as working.

## 1. REPO, PATHS, GIT AND FLEET LAW (applies to every lane)

- **Canonical checkout:** `/Users/sac/plan`. One checkout. No worktrees, clones or per-agent
  copies. Lanes are not copies of the repo.
- **Absolute paths:** every subagent prompt names its repo path explicitly (`/Users/sac/plan`)
  and its owned files.
- **Git:** agents never run git state commands (no add, commit, stash, checkout, reset,
  rebase or push). The coordinator owns all git transitions.
  - Stage explicit paths only. Never `git add -A`.
  - Commit with `git commit -F <file>`, never inline `-m`.
  - Fix forward only. No `reset --hard`. Never rebase or force-push. Merge only.
  - After any push, verify with `git ls-remote | grep $(git rev-parse HEAD)`. Do not trust
    push output.
  - Run `git status` right after generating any file a test or gate needs. A file that is
    present locally but untracked fails every fresh checkout.
- **Shared files** (`pipeline/enterprise_pipeline/store.py`, `staged.py`, `align.py`,
  `console.py`, `ledger/*`, `spec/servengine_ideal_domain.pddl` and its copies) are edited
  serially, one owner at a time. Disjoint new files (`pipeline/tests/diataxis/*`,
  `docs/diataxis/*`, `scripts/verify_diataxis.py`, `justfile.d/95-diataxis.just`) can be
  written in parallel.
- **Compile-freeze SLA:** a lane that breaks the shared import or compile fixes or reverts
  within about 10 minutes. Any lane may apply a minimal unblock to another lane's file.
  It must name the fix in both lanes' receipts.
- **Dead lanes:** a lane killed by 429 or abort may have written partial edits and no receipt.
  Inventory its owned files on disk with a scoped `git status` and a receipt-existence check.
  Do not resume its report as truth.
- **Build isolation:** any per-lane scratch dir (`/tmp/diataxis-lane-<N>/`) is a lease. The
  coordinator deletes every lane scratch dir before the final commit.
- **Poll discipline:** no fixed sleeps. Use bounded polls with `Instant`/`time.monotonic()`
  deadlines on real observables. `pgrep -f X` matches its own shell, so filter it out or match
  the child binary. Capture `rc=$?` un-piped.
- **Ring discipline:** land code changes in monotonic rings. `just check` must stay green
  after every ring, with the real output cited. After a failing early gate is fixed, expect
  newly exposed failures in later gates and budget for the cascade.
- **Ontology trap:** `ontology/servengine.ttl` is generated from the PDDL. Regenerate it after
  any PDDL edit so the gate-root (L10) check stays byte-identical and SHACL-valid. Never
  hand-edit generated output. `~/ggen` and `~/ggen-marketplace` are available for projections.
- **Backend law:** this repo is the planning kernel. Do not point anything at `:3002`. Do not
  re-introduce the legacy-prefix surface.

## 2. CONTRACT BLOCK (paste into every lane prompt)

```
LANE:          <id>
REPO:          /Users/sac/plan   (single checkout, no worktrees)
OWNED FILES:   <exact paths this lane may write; everything else is read-only>
READ-ONLY:     everything not listed above
GATES:         <commands that must exit 0, with the expected output substring>
COURTS:        <the positive test and the anti-vacuity twin for this lane>
WAIT-GATES:    <named files or lanes to poll, <=60s poll step, <=45min cap,
                typed IN-FLIGHT-AT-FILL fallback>
PORTS:         <ports used; private ports only; fds closed on spawn>
GIT:           none (coordinator owns git)
SEED:          PLAN_TEST_SEED=<n>   (replay must be identical)
RECEIPT:       receipts/diataxis-<lane>.md
               - H1, then a blank line, then "Standing: <ALIVE|PARTIAL_ALIVE|PASS|
                 BLOCKED|UNVERIFIED|PARTIAL>" (closed vocabulary)
               - exact base SHA, commands run, exit codes, real output excerpts
               - tests added (node ids), files touched, collisions disclosed
               - UNSUPPORTED[...] and BLOCKED (file:line) rows
```

Receipt rules:
- Counts are re-read from disk at fill time. A count recalled from earlier in the session is stale.
- Distinguish failures that were already present from failures this session introduced.
- Never report done without the real gate and its actual output.
- Re-read each edited file on disk after the edit.

## 3. VOICE AND AUDIENCE

- **Audience:** commercial founders and operations leaders. They run entities, P&Ls,
  dispatch floors, broker contracts and field margins.
- **Register:** Tutorial, How-To and Explanation read at that level. They are not academic and
  not condescending.
- **Banned jargon** in `01-TUTORIAL.md`, `02-HOW-TO-GUIDES.md` and `04-EXPLANATION.md`:
  `PDDL`, `PDDL 2.1`, `MiniZinc`, `CP-SAT`, `satisficing`, `timed initial literals`, `TIL`,
  `delete-relaxation`, `token-based replay`, `inductive miner`, `Petri`, `OCEL`, `SHACL`,
  `aries`. Solver and file mappings live only in `03-REFERENCE.md`.
- **Preferred terms:**
  - Rules (Guardrails)
  - Plans (Automated Playbooks)
  - NTE Cost Ceiling
  - Internal Reality Clock
  - Client Proposal Clock
  - GPM Safe-Harbor
  - Desolate-Market Immunity
  - Site Exclusion vs. Global Ban
  - Internal Photo Vault
  - Executive Single-Visit Override
  - Completed Barrel
- No `TODO`, `TBD`, or placeholder text anywhere in `docs/diataxis/`.

## 4. THE FOUR QUADRANTS (strict separation)

| File | Quadrant | Content | Forbidden |
|---|---|---|---|
| `01-TUTORIAL.md` | Learning | One unbroken journey from an empty store (0 entities, $0.00) to a settled work order | branches, tangents, reference tables |
| `02-HOW-TO-GUIDES.md` | Task | Seven short repeatable recipes | teaching from zero, theory |
| `03-REFERENCE.md` | Information | Generated tables: dials, events, refusals, dimensions, lifecycle | narrative, opinions |
| `04-EXPLANATION.md` | Understanding | Why Rules and Plans together replace the filing-cabinet model | step lists, tables of keys |
| `INDEX.md` | Navigation | Links to all four, a status legend, and the list of `UNSUPPORTED[...]` items | content duplication |

## 5. ZERO UNVERIFIED PROSE

A workflow, dial, command or UI flow may be documented as working only if a test under
`pipeline/tests/diataxis/` runs it end-to-end against a blank store and proves both of these:

a) **Positive execution:** exit code 0. A real state change is admitted. Real solver or
   ledger output is verified. `pm4pytest` conformance fitness equals 1.0.

b) **Anti-vacuity twin:** withholding the required fact, or violating the guardrail,
   deterministically triggers the documented refusal (`MISSING[...]`, `REFUSED[...]`,
   `BAD_DIM[...]`, `NteCap`, `MarginGuard`, `NO PLAN`). A test that cannot fail is vacuous
   and is itself a defect.

Statuses in docs and receipts come from a closed vocabulary:
- `ALIVE`: ran this session. Cite the command and exit code.
- `PARTIAL`
- `BLOCKED`: cite file:line.
- `UNSUPPORTED[<gap>]`
- `UNVERIFIED`: the default. Never round up.

## 6. ZERO HARDCODED FIXTURES IN THE BACKING TESTS

- Prose may use clear illustrative numbers. Runnable blocks must execute in a scratch temp store.
- Every `pytest` suite under `pipeline/tests/diataxis/` synthesizes every identifier, labor
  rate, NTE, SLA, date and uploaded byte stream with `factory_boy`/Faker, seeded by
  `PLAN_TEST_SEED`.
- Relational bounds come from TOML (extend `pipeline/tests/scenario_envelopes.toml` or add
  `diataxis_envelopes.toml`). For example `client_rate > provider_rate` and
  `complete_sla > onsite_sla`.
- No `time.sleep` outside one audited bounded-deadline poll helper.
- Reuse existing capital: `pipeline/tests/mega_factories.py`, `jtbd_factories.py`,
  `ui_driver.py`, `ui_plan.py`, `conftest.py` and `plankinds/`. Do not reinvent them.

## 7. THE SEVEN COMMERCIAL BEHAVIORS

Wave 1 audits each one. Wave 2 implements or labels each one. Current known state, to be
re-verified on disk (it may be stale):
- Territory flag and the `sales_rep_notified` event: laws #6/#7 were not landed. A primary
  client's out-of-coverage job currently stops with NO PLAN.
- `clock_policy` and the GPM/desolate-market dials: planned and open. Their thresholds are
  OPEN in `docs/jira/v26.11.11/OPEN.md`.
- Repair-to-project link fields (`link_kind`, `parent_wo`) and visit lists: planned. The
  change-order and override events do not reach the ledger from the UI yet.

For each behavior: build it in monotonic rings if it is missing and `just check` stays green,
or label it `UNSUPPORTED[<exact_gap>]`.

### B1. Completed Barrel: vertical spin-up
Create a new internal operating entity with a DBA, its own compliance docs (`ss4_doc`,
`w9_doc`), bound brand/templates (`templates_bound`), clients and rates, from a blank slate.
Same processes, different outfit, with zero code edits.
- Positive: the second vertical dispatches and settles. The first vertical's state is
  byte-identical afterward.
- Twin: with `templates_bound` or a compliance doc withheld, the documented refusal fires.
- Depends on the multi-entity work (law #25). If it has not landed, this behavior is
  `UNSUPPORTED[multi-entity: SINGLE_ENTITY_STORE]`.

### B2. Two-tier vendor escalations
- Global Ban: `invoice_left_on_site` leads to `provider_blacklist`. Dispatch and payout are
  blocked across every entity, DBA and site.
- Single-Site Exclusion: `site_manager_clash` leads to a `provider_filter` on `exc_site`. The
  provider is blocked at that site only and stays eligible elsewhere for the same client.
- Positive and twin for each tier. One test proves the exclusion does not leak to another site.

### B3. No "divide NTE by 2"; ranked zero-touch dispatch
Auto-dispatch evaluates all 10 alignment dimensions (`brand, client, entity, prio, coord,
site, state, sub, trade, wotype`), live COI/license expiry, unified rank (1-20) and cost and
margin caps with no human babysitting. It hands off to a human only when zero aligned
providers qualify (`reactive-hire-triggered`). It queues recruiter outreach once a reactive
provider is paid.
- Twin: with an expired COI or `provider_rate >= client_billable_rate`, the provider is refused
  (`MarginGuard`).
- Open item: hand-off semantics (end at hand-off or continue) is a recorded OPEN switch. Do not choose it.

### B4. Internal Photo Vault and two-stage gate
Field photos stay internal by default. Asset replacement and asset surveys require a
`model_tag_photo`, verified by the SHA-256 of the real uploaded bytes, before invoicing can be
planned. Upload surfaces an immediate missing-media prompt. Only QA-approved `before`/`after`
photos become client-visible.
- Twin: the tag is left out, which gives `MISSING[...]` at the Stage-2 gate. A different byte
  stream gives a different SHA.

### B5. Two clocks, GPM and desolate-market discretion
- External Client Clock: client arrival window and `proposal_quote` duration. It drives AR
  billing and never overwrites internal reality.
- Internal Reality Clock: real check-in/check-out timestamps. It drives AP payout through
  TOML dials in `pipeline/policy_dials.toml`, parsed with `tomllib`:
  - `gpm_safe_harbor_bps`
  - `low_rate_safe_harbor_cents`
  - `desolate_market_min_providers` (fewer than N aligned providers in `(state, trade)`)
  - `default_nte_cost_share_bps`
  - `clock_policy` (default `strict_internal`)
- The dials hold no business names.
- Positive: a dense-market high-rate technician is policed to real time. A high-margin
  low-rate technician, or the sole trusted provider in a desolate market, is paid without clock policing.
- Anti-vacuity: edit a dial in a temp TOML and show the payout and dispatch outcome flips
  at runtime with no code change.
- The thresholds are OPEN. Encode each as a TOML switch with a differential court. Do not choose values.

### B6. Primary vs. secondary territory
- Out-of-territory job for a Primary client: plan and execute normally. Emit `territory_flag`
  and `sales_rep_notified`.
- Out-of-territory job for a Secondary client: it requires a `parent` primary brand, and
  `quick_add` is primary-only. Automated dispatch is refused with NO PLAN unless an explicit
  `territory_waiver` is recorded.
- Update the continuum expectation for the CVS work order to match.

### B7. Executive baton overrides and over-NTE paths
- `nte_override_receipt`: the margin is absorbed internally for one visit.
- `change_order_approved`: raises the client NTE.
- `dispatch_override`: bypasses soft alignment filters for one visit and never bypasses
  `provider_blacklist` or a missing W-9.
- Twin: an override attempted against a globally banned provider is refused. An over-NTE
  charge with no receipt gives an `NteCap` refusal.
- Open items: who owns the NTE that caps a change order, and whether a change order waits
  for its parent. Both are OPEN switches.

## 8. WAVE PLAN

### WAVE 1: reality probe (read-only, 1 to 10 Explore lanes)
Each lane reads and writes nothing except its receipt.
- **D0** code inventory: `store.py`, `staged.py`, `align.py`, `ledger/`, `console.py`,
  `spec/servengine_ideal_domain.pddl`, `pipeline/tests/`. Output one row per behavior B1-B7
  with: exists / missing / partial, the file:line of the hook, the event or dial that must be
  added, and the exact `just check` baseline with its real output.
- **D1** dial census: grep for hardcoded thresholds that should become dials.
- **D2** event and refusal census: every `kind`, every `Refused(...)` code, and `align.DIMS`.
- **D3** test-capital census: reusable factories, drivers and `.results` writers.
- **D4** UI census: which console views and forms exist for each behavior.
- **D5** `docs/jira/v26.11.11/LAWS.md` and `OPEN.md` cross-check: which laws have landed.
Output: `docs/diataxis/_GAPS.md`, a machine-readable gap map. The coordinator resolves
conflicts between lanes before Wave 2 starts.

### WAVE 2: close gaps and build tests first (code and tests before prose)
Serialize edits to `store.py`, `staged.py`, `align.py`, `console.py` and the PDDL. Parallelize
disjoint test modules.
- **T1** (`pipeline/policy_dials.toml` and the hooks). Add the dials in B5 and the hooks that
  read them in `staged.py` and `ledger/`. Regenerate `ontology/servengine.ttl` if the PDDL
  changed. Gate: `just check` PASS.
- **T2** (`pipeline/tests/diataxis/test_tutorial_walkthrough.py`). Blank store, then entity,
  client, provider, work order, auto-dispatch, geofenced check-in and check-out, model-tag
  byte upload, invoice and payout settlement. `pm4pytest` fitness 1.0 with bounded allowed
  transitions, plus the anti-vacuity twin (model tag omitted gives `MISSING[...]`).
- **T3** (`pipeline/tests/diataxis/test_howto_playbooks.py`). A positive and a twin for each of:
  1. `test_howto_new_vertical_dba_isolation`
  2. `test_howto_global_ban_vs_single_site_exclusion`
  3. `test_howto_tune_gpm_and_desolate_market_dials`
  4. `test_howto_primary_sales_lead_vs_secondary_territory_hold`
  5. `test_howto_internal_photo_vault_and_model_tag_gate`
  6. `test_howto_executive_override_and_over_nte_change_order`
  7. `test_howto_reactive_hire_handoff_and_recruiter_queue`
- **T4** (`pipeline/tests/diataxis/test_ui_diataxis_smoke.py`). Real headless Chromium through
  `ui_driver.py`. The UI forms and feedback must match the Tutorial and How-To text. Reuse
  `live_server`, `new_context` and the lazy `ui_driver` fixture.
- Gate for each lane: lane tests, then the existing 8-plan suite (4 pass, 4 fail) unchanged,
  then `just check`. A byte-diff of `compile_wo` and dzn output for the 8 plans before and
  after must be empty unless the change is the intended one.

### WAVE 3: author the quadrants (bound to Wave 2 tests)
Every section carries `<!-- VERIFIED-BY: <pytest_node_id> -->` and, where applicable,
`<!-- DIALS: key1, key2 -->`. A section for an unsupported behavior carries
`<!-- UNSUPPORTED: <gap> -->` and says so in plain text.
- **W1** `INDEX.md` and `04-EXPLANATION.md`. How Rules and Plans run the business together.
  Cover:
  - Why a digital filing cabinet looks 80% done and fails Monday morning.
  - Rules are the sidelines and Plans are the play calling.
  - How the two clocks, discretion, territory sales leads, photo shielding and single-visit
    overrides give runtime flexibility without chaos.
  - Why growing from a verified blank-slate core, checked with real boundary tests, means
    every green result is backed by state and cash math and not by mocks.
- **W2** `01-TUTORIAL.md`. "From empty ledger to settled job in 10 minutes." Runnable
  commands plus the exact console steps (views A to F). It shows real outputs and the
  intentional refusal when the compressor model tag is left out. Mark runnable blocks with a
  fenced `bash runnable` info string.
- **W3** `02-HOW-TO-GUIDES.md`. One page per playbook (B1-B7). Each has: when to use it, exact
  steps or the dial to turn, what the Plan produces, and what the Rule refuses if violated.
- **W4** `03-REFERENCE.md` plus `scripts/extract_reference.py`. Generated from AST, TOML and
  domain introspection:
  1. Runtime dials (key, type, range, effect)
  2. Store event schema (kind, avatar, required and optional fields, stage precondition)
  3. Typed refusal dictionary (`MISSING[...]`, `REFUSED[...]`, `BAD_DIM[...]`, `UNKNOWN[...]`,
     `NteCap`, `MarginGuard`, `NO PLAN`)
  4. The 10-dimension alignment table
  5. Work-order lifecycle and dual-clock settlement formulas

### WAVE 4: fail-closed verifier and aggregate gate
Create `scripts/verify_diataxis.py` and `justfile.d/95-diataxis.just`, then import it in the
root `justfile`. Add it to `just check` only if the tree stays green. Recipes called from the
root resolve directories via `parent_directory(justfile_directory())`, so test the
`--justfile` form too. `diataxis-check` exits nonzero if any of these fail:
1. **Test-link resolution:** parse every `VERIFIED-BY` marker. Confirm each tutorial step and
   how-to recipe has a positive test and a twin. Run pytest on them (`rc == 0`).
2. **Runnable-block runner:** execute every `bash runnable` block in an isolated temp
   `PLAN_STORE`. Assert exit codes and expected output substrings.
3. **Reference drift:** re-extract event kinds, `Refused(...)` codes, `align.DIMS` and dial
   keys. Fail on any undocumented item and on any phantom item in `03-REFERENCE.md`.
4. **Purity and jargon lint:** fail on banned jargon, `TODO`/`TBD`/placeholders, hardcoded
   entity, client or rate literals in `pipeline/tests/diataxis/`, and unguarded `time.sleep`.
5. **Gate non-vacuity:** in a scratch copy, rename one dial key and break one marker. Confirm
   the verifier exits 1. Restore the files and verify them byte-exact with sha256. A skip is
   loud (`[SKIP] <reason>`), never a faked pass.

## 9. COORDINATOR DUTIES AND FINAL RECEIPT

- Order: Wave 1, resolve conflicts, Wave 2 (serial on shared files), Wave 3, Wave 4, audit.
- Same-turn refill: when a lane finishes and backlog remains, dispatch the next item in the
  same turn. Audit the fleet (ListAgents and the backlog) before anything else each turn.
- Nudge a lane that is silent past about 37 minutes, offering a partial-honest landing.
- Saturation: stop re-waving when findings per wave and their severity are both below
  threshold. A wrong constant or a compile break means fix and re-wave.
- Before staging: delete lane scratch dirs, confirm no new build or `.results` dirs are being
  swept in, and check `git status` for untracked files that a test needs.
- Write `receipts/diataxis-final.md` with the real scorecard:
  - Exact subject: branch and SHA.
  - Commands and exit codes for `just check`, `just diataxis-check`, and
    `just --justfile justfile.d/45-ui.just ui-chicago`.
  - Seed replay result (two runs, identical outcome).
  - Per behavior B1-B7: ALIVE, PARTIAL, or `UNSUPPORTED[<gap>]`, with the test node ids.
  - OPEN switches left unchosen, listed with their TOML keys.
  - Failures that were already present vs introduced this session.
  - Push verification output from `git ls-remote`.
- Never claim planned, inspected or inferred work as executed.
