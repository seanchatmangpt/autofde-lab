# Zero-Human Software Factory whitepaper — grounded standing, 2026-09-21

A whitepaper draft ("The Zero-Human Software Factory") named seven cooperating
systems — SA2A, Semantic Jira, zcode-cli, XaaS, UltraCode, AutoFDE Lab, ggen_igniter,
ggen-marketplace — as jointly completing an autonomous Atlassian→`ash_atlassian`
migration. This document is the real, per-claim standing check against `~/` and this
repo's own ledger, run this session, not a description of the whitepaper.

Vocabulary: `ALIVE` / `PARTIAL_ALIVE` / `BLOCKED:<reason>` / `UNSUPPORTED` / `UNKNOWN`,
per `.claude/rules/standing-law.md`.

## System inventory — real vs. named

| Whitepaper name | Real status |
|---|---|
| SA2A | No standalone repo. A beam port-bridge feature inside `autofde-lab` (`src/autofde_lab/beam/beam_port_bridge.py`, commit `b70331aa`) and a pack (`sa2a-bridge-pack`) inside `ggen-marketplace`, rendered into `xaas`. |
| Semantic Jira | No standalone repo. `GgenIgniter.SemanticJira`/`Reconciler`/`TransitionLog` exist inside `ggen_igniter` as a module, not a product. |
| zcode-cli | No standalone repo. Only a `zcode-ocel-pack` generator target inside `ggen_igniter`; `xaas`'s "zcode" hits are an unrelated same-named subsystem (`zcode_plugin`). |
| XaaS | Real, large (`~/xaas`, 64k files), Elixir/Phoenix on Ash, active. |
| UltraCode | Not a codebase — the Workflow tool's opt-in multi-agent orchestration mode used to produce this document, not a separate repo. |
| AutoFDE Lab | Real, very large (`~/autofde-lab`, 262k files), active. |
| ggen_igniter | Real, large (114k files), active. |
| ggen-marketplace | Real (16k files), active. |
| ash_atlassian | Does not exist. Only an empty `atlassian` stub (1 file, no README, no git). |

## Per-claim standing (verified this session)

| Claim | Standing | Evidence |
|---|---|---|
| autofde-lab's sa2a beam port bridge exposes validate/admit/plan/execute/replay end to end, real test | **ALIVE** | `beam_port_bridge.py:125-138` routes all five ops to real in-process sa2a objects. `tests/beam/test_sa2a_port_ops_chicago.py` spawns a real subprocess, round-trips admit→plan→execute→replay (correct-hash and wrong-hash paths). `grep -rn "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch"` → zero matches. `.venv/bin/python -m pytest tests/beam/ -v` → `4 passed in 5.55s`. |
| ggen_igniter's SemanticJira/Reconciler/TransitionLog connect to autofde-lab or xaas | **UNSUPPORTED** | `grep -rniE "semantic_jira\|sJira"` over both repos → zero real matches (xaas's "semantic" hits are its own unrelated `SemanticCrown` system). Only exposure is local Mix tasks (`ggen_igniter.sync`, `ggen_igniter.doctor`) — no network/CLI-external surface. |
| ggen_igniter's zcode-ocel-pack has a real consumer in xaas or autofde-lab | **UNSUPPORTED** | Zero references to `zcode-ocel-pack`, `ocel/registry`, or its generated constants (`OBJECT_TYPES`/`EVENT_TYPES`/`PRIMARY_OBJECT`/`QUALIFIERS`/`TRANSITIONS`) in either repo. xaas's `zcode` hits are an unrelated `zcode_plugin` subsystem. |
| ggen-marketplace's sa2a-bridge-pack was actually rendered into xaas | **ALIVE** | Commit `2d3c2e9` is on xaas's `main` (`git merge-base --is-ancestor 2d3c2e9 main` confirmed). `lib/xaas/generated/sa2a_mcp_descriptor.ex` is a real generated module: `@capabilities` map for all five sa2a ops with authority/reversibility/receipt-semantics metadata, fail-closed `requires_authority?/1`. Not a stub. |
| autofde-lab's own cross-repo ecosystem-standing ledger, reconfirmed | **ALIVE** (as a ledger — its contents are mixed) | `docs/ecosystem-standing.md` verbatim: S1 `UNSUPPORTED`, S2/S3/S3b `ALIVE` (S3b projection-only), S3c/S4/S5/S6 `PARTIAL_ALIVE`, S7 `UNSUPPORTED`; G1/G2/G2b/G6 `ALIVE` (bounded), G3/G4/G5 `PARTIAL_ALIVE`, G5b `BLOCKED:SAME_POSTCONDITION_CHECKED_EVERY_STEP`, G7 `UNKNOWN`. None of SA2A/XaaS/zcode/ggen_igniter/Semantic Jira appear in this ledger by name — this session's sa2a-bridge finding is new territory not yet folded into it. |

## Where autofde-lab actually sits

autofde-lab today is a real, tested decision-and-planning control plane with one
concretely working new capability — the sa2a beam port bridge, verified end-to-end
against a real subprocess this session — plus a downstream generated capability
descriptor in xaas (`Xaas.Sa2a.Generated.McpDescriptor`) that describes but has not
been shown to invoke it yet. It manufactures plans, hashes, and replayable receipts
entirely in-repo. Every op in the verified bridge terminates inside this repo's own
process or test harness — `sa2a_execute`'s own test returns a synthetic
`"port-bridge-answer"`, not a real-world consequence. No code path found this session
reaches a customer system, external service, or `BRCE.DO`. Per this repo's own
declared boundary (`FORWARD_DEPLOYMENT.md`): "It does not itself receive ambient
authority to actuate customer systems" — confirmed, no exception found.

Two whitepaper-named subsystems (Semantic Jira, zcode-ocel-pack) are real code
sitting inside `ggen_igniter`, but are unconnected generator packs with no
demonstrated consumer anywhere in this ecosystem, not live integrations. `UltraCode`,
`zcode-cli`, and `ash_atlassian` as named in the whitepaper do not exist as
standalone systems at all. The whitepaper's narrative of seven jointly-operating
systems overclaims relative to what is on disk; the real picture is: autofde-lab
plans, one narrow real bridge exists between it and xaas's capability description
layer, and the rest of the named "factory" is either embedded feature work inside
larger repos or does not yet exist.

## Scope note

No gap-closure step was needed this pass: the sa2a bridge — the one claim with a
plausible narrow test gap — came back `ALIVE` with a real passing Chicago-style test
already in place, so no fabricated closure was attempted (per this document's own
governing plan). The `~/ggen_igniter` open-PR-stack / `v26.9.20` tag question from
earlier this session is unrelated and remains parked separately.

---

## Addendum — v26.9.22 wave deltas (2026-09-22, lane L4)

Grounded deltas to the per-claim table above, each verified this wave:

| Claim | Standing | Evidence |
|---|---|---|
| SA2A benchmark suite (RFC-SA2A-002 Appendix E) | **ALIVE** (was: SA2A-B2 BUILD_BROKEN) | `reports/rfc_sa2a_002_benchmarks.json` regenerated: `all_passed: true`, `standing: ALIVE`, all 10 benchmarks B1..B10 pass. Root cause of the standing BUILD_BROKEN was never B2 alone: the v26.9.16 runner crashed at the missing `DatalogEngine.compute_closure` before evaluating the rest; the repair (commit 2a204f27) fixed the call plus five latent harness-vs-source drifts unmasked by it (DatalogAtom varargs, IdentityPolicy/ProvenancePolicy fields, ExplorationBudget lanes, AFDE-2604 require_admission defaults, FinalReceipt evidence identity). |
| Phase H unattended trigger | **ALIVE** (was: BLOCKED:NO_SCHEDULER) | `.github/workflows/phase-h-trigger.yml` (daily cron + dispatch) runs `phase_h_trigger.run_once` against the exact subject; all tick state is redirected outside the tracked tree (`run_once` gained the additive `coverage_state_file` parameter); a local run at release SHA d4faeff9 fired a real solve-and-falsify and left `git status --porcelain src/autofde_lab/fabric` at 0. |
| SA2A receipts bound to an exact subject | **PARTIAL_ALIVE → ALIVE at refresh** | Qualification receipts regenerated at the exact v26.9.22 subject by the same wave (see `reports/` + `receipts/v26.9.22/`). |
| SJ-006 folded into this repo's ledger | **ALIVE** | `docs/ecosystem-standing.md` Pass 5 (commit 455cc7b5, merged to master by this wave) now names SA2A/XaaS/zcode/ggen_igniter/Semantic Jira; the row citing the mixed `~/xaas-worktrees/sjira/sj-006` run was rewritten to cite a run inside this repo at the merged SHA. The claim above ("none of them appear in this ledger by name") is therefore historical as of this wave. |

Not claimed: any new external actuation authority. The unattended tick's
coverage-gap leg stays fail-safe (no ~/xaas on the runner → transient-error
report, no state persisted, no invocation).
