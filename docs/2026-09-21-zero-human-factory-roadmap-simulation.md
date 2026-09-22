# Zero-Human Software Factory — working-backwards roadmap and simulation

Companion to `2026-09-21-zero-human-factory-standing.md` (the real-state ledger for
today). That doc answers "what exists." This doc answers "how do we get from what
exists to the press release's claimed end state" — an EXPLORE-mode artifact
(`.claude/rules/explore-exploit-premises.md`): reasoning forward inside the
working-backwards premise, not re-auditing it.

## Starting state (真, from the standing doc — not re-derived here)

| Node | Status |
|---|---|
| autofde-lab sa2a beam bridge (validate/admit/plan/execute/replay) | ALIVE, in-repo only |
| ggen-marketplace `sa2a-bridge-pack` → xaas `Xaas.Sa2a.Generated.McpDescriptor` | ALIVE, description only, no proven caller |
| ggen_igniter `SemanticJira`/`Reconciler`/`TransitionLog` | real code, UNSUPPORTED (no consumer) |
| ggen_igniter `zcode-ocel-pack` | real code, UNSUPPORTED (no consumer) |
| ash_kudzu | real, small (197 files), Ash-resource-scoped ontology compiler |
| ash_atlassian, UltraCode-as-repo, zcode-cli, Semantic-Jira-as-product | do not exist |
| autofde-lab ecosystem chain S1-S7 | mostly `PARTIAL_ALIVE`/`UNSUPPORTED`, no POWL plan executes end to end |
| actuation authority | never in autofde-lab; belongs to `autofde`/`gymact`/`ggen` per its own boundary docs |

## 1. HDDL roadmap — `SOLVE(atlassian-migration)`

```
task SOLVE(atlassian-migration)
  method factory-composition
    ordered:
      DISCOVER(atlassian-contracts)
      RECONSTRUCT(canonical-ontology)
      ADMIT(shacl-court)
      ROUTE(sa2a-capabilities)
      PLAN(work-graph)
      MANUFACTURE(implementation)
      EXECUTE(work-orders)
      VERIFY(consequences)
      RECEIPT(close-loop)
```

### DISCOVER(atlassian-contracts)
- precond: none (cold start)
- effect: OpenAPI/GraphQL SDL/JSON-Schema/webhook schemas admitted as source facts
- owner: `ash_kudzu` (real, 197 files — this is its stated job: "introspects Ash.Resource/
  Domain reflection API"; extending it to ingest *external* OpenAPI/GraphQL rather than
  only reflect on existing Ash resources is the actual gap, not a rewrite)
- bounded closing work: add an `ash_kudzu` EXTRACT stage that ingests a raw OpenAPI/
  GraphQL SDL file (not just Ash reflection) — smallest real increment, same shape as
  its existing pipeline.

### RECONSTRUCT(canonical-ontology)
- precond: DISCOVER done
- effect: local Atlassian concepts aligned to public prior art (PROV-O, W3C ORG, SKOS,
  Schema.org, OSLC CM, OWL-Time, SHACL) per this ecosystem's reuse-before-invent law
- owner: `ash_kudzu` ALIGN stage (per its documented pipeline: EXTRACT→RECONSTRUCT→
  ALIGN→ADMIT→GENERATE→VERIFY→PROJECT)
- status today: pipeline shape exists in principle (ggen_igniter's ontology→SPARQL→EEx
  machinery is real and in daily use for other domains this session — Semantic Jira,
  sa2a-bridge-pack); no Atlassian-specific ontology file exists yet

### ADMIT(shacl-court)
- precond: RECONSTRUCT produces a candidate ontology
- effect: SHACL shapes gate the ontology before any code generation — same admission
  pattern this session's own `sa2a-bridge-pack` gates already use
  (`gates/070_consequential_requires_authority.rq`,
  `gates/080_exposed_via_closed_vocab.rq`)
- owner: ggen_igniter's existing SHACL-admission machinery (already real —
  `lib/ggen_igniter/reactors/reconcile_reactor.ex` has an `admit_semantic_jira_shacl`
  step for a different domain; the mechanism generalizes, it doesn't need inventing)

### ROUTE(sa2a-capabilities)
- precond: ADMIT passed
- effect: capability descriptors exist for whatever the ontology says is
  discoverable/exposable
- owner: the REAL mechanism already exists — `ggen-marketplace`'s `sa2a-bridge-pack`
  composition pattern (this session verified it: `ontology.ttl` → `ema:Capability`
  individuals → generated `McpDescriptor`). Closing work: run the SAME composition
  for an `ash-atlassian-capabilities` ontology once RECONSTRUCT produces one — this is
  the one step in the whole roadmap with a proven, working template to copy.

### PLAN(work-graph)
- precond: capabilities routed
- effect: a Semantic-Jira-shaped WorkOrder graph (subject, target_state,
  ontology_dependencies, admission_rules) admitted for the migration
- owner: `ggen_igniter`'s `GgenIgniter.SemanticJira` + `Reconciler` + `TransitionLog`
  (real, tested — 5/5 + 97/97 passing this session per the earlier commit) — but
  UNSUPPORTED as an integration today because nothing outside `ggen_igniter` calls
  it. Closing work: this is the single highest-leverage gap in the whole roadmap —
  give `Reconciler.reconcile/4` a real external caller (a Mix task with a JSON/HTTP
  entrypoint, or an autofde-lab planner emitting WorkOrder events into
  `TransitionLog.append/2`) so PLAN can consume it instead of the migration needing a
  parallel, unconnected planner.

### MANUFACTURE(implementation)
- precond: WorkOrder admitted
- effect: framework-native Ash resources generated from the ontology
- owner: `ggen_igniter.sync` (real, used constantly this session for other domains —
  `mix ggen_igniter.sync --ontology ... --query ... --template ... --out ...`)
- gap: no `ash_atlassian` ontology/query/template set exists yet; the *mechanism* is
  proven, the *content* is not written

### EXECUTE(work-orders)
- precond: implementation manufactured
- effect: a worker (zcode-shaped) claims and performs the transformation
- owner: no real zcode-cli exists. Closing work is real but narrow: `zcode-ocel-pack`
  already defines the OCEL event/object vocabulary a worker protocol would need
  (`OBJECT_TYPES`/`EVENT_TYPES`/`TRANSITIONS`) — it has zero consumers today. The
  actual missing piece is not "build zcode-cli from scratch," it's "write the one
  consumer that imports `src/ocel/registry.ts` and drives a worker loop against it" —
  same gap the standing doc already named as UNSUPPORTED, now framed as the next
  buildable increment instead of a deficiency.
- actuation note: per autofde-lab's own boundary, EXECUTE's actual side effects must
  route through `autofde`/`gymact`, never autofde-lab itself — this roadmap step
  belongs to a different repo's authority, not autofde-lab's.

### VERIFY(consequences)
- precond: execution produced a candidate result
- effect: real test/court run against the actual change
- owner: the verify ladder this ecosystem already uses everywhere (Chicago-style
  tests, SHACL courts, `mix credo`/`mix test` gates) — mechanism proven repeatedly
  this session (sa2a bridge's own 4/4 passing test is a working instance of exactly
  this step)

### RECEIPT(close-loop)
- precond: VERIFY passed
- effect: durable, replayable evidence — exact identities (repo, SHA, digest,
  toolchain), per `.claude/rules/no-dual-bookkeeping.md`'s identity discipline
- owner: `sa2a_replay` (ALIVE today — the bridge's replay op already verifies a
  receipt DAG against a hash, both success and failure paths, per this session's
  test run) is the one piece of RECEIPT that is *already* working end to end, just
  not yet wired to anything but its own test.

### Phase gates (DMEDI)

| Phase | Gate | Current state |
|---|---|---|
| Define | Atlassian migration charter, scope, acceptance criteria | not written — this roadmap is the first Define artifact |
| Measure | Real baseline: existing Jira/Confluence/Bitbucket contract inventory | not started (DISCOVER unimplemented) |
| Explore | Candidate ontology alignments (PROV-O/ORG/SKOS/OSLC-CM/etc.), scored | not started, but the *pattern* is proven on other domains this session |
| Develop | ash_atlassian resources, generated and tested | not started |
| Implement | Piloted migration of one bounded surface (e.g. issue-type schema only), staged rollout | not started |

The honest read: every mechanism this roadmap needs (ontology→SPARQL→EEx generation,
SHACL admission, capability-pack composition, WorkOrder reconciliation, replayable
receipts) already exists and is independently proven *somewhere* in this ecosystem
this session. Nothing in the roadmap requires inventing new machinery — the real work
is wiring proven mechanisms to a new domain (Atlassian) and to each other (SemanticJira
→ a caller; zcode-ocel-pack → a consumer), which is a materially smaller lift than the
press release implies but also not zero, contrary to the standing doc's read of "mostly
absent."

## 2. Simulated execution trace

One concrete work order: **"migrate the Jira `issuetype` schema field to
`ash_atlassian`."** Each hop is marked `[REAL]` (mechanism exists, proven this
session) or `[SIMULATED]` (narrated as the press release describes it; not built).

```
1. [SIMULATED] Intake
   WorkOrder{ subject: "issuetype-schema-migration",
              target_state: "Ash.Resource IssueType backed by canonical ontology",
              source_contract: "jira-cloud-rest-v3 openapi.yaml#/components/schemas/IssueType" }
   → admitted into a Semantic-Jira-shaped graph.

2. [REAL mechanism, SIMULATED content] PLAN
   GgenIgniter.SemanticJira.admit_work_order/1 accepts the WorkOrder.
   GgenIgniter.SemanticJira.Reconciler.reconcile/4 verifies definition_digest,
   delegates to promote/3 (pure admission gate — dependency evidence from the
   TransitionLog projection, never from the WorkOrder itself).
   → TransitionLog.append/2 persists an immutable "admitted" event.
   [SIMULATED part: nothing outside ggen_igniter calls this today — in this trace,
    an autofde-lab planner does.]

3. [SIMULATED] ROUTE via SA2A
   autofde-lab's beam_port_bridge.py receives {"op": "sa2a_admit", ...} for this
   WorkOrder — this exact op is REAL and tested (b70331aa), but has never been fed
   an Atlassian-shaped WorkOrder; here it is.
   sa2a_plan produces a plan_hash and candidate allocations (REAL mechanism,
   SIMULATED input domain).

4. [SIMULATED] Reuse check
   ggen-marketplace queried for an existing "issue-type" or "work-item" pack.
   [REAL, this session] `elixir-mcp-a2a-pack` and `sa2a-bridge-pack`'s composition
   pattern (reuse ema:Capability vocabulary verbatim) is the template this step
   would follow if a matching pack existed — none does yet for Atlassian issue
   types, so this step would fall through to RECONSTRUCT.

5. [SIMULATED] RECONSTRUCT + ALIGN
   ash_kudzu ingests the OpenAPI schema fragment, proposes issuetype → skos:Concept
   (a taxonomy of issue kinds) + oslc_cm:ChangeRequest for the work-item shape.
   No real ash_kudzu run against this input exists yet.

6. [REAL mechanism] ADMIT
   SHACL shapes gate the proposed ontology — same gate class as
   `gates/070_consequential_requires_authority.rq` in `sa2a-bridge-pack`.

7. [REAL mechanism, SIMULATED content] MANUFACTURE
   mix ggen_igniter.sync --ontology issuetype.ttl \
     --query name=issuetype_resource.rq --template ash_resource.eex \
     --out lib/xaas/generated/ash_atlassian/issue_type.ex
   This exact command shape is real and used this session (sa2a mcp_descriptor,
   Semantic Jira artifacts) — only the Atlassian-specific ontology/query/template
   files don't exist yet.

8. [SIMULATED] EXECUTE
   A zcode-shaped worker claims the WorkOrder, drives the generated resource through
   a migration script. zcode-ocel-pack's OBJECT_TYPES/EVENT_TYPES would record this
   as an OCEL trace if wired up — today nothing consumes that registry, so this hop
   is the roadmap's named gap (EXECUTE(work-orders), above).
   Actuation, if any occurs, is NOT autofde-lab's — routes to `autofde`/`gymact` per
   the confirmed boundary.

9. [REAL] VERIFY + RECEIPT
   sa2a_execute and sa2a_replay (ALIVE, tested this session) are the real closing
   mechanism: execute returns a result + llm_avoidance_ratio, replay verifies the
   receipt DAG by hash (both correct- and wrong-hash paths tested). This is the one
   full hop in the trace that would work unmodified today if fed real input.
```

### What the simulation shows

Six of nine hops are `[SIMULATED]` content over a `[REAL]` or partially-real
mechanism; zero hops require a genuinely new architecture. The two REAL, fully
working end-to-end mechanisms already proven this session (`sa2a_execute`/
`sa2a_replay`, and the `sa2a-bridge-pack`→xaas composition pattern) are the two
load-bearing pieces the rest of the roadmap would reuse rather than reinvent — which
is the actual working-backwards insight: the press release's claimed factory is not
science fiction relative to this ecosystem's real mechanisms, but it is also not
built — the gap is domain content (an Atlassian ontology, its queries/templates) and
three wiring steps (SemanticJira → a real caller, zcode-ocel-pack → a real consumer,
sa2a bridge → fed real-world WorkOrders instead of only its own test fixtures), not
new invention.
