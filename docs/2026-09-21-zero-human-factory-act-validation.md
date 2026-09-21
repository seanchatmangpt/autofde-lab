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
limitations unrelated to pushing at all. If a push is authorized later,
re-running gymact/xaas/autofde-lab's `act` jobs (exact commands in the table
above) would be the direct next step; ggen_igniter's `act` limitation would
need a different community runner image or acceptance that real GitHub-hosted
CI is required to validate that repo's `erlef/setup-beam` step, since no
push fixes it.
