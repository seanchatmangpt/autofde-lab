# Implementation inventory — cloud-cert-wbpr-prd.md

Companion to `cloud-cert-wbpr-prd.md`. Produced by 5 parallel lumen-first Explore agents
(2026-08-12), one per FR/ARD section, auditing the PRD against real code. Every row below
traces to a direct file read logged in that session — see the PRD's own "Corrections
(2026-08-12, 5-agent grounding audit)" section for the narrative version of the same findings.

## File + LOC inventory, by FR

| FR | Deliverable | New/modified files | Est. LOC | Real blocker |
|---|---|---|---|---|
| FR1a | Fix AzureGoat's `verify()` | `hub/domain/azuregoat_privesc/gymact_bridge.py` (modify) | ~30–50 | Needs a real external Azure-shaped check to replace the in-process self-report; no such check exists in the file today |
| FR1b | CloudGoat + kube-goat bridges | `hub/domain/{cloudgoat_iam_privesc,k8s_goat_rbac_escalation}/gymact_bridge.py` (new, ×2, ~200–210 each), `scripts/run_{cloudgoat,k8sgoat}_gymact_ocel_episode.py` (new, ×2, ~80–105 each) | ~560–630 | Both domains' current code explicitly disclaims actuation in its own docstring |
| FR1c | GCPGoat domain + bridge | new domain module (~250–320), `gymact_bridge.py` (~200–210), `scripts/run_gcpgoat_gymact_ocel_episode.py` (~80–105) | ~530–635 | No domain module exists at all; no single numbered privesc manual to parse (unlike AzureGoat) — attack-path content lives only in defender-facing docs upstream |
| FR2 | Certification ladder + stride sampling | `certification/stride_sampler.py` (~60–90), `certification/ladder.py` (~100–150), 4× per-domain scenario registries (~150–300 each = 600–1,200), tests (~150–250) | ~910–1,690 | Zero scenario-variant registries exist in any domain — the largest real gap in the whole PRD |
| FR3 | Chained ledger, `BLOCKED:` rigor | `ocel/ledger.py` (~200–280), `ocel/model.py` additions (~20–40), 4× episode-script call sites (~60–120 total), tests (~150–250) | ~430–690 | Depends on FR1+FR2 existing first; no chain-hash primitive exists yet to build on; `ocel_standing.py` (cited as the extension point) doesn't exist |
| FR4 | Log-only replay-verify | `gymact/replay.py` additions (~40–70), new CLI subcommand (~25–40), per-domain `verify_from_log`/snapshot fns — Terraform (~15–25), K8s (~30–50), 3× goat bridges (~30–60 each = 90–180), docs (~80–150), tests (~150–300 across ~5 files) | ~430–815 | Only Terraform's verifier is cleanly log-derivable; live-state verifiers (K8s, all 3 goats) can at best get a weaker snapshot-consistency mode |
| FR5 | SQLite-first ≥ Professional | `gymact/ocel_sqlite.py` or adapter through `autofde_lab.ocel.log` (~120–180), tier-gating hook (~30–60, blocked on FR2), tests (~80–150) | ~230–390 | Two independent OCEL producers (`gymact.ocel` vs `autofde_lab.ocel.log`) must be reconciled first |
| FR6 | Model-conformance validation, as a ggen pack (added 2026-08-12, second correction pass — supersedes hand-writing 4 more Python fidelity checks) | `packs/goat-capabilities-pack/pack.toml` (~20), `ontology.ttl` with verbatim-transcribed manual/scenario/finding literals per domain (~150–400, dominated by transcription volume not code), `gates/010_step_count_matches_manual.rq` + 3 sibling gates (~15–25 each = 60–100), generated fidelity-proof test(s) modeled on AzureGoat's existing `test_attack_steps_match_real_manual_commands_parsed_at_runtime` (~60–100 generated, template ~80–120), idempotency proof script/CI step (~20–40), `docs/packs/PACK_MATURITY_MODEL.md`-equivalent scoring entry (~40–80 prose) | ~430–860 | AzureGoat/TerraGoat have a reference-oracle-shaped hand-written check to generate from (low risk); CloudGoat/kube-goat/GCPGoat have none, so the pack must define the fidelity-check shape for those from scratch, then generate it — and even the best-covered domain (AzureGoat) only checks command-string fidelity, not precondition/effect topology, a residual gap FR6 must name, not silently close |
| ARD | `certification_claim` OCEL object type | Inline in FR3's ledger writer (~40–60) | ~40–60 | **No blocker** — vendored OCEL 2.0 JSON Schema (`gymact/schemas/ocel20-schema.json`) is permissive of new type names; no SHACL gate governs OCEL object types anywhere in either repo |

**Total realistic estimate: ~3,560–5,770 new/modified LOC across ~30–36 files**, including
FR6 (added 2026-08-12). The single largest cost is still FR2's per-domain scenario-registry
construction — domain-modeling work, not software-architecture work — with FR6's ontology
transcription volume as the second-largest, non-code-complexity cost (verbatim manual text,
not logic).

## Verification

- Every file path and LOC estimate above must be re-confirmed against the actual repo state
  at implementation time, not assumed to still hold after time passes.
- Before any implementation PR cites this inventory, re-open `cloud-cert-wbpr-prd.md`'s
  Corrections section and confirm no further drift has occurred since 2026-08-12.
