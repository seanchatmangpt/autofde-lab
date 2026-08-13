# PRD/ARD — Receipted Cloud-Certification Trials (WBPR: "Autonomous Expert-Level Certification")

## Executive summary

This document is the implementation spec for the working-backwards press release written this
session: an OCEL-v2-receipted cloud-certification system built on `autofde-lab` (planner) and
`gymact` (actuation), where a certification claim resolves to a replayable, hash-chained trial
against a real environment instead of an exam score.

**Standing, stated per `.claude/rules/standing-law.md` before any other section**: this PRD
targets a real, buildable system with real precedent in both repos, but a 5-agent audit
(2026-08-12, logged in `docs/jira/v26.8.12/`) found this document's own grounding section
contained factual errors — corrected below, in place, rather than left standing. As corrected,
this PRD is `PARTIAL_ALIVE`, and materially less far along than its first draft implied: the
receipt format and planner/broker separation are real; of the four target security domains,
only **AzureGoat has any real actuation bridge at all**, and that bridge's own `verify()`
already violates this PRD's own actor/verifier-independence rule (see Correction 4). CloudGoat
and kube-goat have real domain-planning code but explicitly disclaim actuation in their own
docstrings; **GCPGoat has no domain module in this repo at all**. Nothing in this document
claims `enterpriseStanding`; a receipted trial is a `technical consequence`
(`.claude/rules/fde-authority-boundary.md`), never a certifying body's adoption decision. This
PRD does not claim to *be* an AWS/Azure/GCP certification — it claims to produce evidence of
equivalent competency, receipted to a higher standard than an exam score is.

## Corrections (2026-08-12, 5-agent grounding audit)

The claims below, made in this document's first draft, were checked against real code and
found wrong or unsupported. Corrected here rather than silently fixed, per this session's own
"correction = re-derivation" discipline — each correction changes what downstream sections
(FR1–FR5, Rollout) actually require:

1. **`ocel_standing.py` does not exist anywhere in this repo.** The Receipt/ledger ARD bullet
   cited it as "already real" — false; no file of that name was found. The nearest real code
   is `src/autofde_lab/standing.py` (a standing-vocabulary *type system*, not an OCEL-log
   aggregator) and `scripts/ocel_procint_report.py`/`ocel_failure_signatures.py` (aggregate
   OCEL stats to stdout, no write-back, wrong name and wrong shape for FR3's ledger).
2. **JSON and SQLite OCEL are not one model with two serializers**, contrary to FR5's
   assumption. Three independent producers exist: `gymact.ocel` (JSON only — what every
   `*goat` episode script uses today), `autofde_lab.ocel.log` + `sqlite_store.py` (JSON+SQLite,
   one shared model — this is what produced the sregym `.ocel2.sqlite` files), and no bridge
   between them. "SQLite-first for Professional tier" requires either a new
   `receipts_to_sqlite()` in `gymact.ocel` or an adapter routing gymact receipts through
   `autofde_lab.ocel.log` first — not a trivial format swap.
3. **GCPGoat has no domain wrapper under `hub/domain/` at all** — not "code exists, no OCEL
   log yet" as this document's grounding section originally implied. Only
   `azuregoat_privesc`, `cloudgoat_iam_privesc`, `k8s_goat_rbac_escalation`, and `terragoat`
   exist; a GCPGoat domain module is net-new work, not a missing episode script.
4. **AzureGoat's existing `verify()` already violates this PRD's own ARD (Non-functional
   requirements, "verifier step... never collapsing proposer and verifier into one call").**
   Its `verify()` calls `await self.observe()` against the same in-process state `actuate()`
   just wrote — self-report, not an independent check — unlike
   `kubernetes_reconciliation.py`'s real `kubectl get` poll, which is the actual pattern this
   PRD describes. AzureGoat was treated as the working template for FR1; it needs its own fix
   before being replicated, not just copied.
5. **FR4's "replay" name collides with an existing, different capability.** `gymact replay`
   already exists (`gymact/src/gymact/replay.py` + its CLI subcommand) but means ledger/chain-
   hash **integrity** verification (`ReplayMode.EVIDENCE_REPLAY`) — it never re-derives a
   verifier's pass/fail from a log, and its own docstring states this ("replay validates
   evidence and never silently actuates"). This exact collision is already named in gymact's
   own docs (`2026-08-12-gymact-process-mining-reading-van-der-aalst.md` §6, "the replay false
   friend"). FR4 needs a distinctly-named new capability, not a rename or reuse of the
   existing one.
6. **FR2's "reuse the Pass-20 stride-sampling method" is not reusable code.** The STATUS.md
   Pass 20 stride-5 sample was a one-off manual operation (sort the registry, take every 5th
   ID), never committed as a function. `ProblemRegistry.get_problem_ids(all=True)` (sregym-
   specific, 17 lines) only returns all IDs unordered — there is no sampler to generalize;
   FR2 must write one from scratch.
7. **None of the four `*goat` domains have a scenario-variant registry.** Each models exactly
   one fixed scenario/state machine today (confirmed by direct read of all four domain files).
   FR2's Professional tier ("stride-sampled... via the domain's own registry") has nothing to
   sample from until multi-scenario registries are built per domain — real domain-modeling
   work (transcribing additional attack-path variants from each upstream vulnerable-by-design
   repo), not a sampling-utility problem.

## Grounding: what already exists, real, in this repo and its ecosystem

- `~/gymact/src/gymact/gyms/` — 24 real gym provider modules; 23 are real actuation surfaces
  (subprocess/Docker/K8s/HTTP), confirmed this session by direct inspection. Relevant ones for
  this PRD: `kubernetes_reconciliation.py` (real `kind`/`k3d`/colima cluster, real `kubectl`),
  `terraform_plan.py`/`terraform_docker_apply.py` (real `terraform`/`tofu`, local Docker
  backend), `sregym.py` (live `fastmcp.Client` against real kubectl/Jaeger/Loki/Prometheus MCP
  routes). `multicloud.py` is explicitly out of scope for this PRD — its own docstring states
  it is simulated, zero cloud SDK, zero network I/O; it is a reasoning aid, not an actuation
  surface a certification trial can run against.
- `~/autofde-lab/src/autofde_lab/hub/domain/{azuregoat_privesc,cloudgoat_iam_privesc,
  k8s_goat_rbac_escalation,terragoat}/` — four real domain wrappers (note: `terragoat`, not
  `terragoat_remediation` — the file is `terragoat/terragoat_remediation.py`), backed by real
  vendored submodules (`forwardbench-{azuregoat,cloudgoat,gcpgoat,terragoat}`, confirmed live
  under `.git/modules/`), each with real tests (`tests/domains/{python/,}test_*_unit.py`).
  **Per Correction 3, no GCPGoat domain module exists** — this is a four-way family in name
  only (Azure/AWS/K8s + a Terraform-findings domain), not yet four-cloud. **Per Correction 4,
  only `azuregoat_privesc` has any gymact actuation bridge**, and it self-reports rather than
  independently verifying.
- `~/autofde-lab/reports/ocel/azuregoat-privesc-gymact/episode.ocel.json` and
  `~/autofde-lab/scripts/run_azuregoat_gymact_ocel_episode.py` — the one existing, real,
  end-to-end example of this pattern. **Per Correction 4, this template's own `verify()` needs
  a fix before FR1 replicates it** — "do that three more times" is no longer accurate; it's
  "fix the template, then build three more from the corrected version."
- `~/autofde-lab/docs/ocel/sregym/anon_*.ocel2.sqlite` — proof that `autofde_lab.ocel` can
  produce OCEL 2.0 in the schema-rigorous **SQLite** encoding. **Per Correction 2, this is a
  separate producer from `gymact.ocel`** (which is what the `*goat` episode scripts actually
  use) — "standardize on SQLite" requires reconciling the two, not a serializer flag.
- `~/autofde-lab/docs/STATUS.md` Pass 20 — real precedent for the *discipline* of stride-
  sampled, representative-draw measurement over hand-picked best trials. **Per Corrections 6
  and 7, the sampling code itself is not reusable (never committed as a function) and none of
  the four `*goat` domains have a registry to sample from** — FR2 reuses the discipline, not
  any code, and needs per-domain scenario registries built first.
- `.claude/rules/fde-authority-boundary.md` — "technical consequence" vs. "adoption decision"
  vs. "verifier verdict" as three non-interchangeable kinds. This PRD's non-functional
  requirements are built directly on that table.
- `.claude/rules/standing-law.md` — the six-value standing vocabulary
  (`ALIVE`/`PARTIAL_ALIVE`/`BLOCKED:<reason>`/`BUILD_BROKEN`/`UNKNOWN`/`UNSUPPORTED`) this PRD
  uses throughout, including in its own executive summary above.
- **Model-conformance precedent, and why FR6 is a ggen pack, not more hand-written Python**
  (added 2026-08-12, second correction pass). `azuregoat_privesc.py`'s
  `parse_manual_steps()` + `tests/domains/test_azuregoat_privesc.py`'s
  `test_attack_steps_match_real_manual_commands_parsed_at_runtime` is real, working precedent
  for checking a hand-modeled domain against its real upstream source (asserts the vendored
  manual's step count and a per-step command substring match) — `terragoat_remediation.py`'s
  `parse_findings` does a weaker, capped version of the same thing. **But this precedent is
  hand-written Python, per-domain, uncoordinated, and only 2 of 4 domains have it at all**
  (CloudGoat and K8s-Goat have zero fidelity-checking — their tests self-consistency-check a
  hand-authored constant against itself, never read the real vendored walkthrough file).
  Extending this pattern by hand to the other domains (~200 LOC across 4 files) would work,
  but it is exactly what `~/ggen`'s **`l5-pack-method`** skill (`.claude/skills/l5-pack-
  method`, real, present only in `~/ggen`, confirmed absent from `~/autofde-lab`/`~/gymact`)
  exists to replace: *vendor a real reference read-only, transcribe verbatim into ontology
  sourceText, prove fidelity, gate every structural invariant as a SPARQL query, prove
  idempotency, score honestly* — the exact shape of problem this PRD now has four instances
  of. Per this session's own `feedback_ggen_first_generate_dont_handwrite` discipline: model
  in RDF and let ggen generate/gate, hand-written code is the exception that must earn its
  place. FR6 below replaces "write four more Python parsers" with "build one ggen pack that
  does all four, generated and gated, not hand-maintained."

## PRD — what this system must do

### Goal

Produce, for any of the four `*goat` security domains plus the existing Kubernetes/Terraform
gyms, a **receipted trial** whose OCEL v2 log independently proves a specific claimed
competency (e.g. "diagnosed and remediated an AWS IAM privilege-escalation path in
CloudGoat"), replayable by anyone holding the log file, without requiring trust in the system
that produced it.

### Non-goals (explicit, per this session's own correction-discipline)

- This PRD does **not** claim to produce an accredited AWS/Azure/GCP certification. It
  produces independently-verifiable competency evidence that argues the same underlying
  skill, nothing more.
- This PRD does **not** attempt real-cloud-account actuation. Every trial target is local
  (Docker/`kind`/`k3d`) or a vendored, deliberately-vulnerable benchmark repo (`*goat`) — the
  same boundary `gymact`'s real providers already respect.
- This PRD does **not** grant itself `enterpriseStanding` or an "adoption decision" — see
  Non-functional requirements below.
- This PRD does **not** attempt the full theoretical combinatorial space (every fault type ×
  every seed × every domain) in one pass — see Rollout below for the bounded, real first
  slice.

### Functional requirements

1. **FR1 — Fix the template, then one real OCEL episode per currently-unlogged `*goat`
   domain.** FR1a: fix AzureGoat's `gymact_bridge.py::verify()` to independently poll real
   state instead of self-reporting (Correction 4) — this is the template every other domain
   copies, so it must be correct first. FR1b: CloudGoat and kube-goat each need a new
   `gymact_bridge.py` built from scratch (their domain code today is planning-only and
   explicitly disclaims actuation) plus `scripts/run_{cloudgoat,k8sgoat}_gymact_ocel_episode.py`
   modeled on the corrected AzureGoat template. FR1c: GCPGoat needs a domain module built
   before any bridge or episode script is possible (Correction 3) — treat this as its own,
   larger sub-item, not parallel-equal to the other two. Every episode: a real
   `materialize → act → verify → teardown` trial with hash-chained `pre_state_digest`/
   `post_state_digest` attributes, written to `reports/ocel/<domain>-gymact/episode.ocel.json`.
2. **FR2 — Certification ladder, three tiers, each with a named, checkable admission rule.**
   Per Corrections 6–7, Professional tier's prerequisite (a per-domain scenario-variant
   registry) does not exist for any domain and is the single largest item in this PRD —
   recommend splitting FR2 into its own follow-up PRD once one domain's registry has been
   built once, so LOC-per-additional-scenario is measured, not estimated (see Rollout).
   - *Associate*: one clean `standing: ALIVE` receipted trial per domain (depends on FR1).
   - *Professional*: a stride-sampled representative set of scenario variants within the
     domain, sampled with the same *discipline* as `STATUS.md` Pass 20 (sort, fixed stride,
     computed once, never hand-picked) — implemented as new code (Correction 6), run against a
     scenario registry that must first be built per domain (Correction 7), with a published
     pass rate, not a single best run.
   - *Expert*: a cross-domain composed episode — e.g. an AWS IAM misconfiguration diagnosed
     and an equivalent Azure remediation proposed, chained in one receipted trial — proving
     the transferable reasoning, not per-cloud memorization.
3. **FR3 — A ledger, not a badge.** Every trial's receipt is appended to a chained ledger
   (extend the existing `docs/ocel/` convention) — a failed or blocked trial is logged with
   the same rigor as a pass, naming the exact blocker (`BLOCKED:<reason>`), never silently
   dropped.
4. **FR4 — A replay-verify command (new capability, distinctly named — Correction 5).** Not
   `gymact replay` (existing, means ledger/chain-hash integrity only). For domains whose
   verifier polls purely-captured subprocess output already stored at actuation time
   (Terraform is the only clean case), a true log-only pass/fail re-derivation is achievable —
   build this first as the proof of concept. For domains whose verifier polls *live* external
   state (Kubernetes, all three `*goat` bridges), full log-only replay is not achievable
   without recording the raw poll payload at actuation time; at best this yields a weaker
   "snapshot-consistency" replay (the stored evidence was internally consistent with the
   verdict, not that the verdict is still true of the world today) — must be labeled as such,
   not conflated with the Terraform case's stronger guarantee.
6. **FR6 — Model-conformance validation, as a ggen pack, not hand-written per-domain checks.**
   Every `*goat` domain's modeled action/state space (`ATTACK_STEPS`, `DEFAULT_STEPS`,
   `parse_findings` output, etc.) must be validated as correct and complete against its real
   upstream source (the vendored `*goat` manual/scenario/walkthrough doc) before any episode
   built on it is trusted — not just that a trial runs and produces a receipt, but that the
   *model itself* is proven faithful. This is the requirement `l5-pack-method` exists for.
   Concretely, one new pack, e.g. `packs/goat-capabilities-pack`, built per the skill's 7 steps:
   - **Reference**: the four real vendored manuals/scenarios already on disk —
     `vendor/gyms/azuregoat/attack-manuals/module-1/05-Privilege Escalation.md`,
     `vendor/gyms/cloudgoat/scenarios/iam_privesc_by_attachment/` (walkthrough doc, path to
     confirm), `vendor/gyms/kubernetes-goat/guide/docs/scenarios/scenario-16/scenario-16.md`,
     `vendor/gyms/terragoat/terraform/aws/s3.tf` (comment-annotated findings). GCPGoat has no
     domain yet (Correction 3) — its manual becomes the reference once FR1c exists.
   - **Vendor read-only**: these files are already vendored via git submodules; the pack
     references them, never copies/edits them.
   - **Transcribe verbatim**: each numbered step/finding, whole-file first, into
     `ontology.ttl` `sourceText` literals — reusing the `pack-transcriber` agent pattern
     already established in `~/ggen` for exactly this "real file → verbatim RDF literal" step.
   - **Prove fidelity**: AzureGoat's own test
     (`test_attack_steps_match_real_manual_commands_parsed_at_runtime`) is the reference-
     oracle-shaped assertion already proven to work — the pack's generated equivalent must
     reproduce the same check (step count + per-step command substring), generated from the
     ontology's admitted facts instead of hand-maintained per-domain.
   - **Gate everything**: `gates/010_step_count_matches_manual.rq` (SELECT returning any
     domain whose modeled step count != its manual's admitted step count — a violation, not a
     warning), one gate per domain, each with a `# MESSAGE:` header naming the exact mismatch.
   - **Prove idempotency**: `ggen sync run` twice, whole-tree diff — only the receipt chain
     differs.
   - **Score honestly**: a `docs/packs/PACK_MATURITY_MODEL.md`-style entry (or this repo's
     equivalent) stating plainly that command-fidelity is checked but precondition/effect
     *topology* fidelity against manual prose is not — the real residual gap even AzureGoat's
     current hand-written check doesn't close (per the grounding bullet above), named rather
     than silently claimed solved.
7. **FR5 — SQLite-first log format** for anything at Professional tier or above. Per
   Correction 2, this requires reconciling `gymact.ocel` (JSON-only, used by every `*goat`
   episode script today) with `autofde_lab.ocel.log`/`sqlite_store.py` (the actual SQLite
   producer) — either a new `receipts_to_sqlite()` in `gymact.ocel`, or routing gymact
   receipts through `autofde_lab.ocel.log` first. Associate-tier JSON receipts may stay JSON.

### Non-functional requirements (authority boundary)

Per `fde-authority-boundary.md`'s seven-kind table, mapped explicitly so this system cannot
drift into self-certification:

| This system produces | Kind | Never becomes |
|---|---|---|
| A receipted trial pass/fail | verifier verdict (independent of the producer) | the producer's own claim |
| A certification-ladder tier | technical consequence | value delivered / an accredited cert |
| A stakeholder's decision to rely on it | (not produced by this system) | self-granted by this system |

Concretely: the verifier step in every trial must be a separate code path from the actor that
proposed/attempted the remediation — reusing the existing gymact `verify()` convention
(polls real state, does not trust the actor's self-report), never collapsing proposer and
verifier into one call.

## ARD — how it is built

### Components (all reuse existing real infrastructure — no new subsystem)

- **Planner** (`autofde-lab`): proposes which domain/scenario/seed to attempt next. Existing
  `autofde_lab.hub.domain.*` wrappers are the domain layer; no new planner code needed for
  FR1 beyond what `azuregoat_privesc.py` already demonstrates.
- **Broker/actuator** (`gymact`): admits the proposed trial, actuates it through the real
  `kubernetes_reconciliation.py`/`terraform_plan.py`/domain-specific gym provider, and is the
  sole place any real subprocess/Docker/K8s call happens — matching the existing
  planner-proposes / broker-admits separation this repo already enforces elsewhere
  (`FORWARD_DEPLOYMENT.md`).
- **Verifier**: a distinct function per domain that polls real post-trial state (cluster RBAC
  bindings, IAM policy diff, Terraform state) — never re-derives its verdict from the actor's
  own narration. `kubernetes_reconciliation.py`'s existing `verify()` (real cluster pod-phase
  poll) is the template.
- **Receipt/ledger**: per Correction 1, no `ocel_standing.py` exists — this is net-new code
  (`ocel/ledger.py`, per the implementation plan in `docs/jira/v26.8.12/`), not an extension
  of a standing-derivation mechanism that turned out not to exist. The nearest real precedent
  to model it on is `scripts/ocel_procint_report.py`'s aggregation-across-logs pattern, plus
  `src/autofde_lab/standing.py`'s vocabulary — neither is the ledger itself.

### Data model addition

One new OCEL object type, `certification_claim`, related to an `episode` object via a
`certifies` qualifier, carrying attributes `domain`, `tier` (`associate`/`professional`/
`expert`), and `standing`. No change to the existing `event`/`object` OCEL 2.0 schema — this
is additive, following the same pattern `docs/ocel/sregym/*.ocel2.sqlite`'s `attributes` table
already supports.

### Rollout (dependency-ordered, corrected 2026-08-12)

The original 4-step rollout assumed FR1 was a mechanical 3-script port from a working
template. It is not (Corrections 3–4). Revised sequencing, dependency-ordered rather than
FR-numbered — full file/LOC breakdown per step lives in the companion document
`docs/jira/v26.8.12/cloud-cert-wbpr-implementation-inventory.md`:

1. **FR6 first, ahead of FR1's remaining sub-items** — build the `goat-capabilities-pack`
   against the two domains with existing hand-written fidelity checks (AzureGoat, TerraGoat)
   as the proof of concept, since their reference-oracle-shaped assertions already exist to
   generate from. This validates the ggen-pack approach before it's relied on for CloudGoat/
   kube-goat/GCPGoat, which have no fidelity check of any kind yet to fall back on.
2. Fix AzureGoat's `verify()` self-report bug (FR1a) — smallest real fix, and every other
   domain's bridge is modeled on it.
3. Build CloudGoat's and kube-goat's `gymact_bridge.py` (FR1b) — real domain-planning code
   exists to bridge to; GCPGoat (FR1c) is naturally last since its domain module doesn't
   exist yet. Once GCPGoat's domain module exists, extend FR6's pack to cover it too, rather
   than hand-writing a fifth Python fidelity check.
4. Only then attempt FR3 (ledger) and FR5 (SQLite reconciliation), which need FR1's real
   episodes to have something to chain.
5. FR4 (replay-verify) can proceed in parallel with 2–4 once naming is fixed (Correction 5) —
   start with Terraform's verifier (the only cleanly log-derivable one) as the proof of
   concept before attempting the weaker snapshot-consistency mode for live-state domains.
6. FR2 (ladder + stride sampling) is the largest, least-scoped item (Corrections 6–7) —
   recommend splitting it into its own follow-up PRD once a single domain's scenario registry
   has been built once, so real LOC-per-scenario is measured rather than estimated. **FR6's
   gates become the admission check for any new scenario variant FR2 adds** — a variant with
   no verbatim-transcribed manual backing it should be refused by the pack's own gates, not
   silently accepted.
7. Explicitly deferred, not attempted in this rollout: GCP/Terraform Expert-tier composition,
   full fault-type coverage on `sregym`, precondition/effect-topology fidelity (FR6's own
   named residual gap, not just command-string fidelity), and any claim beyond
   `PARTIAL_ALIVE` for the ladder as a whole until step 5 above (an Expert-tier cross-domain
   trial) is real.

## Session-close standing (2026-08-12, no-live-infra scope)

Per user scoping decision ("everything that doesn't need live infra"). Every tag below is
backed by a real command run this same session — see each item's own test file/output, not
narrated:

- **FR1a** (fix AzureGoat `verify()` self-report) — `ALIVE`. `gymact_bridge.py::verify()` now
  independently replays `_action_log` via the domain's real transition function and fails
  closed on divergence from live state. 5/5 real tests pass
  (`tests/domains/python/test_azuregoat_verify_independence_chicago.py` + the pre-existing
  `test_azuregoat_privesc.py`), including a real tamper-and-detect proof.
- **FR2** (`certification/stride_sampler.py` + `ladder.py`) — `ALIVE` for the sampler/ladder
  logic itself; `BLOCKED:NO_SCENARIO_REGISTRIES` for Professional-tier real usage (Correction 7
  — no domain has a scenario-variant registry yet, unchanged this session, deliberately
  deferred per Rollout item 6). 11/11 real tests pass.
- **FR3** (`ocel/ledger.py`) — `ALIVE`. Real chained ledger over real `OcelLog`, `BLOCKED:`
  trials chained with identical rigor to `ALIVE` ones, tamper-detection proven. 5/5 real tests
  pass; full `tests/ocel/` suite (23 tests) still green.
- **FR4** (Terraform-only replay-verify) — `ALIVE` for Terraform; `UNSUPPORTED` for Kubernetes/
  `*goat` snapshot-consistency replay (not attempted, needs live state to have ever produced a
  real snapshot). `gymact/verify_replay.py`, shared by the live `verify()` and the new replay
  path so they cannot silently drift. 5/5 new tests pass, including a real end-to-end proof
  that a live episode's verdict is reproduced from its captured state with zero subprocess
  calls; 16/16 across the full terraform_plan + verify_replay suite.
- **FR5** (SQLite reconciliation) — `ALIVE`. `ocel/gymact_adapter.py` routes real
  `gymact.ocel` JSON through the existing `OcelLog`/`sqlite_store.py`, proven via a real
  receipts → JSON → SQLite → re-read round trip against real `gymact.models.Receipt` objects,
  with the same table schema the real sregym logs use. 3/3 new tests pass.
- **FR6** (`packs/goat-capabilities-pack`) — `ALIVE` for the AzureGoat/TerraGoat proof of
  concept; `BLOCKED:GCPGOAT_DOMAIN_ABSENT` for extending it further (Correction 3, unchanged).
  Real `ggen sync run` executed three times this session against `examples/goat-capabilities-
  verify`: once to generate, once to prove byte-identical idempotency (SHA-256 hashes
  compared, matched), once with a deliberately corrupted `declaredStepIndividualCount` to
  prove the gate genuinely refuses (`FM-PACK-013`, real error, real remediation message) before
  being restored and re-verified clean. The generated fidelity-proof test (4/4 passing) cross-
  checks the ontology's transcribed content against the real, live `ATTACK_STEPS`/
  `parse_findings` — not a hand-maintained duplicate. Named residual gap, unclosed: precondition/
  effect-topology fidelity against manual prose (same gap the PRD's FR6 section names).
- **FR1b/c, FR2's registries, FR4's live-state replay** — `UNSUPPORTED` in this environment
  (no responsive Docker daemon at session start) — explicitly deferred per the approved plan,
  not attempted, not claimed.

Full cross-repo real-test tally this session: autofde-lab 118 tests (certification + ocel +
azuregoat, all passing), gymact 16 tests (terraform_plan + verify_replay, all passing), plus
the 4 ggen-pack fidelity tests and one proven gate refusal — zero failures, zero skips beyond
the pre-existing, previously-documented submodule-not-initialized skip.

## Verification

- Each new script (FR1) must produce a real `reports/ocel/<domain>-gymact/episode.ocel.json`
  with `standing: ALIVE` on at least one full trial before being cited anywhere as evidence —
  re-run it live, don't reuse a prior session's paraphrase.
- The ledger's pass-rate numbers (FR2 Professional tier) must come from the domain's own real
  scenario registry, sampled the same way `STATUS.md` Pass 20 samples sregym — never hand-
  picked.
- Before this system's output is cited in any external-facing artifact (e.g. the Sony
  interview page), re-verify the specific log being cited still replays cleanly via FR4's
  replay command — a stale or since-drifted log is not evidence.
