# CHANGELOG

> **Note on scope**: autofde-lab is a docs/research lab, not a versioned package.
> There is no package version to bump; "versions" below are git tags marking
> docs-only cuts of the working tree. Entries are grouped candidate entries
> derived from the git history, not per-commit release notes.

## v26.10.8 (2026-10-08) — docs-only cut

Tag `v26.10.8` at `45e0a6bc`; range `v26.9.17` (`334b3eb6`, 2026-09-17) → HEAD,
565 commits (477 non-merge).

### Docs / test / tooling waves

- 477 non-merge commits across `docs/` (495 files changed), `src/` (473),
  `tests/` (355), plus `receipts/`, `reports/`, `scripts/`, `.github/`,
  `ontology/`. Commit-type mix is led by `feat(iec)` (75), `docs(gall)` (27),
  `feat(gall)` (25), `feat(fortune5)` (21), `test(gall)` (19), `ci(gall)` (14).
- IEC line: region-granular non-LLM benchmark (`4fae1e68`, PR #184), LLM
  residue census and census v2 with import-resolved frontier + CI residue gate
  (`f718d65c`, `85c36746`, `69d2690c`), IEC sibling fetch fix (`ad0ff179`).
- ALOOP-001 autonomous closed-loop court over OCEL 2.0 (`3cb94f60`) with a
  repair series r1–r9 (`5a8641b6` … `656e81ee`, `ccec4dd3`) closing
  vacuous-loop, stale-consequence, human side-channel and freshness-cone
  attacks, plus provider-extinction semantic conservation (`5e83f6f8`).
- Osiris bounded companion control kernel and court (`7208c041`, `aa1f24ee`),
  speech/action policy gate independence fixes (`daabd369`, `ac8bec18`).
- Doctrine boundary lab over `fortune5_safe` (Lane 6, `91678ab5`, repairs
  `d6becb59`) with a seal/authority hardening series (catalog allow-list
  `cb4529e9`, strategy-signature binding `28f8a7a7`, verify_run enforcement
  `3d40316d`, mutant kills M9/M10 `c9398f35`, typed seal-key refusals
  `79dfa24e`).
- Test/tooling: AIRo risk-description ontology with rdflib description and pin
  courts (`31e3decf`), lane-lease build-root ignore for campaign fan-out
  (`6d70e17a`), GymAct benchmark contract doc (`96791a95`).

### Concurrency-stress benchmark refreshes

- `a9f4194f` (2026-09-18) and `45e0a6bc` (2026-10-08) each rerun the 5-trial
  shared-journal lost-update stress and refresh
  `docs/jira/v26.9.17/benchmarks/concurrency-stress-findings.md`. Latest run:
  69 actuations, 31 records on disk, 38 lost updates (previously 29/40);
  lost-update race conclusion unchanged — confirmed in 5/5 trials.

### AAIF / graphlaw-court work

- AAIF integration (`2a3d064e`): AAIF vanilla runtime
  (`src/autofde_lab/aaif/`), FastMCP server config (`mcp/mcp_servers.json`),
  A2A handler, agentgateway config + `k8s/agent-router.yaml`, and an AAIF
  runtime court (`tests/aaif/test_aaif_runtime_court.py`).
- Graphlaw as an independent plan-admission court (`55266bde`):
  `src/autofde_lab/fabric/graphlaw_court.py` hosts the graphlaw WASI module
  (wasmtime), replays candidate plans over RDF state, and returns typed
  `PlanRefused` at the first unmet precondition; `guarded_candidate` accepts
  an optional `court` (default behavior unchanged). Follow-up `12ab0552` reads
  graphlaw's structured refusal details instead of scraping the message.
