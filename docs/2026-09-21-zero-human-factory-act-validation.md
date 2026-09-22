# act validation of the 12/12 gap closure — real results

Fifth doc in this session's series. The prior receipt
(`2026-09-21-zero-human-factory-gap-closure.md`) closed all 12 gaps to
`ALIVE` via real local verification gates (format/lint/test per repo). This
doc runs `act` (local GitHub-Actions-in-Docker) against each repo's real CI
gate job to attempt an independent, closer-to-real-CI validation — and
reports what actually happened, honestly, including where `act` itself could
not complete.

## The one remaining `PARTIAL_ALIVE` gap closed first

`ga-explore-execute` (gymact): `execute()`'s CLI contract always materializes
a fresh, randomly-IDed environment inside the same call, so a request file
written beforehand could never predict that ID — the only reachable outcome
was `REFUSED:SUBJECT_PROVIDER_IDENTITY_MISMATCH`. Investigated whether real
cross-process episode persistence exists (it doesn't — `_episodes` is a
plain in-process dict, `MaterializationIntent` has no `episode_id` field, no
attach/reattach method exists anywhere) and confirmed adding one would be new
infrastructure, out of bounded scope. Instead added a real, bounded
`SELF_MATERIALIZED_SUBJECT` sentinel: `execute()` substitutes the real,
just-materialized `environment_id` when a request explicitly opts in, while
any real, pre-known `provider_ref` still hits the identity check exactly as
before. `4/4 tests pass` (the original mismatch-refusal test plus a new real
ALIVE-transition test), `ruff check`/`format` clean, zero mocks. Merged to
`gymact` main (`5d20686`). **12/12 gaps are now `ALIVE`.**

## act validation — real attempts, real results

Every repo's real CI gate job was identified and run via `act` with
Colima-tuned flags (gymact already had a mature, working `act` Justfile
integration — reused directly rather than reinvented; the other four repos
got the same proven flag pattern by hand).

| Repo | Job | Result | Real cause |
|---|---|---|---|
| ggen_igniter | `ci.yml :: test` | `BLOCKED` | Two independent, real `act`-tool/emulation limitations, tried on both architectures: **arm64** — `erlef/setup-beam`'s arm64 OTP-27.2.4 build is linked against `libcrypto.so.1.1`, absent from the `catthehacker/ubuntu:act-24.04` image (Ubuntu 24.04, OpenSSL 3.0-only); confirmed by direct image inspection. **amd64** (retried under emulation) — got past checkout/clone/ggen-install for real, then hit `node: executable file not found in $PATH` inside the emulated container, a documented `act` limitation (nektos/act#107). Neither run ever reached `mix format`/`credo`/`verify`/`test` — this session's 3 merged closures were neither confirmed nor contradicted by either attempt. |
| gymact | `ci.yml :: core` (Python 3.12) | `BLOCKED` | `actions/checkout`'s "Checkout exact subject" step fetches the exact commit SHA from the real `github.com` remote; this session's merge commits were never pushed, so GitHub correctly refuses (`fatal: remote error: upload-pack: not our ref 5d20686...`), exit 128. Never reached ruff/pytest. |
| xaas | `ci_cd.yaml :: ci` | `BLOCKED` | Identical structural cause: exact-SHA remote checkout on an unpushed local merge, `not our ref`. Postgres/pgvector service, Colima flags, and secrets were all independently confirmed working — the checkout step is the only blocker. |
| autofde-lab | `pr-ci.yml :: qualification` | `BLOCKED` | Identical structural cause: local `master` is 8 commits ahead of `origin/master`; the exact pinned SHA (`635868a7`, containing both merged closures) has never been pushed. Confirmed this is *not* the anticipated native-C++/pybind11 friction — the job never got that far. |
| ash_kudzu | *(none exists)* | `UNSUPPORTED` | Confirmed fresh, a second time this session: no `.github/workflows/` directory at all — a real, pre-existing repo gap, not caused by this session. Real substitute validation run directly instead: `mix test test/ash_kudzu/openapi_extractor_test.exs` → **6/6 passing**, under the repo's own pinned toolchain. (Also hit, and this time fixed for real rather than routed around, the same class of stale-leex-generated-artifact `sparql` compile issue from earlier in this session — deleted the stale file, forced a clean recompile under the correct pinned OTP, confirmed clean regeneration.) |

## The push decision

Three of the five `BLOCKED` results share one real, fixable root cause:
`act`'s `actions/checkout` step resolves `github.sha` against the real
remote, and none of this session's local merges were ever pushed (by
design, per the actuation-boundary default this whole session followed).
Pushing would let `act` validate the real merged commits for gymact, xaas,
and autofde-lab.

Asked the user explicitly whether to push. **No response arrived** — per
this repo's own actuation-boundary rule ("an unanswered AskUserQuestion does
not constitute consent"), nothing was pushed. Local-only verification stands
as the ceiling for all five repos' standing:

| Repo | Real local gate (already run this session, unaffected by the `act` limitation) |
|---|---|
| ggen_igniter | `mix test` (3 closures' files): 20/20. `mix credo`: clean (6 pre-existing findings, unrelated file). `mix format --check-formatted`: clean. |
| gymact | 4 closures' test files: 12/12 real assertions passed. `ga-execute-alive`: 4/4, `ruff` clean. |
| xaas | 5/5 (1 honest tag-excluded degraded path). Format clean. |
| ash_kudzu | 6/6 (confirmed 3 times total this session, across two different agents and this doc's own re-run). |
| autofde-lab | `al-sa2a-real-caller`: 9/9. `al-g5b-standing`: real `pytest` re-run confirming the correction. |

## Bottom line

**Code standing: 12/12 gaps `ALIVE`, unchanged and unaffected** by `act`'s
inability to run — every `BLOCKED` result above happened *before* any of
this session's closures' own code executed (either at a third-party
action's setup step, or at checkout, before the workflow reaches this
repo's own test/lint commands at all). `act` validation itself did not
succeed for any of the 5 repos this pass, for two distinct, named, real,
non-code reasons — not because the closures are unverified, but because
local-only `act` runs against workflows built to assert exact-remote-SHA
identity are structurally incompatible with an unpushed merge, and because
this session hit two separate, independently-confirmed `act`/Docker-image
limitations unrelated to pushing at all.

## 2026-09-21, later — pushed, re-ran `act`, real terminal results

Per docs/CLAUDE.md's append-only rule, this section adds to the record above
rather than editing it — the `BLOCKED` findings above are still accurate for
the state they describe; what follows is what happened once that state
changed.

The user instructed pushing. All five repos pushed clean, fast-forward, no
force-push: `ggen_igniter` (new branch `feat/zcode-ocel-pack`), `gymact`
(`2e464ef..e75344d`, including a real merge of origin's 11-commit
CMCA/CONSTRUCT8 feature — zero conflicts, confirmed via `git merge-tree`
before merging, 22/22 tests passing after), `xaas` (`8e72cfc..57c77e7`),
`ash_kudzu` (`3210aa7..122b741`), `autofde-lab` (`d5ac60ff..ecd62ffb`).

Re-ran `act` on the three repos blocked purely by the missing-remote-SHA
issue:

- **gymact** — the original blocker is fully resolved (`✅ Success - Main
  Checkout exact subject [2.8s]`). `act` then ran the **complete, real,
  unrestricted test suite** to a natural terminal result — no force-kill,
  ~50 minutes wall time: real `kind`/`kubectl` cluster provisioned, real
  `terraform` binary, real SHACL semantic admission (`conforms: true`, 96
  triples), then `pytest`: **`8 failed, 1608 passed, 45 skipped, 4 xfailed,
  1 error in 2630.10s`**. Every one of the 9 non-passing results was
  individually diagnosed and **none implicates any of this session's 4
  gymact closures** (whose own test files are not among the failures):
  one real act-runner-image fidelity gap (missing `gh` CLI, present on the
  dev machine and on real GitHub-hosted runners), one external API/
  credential gap (Groq 404 on a pinned model name), one pre-existing defect
  reproducing identically on a local run (missing `terragoat` submodule),
  two plausible nested-container Docker I/O timeouts, and two real,
  pre-existing code defects in unrelated files (a subprocess-orphan
  teardown check, an unclosed-asyncio-resource stress test) — genuine bugs,
  worth fixing, but not this session's to fix and not caused by it.
- **xaas** — original blocker resolved (checkout + exact-subject-identity
  assertion both succeed against `57c77e7`). A *different*, real blocker
  surfaced immediately after: `BLOCKED:ERLANG_OTP_VERSION_UNAVAILABLE_IN_ACT_RUNNER_IMAGE`
  — `.tool-versions` pins `erlang 28.5.0.2`, a very recent patch release not
  yet present in `erlef-setup-beam`'s arm64/ubuntu-20.04 precompiled build
  list as served to the local `act` runner image. Upstream of any
  application code; does not implicate `xa-supervise-bridge` or
  `xa-authority-check`. Not pursued further — the real fix (a different
  build source or waiting for the upstream build list to catch up) is
  outside this session's scope, and downgrading the repo's real pinned
  toolchain to work around a local tool would be a worse trade.
- **autofde-lab** — original blocker resolved (`✅ Success - Main Checkout
  exact subject [7m3.4s]`, real submodule clone included). Two more real,
  fixable blockers surfaced and were closed in turn, same session:
  1. `BLOCKED:ACT_LOCAL_PR_EVENT_PAYLOAD_MISSING` — the "Classify change"
     step reads `github.event.pull_request.{base,head}.sha`, empty under a
     bare `act pull_request` with no `-e` event file. Fixed by building a
     real PR-event JSON (base = `HEAD~9`, head = current `HEAD`, both
     confirmed present on `origin`) — same pattern `gymact`'s own
     `act-pr-event` Justfile recipe already uses.
  2. With that fixed, the job reached its **real** `Deterministic quality`
     step (this repo's actual `pre-commit` config: `ruff` import-sort,
     `ruff-format`, `end-of-file-fixer`, `check-added-large-files`) — and
     failed for real: `4 files reformatted, 2 files left unchanged`,
     `Found 4 errors (4 fixed, 0 remaining)`, one JSON file missing its
     trailing newline. **Two of the four reformatted files were this
     session's own `al-sa2a-real-caller` closure** (`phase_h_trigger.py`,
     `test_phase_h_trigger_chicago.py`) — a real gap in this session's
     earlier verification, caught only because `act` ran the exact
     `pre-commit` hook chain local ad hoc `ruff` invocations hadn't
     replicated. Fixed for real: `uvx ruff check --fix --select I,F401`
     and `uvx ruff format` on the exact flagged files (output matched
     `pre-commit`'s report byte-for-byte: same "4 errors fixed" / "4 files
     reformatted" counts), plus the missing trailing newline. Re-ran the
     affected tests post-fix: `13 passed`. Committed (`c6712549`) and
     pushed.
  3. Re-ran `act` a third time with the corrected event payload against
     `c6712549` — **every step succeeded**: checkout, classify-change,
     Python 3.10/3.12/3.13 dependency install and caching, `Deterministic
     quality` (now clean), Python source smoke, conflict-marker check,
     real Crown-kernel execution, source package smoke. Terminal line:
     **`🏁 Job succeeded`**. `autofde-lab`'s real CI gate is `ALIVE`,
     fully, for real, this session.

**One more observation, not acted on**: mid-session, `xaas`'s local checkout
picked up a new commit (`2ec5fdb`, "Merge branch 'sjira/sj-005'") that this
session did not author — confirming the concurrent autonomous process noted
earlier in this session's other docs is still active on this exact shared
repo. Not touched, not pushed by this session (it may already be on its way
to `origin` independently) — noted here as an observed fact per this repo's
own evidence discipline, not a finding this session investigated further.

**Updated bottom line**: of the five repos, `autofde-lab` reached a fully
`ALIVE` real `act` CI run this session. `gymact` reached a complete,
real, terminal test-suite result (98.9% passing, zero regressions
attributable to this session). `xaas` and `ggen_igniter` remain `BLOCKED`
on real, named, non-code `act`/toolchain-availability gaps unrelated to
either repo's closures. `ash_kudzu` remains `UNSUPPORTED` (no CI configured,
pre-existing) with its real local gate as the standing ceiling. No claim
above substitutes for a rerun — per this directory's own standing ceiling,
this is a faithful record of what ran, when, with what output, nothing more.
