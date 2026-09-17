# AFDE-2605: this repo is not the CMCA execution-route selector — at most a consumer seam

- **Status**: OPEN (scoping ticket; no code changed by this ticket)
- **Severity**: Medium — scoping/naming-collision risk, not a live defect. The risk is a
  future pass conflating this repo's pre-existing, differently-scoped `CMCA` module with the
  route selector `A2A-2605` describes, and wrongly claiming cross-repo closure from local code.
- **Standing**: `NOT_FOUND` for the object `A2A-2605` actually asks for (a lawful selector
  over `KNOWN_DETERMINISTIC` / `UNKNOWN_LOCAL` / `UNKNOWN_IDLE_ESTATE` / `UNKNOWN_FRONTIER` /
  `REFUSED` execution routes). A same-acronym, different-concept module already exists here and
  is `PARTIAL_ALIVE`/tested — see Problem and Local verification below; the two must not be
  read as the same claim.
- **Owning repo(s)**: per the source ticket
  (`A2A-2605-cmca-resource-allocation-control-plane.md`), primary owners are
  `seanchatmangpt/ggen` and `seanchatmangpt/bcinr`, with `seanchatmangpt/ash_a2a` as the
  integration surface. **`autofde-lab` is not a primary owner of this surface.** Per
  `.claude/rules/ecosystem-boundary.md`, this repo computes candidate plans and projects them
  into POWL; a selector that chooses *which compute tier executes a route* (deterministic vs.
  local vs. idle-estate vs. frontier inference) is portfolio-control-plane machinery, the same
  class of authority that file already reserves to the broker/admission layer (`mfw`), not to
  this repo. This ticket makes only claims this repo can back with its own source and tests.

## Problem

Three things, each verified in-repo this session (commands and output below):

1. **The route-class vocabulary `A2A-2605` requires does not exist anywhere in this repo.**
   `KNOWN_DETERMINISTIC`, `UNKNOWN_LOCAL`, `UNKNOWN_IDLE_ESTATE`, `UNKNOWN_FRONTIER`, and any
   `RouteClass`/`ExecutionRoute` type are zero-hit across `src/` and `tests/`. Nothing here
   selects among execution tiers under a bounded objective, and nothing here could honestly be
   described as `PARTIAL_ALIVE` toward that specific object.

2. **A same-acronym, unrelated module already exists and must not be conflated with it.**
   `src/autofde_lab/cmca/` and `src/autofde_lab/sa2a/unknown/allocator.py` implement "CMCA" —
   but here it expands to **Chatman Multifractal Cascade Allocation** (`cmca/contracts.py:3`)
   / **Chatman Multifractal Consequence Allocation** (`cmca/bcinr_bridge.py:3`), a
   salience/entropy-weighted budget allocator that spreads a bounded exploration budget
   (compute ticks, tokens, experiments) across up to 8 already-generated candidate branches on
   the *epistemic* `UNKNOWN` frontier (`sa2a/unknown/resolution.py`'s `EpistemicState`:
   `UNKNOWN` / `CANDIDATE` / `KNOWN` / `REFUSED` — a 4-state admission lattice, not a 5-class
   execution-tier selector). It optionally delegates ranking to a vendored `cmca_rank_cli`
   binary (`cmca/bcinr_bridge.py`, `utils.py:407-474`). This is real, tested, working code —
   see Local verification — but it answers "how much search budget does candidate X get,"
   never "which compute tier should run this work." Two different objects share one acronym by
   coincidence of naming convention (`CMCA` = "Chatman [something] Cascade/Consequence
   Allocation" locally vs. "Combinatorial Maximalism Compute Allocation" in `A2A-2605`), not by
   shared design. Treating them as the same claim would be exactly the conflation
   `no-dual-bookkeeping.md` and `absence-is-not-evidence.md` warn against — coincidence of a
   label is not evidence of the relation.

3. **The closest thing to a local "selector" is `match_solvers(ranked=True)`
   (`utils.py:407`), and it ranks solver candidates within one already-admitted domain — not
   execution routes across compute tiers.** It is also not the no-op two of this repo's own
   doctrine files currently claim. `.claude/rules/ecosystem-boundary.md:63-65` and
   `src/autofde_lab/CLAUDE.md`'s invariant 3 both still say `ranked=True` "accepts the flag and
   ignores it" (citing a stale `utils.py:126` line number). Source and `git log` show that was
   fixed over a month before this session: commits `571e834f` (`feat(solvers): implement
   ranked=True via optional cmca_rank_cli governed ranking`), `9cfbfdf7`, `a6dd0523`, dated
   2026-08-13. `ranked=True` now really computes 4 structural measures, pre-filters to the
   CLI's 8-candidate cap, and — if the vendored `cmca_rank_cli` binary is resolvable — reorders
   by its returned share; otherwise it degrades to the existing match order, never raising.
   This is a genuine, if narrow and non-authoritative, capability: it selects among already
   domain-admitted *solvers*, not among *execution tiers*, carries no authority/admission
   semantics (`cmca/contracts.py:6`: "CMCA performs SELECT, never ambient DO" — same
   discipline as `A2A-2605`'s own "must not grant authority, execute DO, or mutate ontology"),
   and its real-CLI success path is environment-gated (`cmca_rank_cli` is not resolvable on
   this machine — see Local verification). Both doctrine files are stale and should be
   corrected in a follow-up that is out of scope for this ticket.

## Required change (scoped to what this repo can honestly contribute)

This repo may not build the CMCA route selector. What it can lawfully contribute, as a
consumer/seam only:

1. **Accept an externally-admitted route decision, don't compute one.** The existing
   injection point is real today: `UnknownResolutionPipeline.__init__(self, *, allocator:
   CMCACandidateAllocator | None = None, ...)` (`sa2a/unknown/resolution.py:86-96`) already
   takes its allocator by constructor injection rather than hardcoding it. A future adapter
   implementing the same duck-typed `allocate(*, plan_id, budget, candidates) ->
   FrontierAllocationPlan` surface — but backed by a route decision that `ggen`/`bcinr` admits
   externally, rather than this repo's own salience math — is the honest local seam. No such
   adapter exists yet; this ticket does not create one.
2. **`match_solvers(ranked=True)`'s optional `cmca_rank_cli` transport is a real, narrow
   precedent for "defer ranking to an external, receipted process rather than compute it
   locally"** (`utils.py:420-469`), but it ranks solver classes, not execution routes, and
   returns a bare `(solver_type, float)` pair with no route-class, authority, or receipt
   fields. It is evidence this repo already knows how to consume an external ranking signal
   without owning it — not evidence toward `A2A-2605` itself.
3. Correct the stale "no-op" claim in `.claude/rules/ecosystem-boundary.md` and
   `src/autofde_lab/CLAUDE.md` invariant 3 (both point at `utils.py:126`, which is now
   `match_solvers` at line 407 with real behavior) — named here as a follow-up, not fixed by
   this ticket, since fixing doctrine files was not in this ticket's scope.

## Laws that actually apply locally

Only the two this repo already enforces, both narrower than `A2A-2605`'s six:

1. `cmca/contracts.py:6` — "CMCA performs SELECT, never ambient DO." Locally true of both the
   existing allocator and of `match_solvers(ranked=True)`: neither grants authority, executes,
   or mutates ontology. This is the same shape as `A2A-2605` law 6's "CMCA may SELECT a route.
   It must not grant authority, execute DO, or mutate ontology" — convergent design, not
   evidence the two systems are the same object.
2. `.claude/rules/ecosystem-boundary.md`'s standing boundary itself: this repo may compute
   candidate plans and project them; it may not claim admission, broker, or actuation standing.
   A CMCA execution-route selector is exactly that kind of control-plane authority, so this
   repo is structurally the wrong owner for it regardless of what local code happens to exist.

## Chicago falsifiers

None of `A2A-2605`'s five falsifiers are locally testable — there is no route selector here to
falsify (`NOT_FOUND`, not `BLOCKED`). The one falsifier this ticket can state honestly, scoped
to the seam claim above rather than to the selector itself:

1. If `UnknownResolutionPipeline` is ever constructed with an `allocator` whose `.allocate(...)`
   return value cannot be traced back to an external, receipted admission (i.e. the pipeline
   silently falls back to computing its own `CMCACandidateAllocator` allocation while claiming
   an externally-admitted route was used), that is a `no-dual-bookkeeping.md` violation and
   must refuse rather than silently substitute.

## Definition of done

Scoped to what this repo can close, not to `A2A-2605` as a whole:

- This ticket exists and states plainly that `autofde-lab` is not a primary owner of the CMCA
  route selector (`ggen`/`bcinr` own it, `ash_a2a` integrates it) — **done, this document**.
- The naming collision between this repo's existing `CMCA` (Chatman Multifractal
  Cascade/Consequence Allocation, resource-budget allocator) and `A2A-2605`'s `CMCA`
  (Combinatorial Maximalism Compute Allocation, execution-route selector) is recorded so a
  future pass does not read one as evidence for the other — **done, this document**.
- **Not done, and out of scope here**: building the adapter described in "Required change" #1,
  or correcting the stale doctrine lines in `.claude/rules/ecosystem-boundary.md` /
  `src/autofde_lab/CLAUDE.md`. Both are named as real, specific follow-up work, not claimed as
  closed.
- This repo can never mark `A2A-2605` itself closed — full closure requires `ggen`/`bcinr`'s
  route-selector IR and `ash_a2a`'s consumption of it, none of which exist in this repository.

## Local verification (this session)

All commands run from `/Users/sac/autofde-lab` on 2026-09-16, branch
`feat/semantic-model-manufacturing`.

### 1. Route-class vocabulary the source ticket requires — zero hits

```bash
$ grep -rn "IDLE_ESTATE\|idle_estate\|SHLLM\|FRONTIER_INFERENCE\|UNKNOWN_FRONTIER\|UNKNOWN_LOCAL\|KNOWN_DETERMINISTIC\|route_class\|RouteClass\|ExecutionRoute" src/ tests/; echo "grep_exit=$?"
grep_exit=1
```

(zero matching lines printed; `grep_exit=1` confirms no match anywhere under `src/` or
`tests/` — the vocabulary is absent, not merely un-searched.)

### 2. This repo's own `CMCA` acronym — real, extensive, and a different concept

```bash
$ grep -rln "CMCA\|Combinatorial Maximalism Compute Allocation" src/ tests/ | wc -l
      39
```

39 files reference `CMCA` (module docstrings confirm the expansion is "Chatman Multifractal
Cascade Allocation" / "Chatman Multifractal Consequence Allocation" locally, e.g.
`src/autofde_lab/cmca/contracts.py:3`, `src/autofde_lab/cmca/bcinr_bridge.py:3`,
`src/autofde_lab/cmca/__init__.py:1`) — none of the 39 files contain the string
"Combinatorial Maximalism Compute Allocation" itself; that expansion is unique to the source
ticket, not present anywhere in this repo.

### 3. The local `CMCA` allocator module is real and passes its tests, this session

```bash
$ .venv/bin/python -m pytest tests/cmca/test_cascade_math.py tests/sa2a/test_unknown_bridge.py -v
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
collected 18 items

tests/cmca/test_cascade_math.py .......                                  [ 38%]
tests/sa2a/test_unknown_bridge.py ...........                            [100%]

============================== 18 passed in 0.91s ==============================
```

### 4. `match_solvers(ranked=True)` is real and environment-gated, not the no-op the doctrine
   files currently claim

```bash
$ .venv/bin/python -m pytest tests/fabric/test_phi_dispatch_chicago.py -v
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
collected 9 items

tests/fabric/test_phi_dispatch_chicago.py .......ss                      [100%]

=========================== short test summary info ============================
SKIPPED [1] tests/fabric/test_phi_dispatch_chicago.py:177: cmca_rank_cli binary not
  resolvable in this environment (checked CMCA_RANK_CLI_BIN and
  $BCINR_HOME/target/debug/cmca_rank_cli); ranked=True's optional binary-present path is
  skipped, not faked
SKIPPED [1] tests/fabric/test_phi_dispatch_chicago.py:238: cmca_rank_cli binary not
  resolvable in this environment (checked CMCA_RANK_CLI_BIN and
  $BCINR_HOME/target/debug/cmca_rank_cli)
========================= 7 passed, 2 skipped in 7.10s =========================
```

7 passed (the pre-filter/fallback real logic path), 2 named-skip (the real-CLI success path is
`UNSUPPORTED` on this machine — `cmca_rank_cli` binary absent — a genuine environment gate per
the Chicago-style skipif discipline, not a silent mock substitution).

### 5. `ranked=True`'s implementation date — the doctrine files' claim is stale, not current

```bash
$ git log --oneline -3 -- src/autofde_lab/utils.py
a6dd0523 fix(solvers): correct match_solvers' declared return type for the real float-share ranked path
9cfbfdf7 fix(solvers): pre-filter to <=8 candidates so ranked=True's real success path actually fires, not just the fallback
571e834f feat(solvers): implement ranked=True via optional cmca_rank_cli governed ranking
$ git log -1 --format="%H %ad" --date=short -- src/autofde_lab/utils.py
a6dd052386e90d989a6aa382dd38ade8128ffffd 2026-08-13
```

`.claude/rules/ecosystem-boundary.md:63-65` and `src/autofde_lab/CLAUDE.md` invariant 3 both
still assert the pre-2026-08-13 no-op behavior at the time of this ticket. Correcting them is
named as follow-up work in "Required change" #3, not performed here.

## See also

- `A2A-2605-cmca-resource-allocation-control-plane.md` (source ticket this responds to) —
  scratchpad copy at
  `/private/tmp/claude-501/-Users-sac-autofde-lab/805b2d1b-7d56-456a-b169-7ab879cabf6b/scratchpad/ash_a2a_tickets/A2A-2605-cmca-resource-allocation-control-plane.md`;
  not part of this repository.
- `.claude/rules/ecosystem-boundary.md` — the boundary law this ticket applies.
- `.claude/rules/standing-law.md` — the status vocabulary used above.
- `.claude/rules/no-dual-bookkeeping.md` / `.claude/rules/absence-is-not-evidence.md` — why the
  two `CMCA` objects in Problem #2 must not be read as one claim.
- `src/autofde_lab/cmca/`, `src/autofde_lab/sa2a/unknown/` — this repo's real, unrelated `CMCA`
  module.
- `src/autofde_lab/utils.py:407-474` (`match_solvers`) — the closest local analog to a
  selector, and exactly how far short of `A2A-2605`'s laws it falls.

## Local closure work (fix implemented)

Follow-up #3 from "Required change" above (correcting the stale doctrine lines) was
completed this session, 2026-09-16, branch `feat/semantic-model-manufacturing`. Scope: a
documentation-accuracy fix only — no source under `src/autofde_lab/utils.py` or any test
was touched.

**What was corrected.** Both doctrine files previously stated `match_solvers(ranked=True)`
"accepts the flag and ignores it," citing a stale `utils.py:126` line number. That claim was
already known false by the time this ticket was opened (see Problem #3 and Local
verification #4/#5 above) — commits `571e834f`, `9cfbfdf7`, `a6dd0523` (all 2026-08-13)
implemented `ranked=True` for real, over a month before this ticket. Both files now state
the real, current, environment-gated behavior and cite the real commit and the real
`utils.py:407-474` location:

- `.claude/rules/ecosystem-boundary.md` (the paragraph immediately preceding "## See also")
- `src/autofde_lab/CLAUDE.md` invariant 3

Neither file's surrounding context (the "measured, not delegated" conclusion in
`ecosystem-boundary.md`; the rest of `src/autofde_lab/CLAUDE.md`'s invariants and its
Update-obligations section) was deleted — only the stale factual sentence in each was
replaced. That conclusion (`ranked=True`'s real-CLI success path is itself
environment-gated on this machine) is still true and is restated in the corrected text with
its own evidence (`tests/fabric/test_phi_dispatch_chicago.py`'s two named skips).

**Not fixed here, named as a further follow-up.** `docs/ecosystem-standing.md` carries the
same stale "accepts the flag and ignores it" / `utils.py:126` claim in three places (lines
463, 672, 679 as of this session) and was not in this ticket's stated two-file scope, so it
was left untouched. It is stale in the same way and by the same evidence as the two files
fixed here. Also untouched, and noted for the same reason: `src/autofde_lab/CLAUDE.md`'s
own "Update obligations" section still reads "If `ranked` is ever implemented, delete
invariant 3 here and in `.claude/rules/ecosystem-boundary.md` and
`docs/ecosystem-standing.md` together" — `ranked` has now been implemented for over a
month, and the chosen fix corrected invariant 3 in place rather than deleting it (per this
session's explicit scope: a documentation-accuracy correction, not a doctrine restructure),
so that bullet is now itself stale relative to the action actually taken. Both of these are
real, specific, out-of-scope-for-this-pass findings, not claimed as closed.

### Verification (this session)

```bash
$ cd /Users/sac/autofde-lab && pwd
/Users/sac/autofde-lab
$ grep -n "571e834f\|is implemented, not a no-op" .claude/rules/ecosystem-boundary.md src/autofde_lab/CLAUDE.md
.claude/rules/ecosystem-boundary.md:63:`match_solvers(..., ranked=True)` is implemented, not a no-op (as of commit
.claude/rules/ecosystem-boundary.md:64:`571e834f`, "feat(solvers): implement ranked=True via optional cmca_rank_cli
src/autofde_lab/CLAUDE.md:44:3. **`match_solvers(..., ranked=True)` is implemented, not a no-op** (`utils.py:407-474`,
src/autofde_lab/CLAUDE.md:45:   commit `571e834f` "feat(solvers): implement ranked=True via optional cmca_rank_cli
$ .venv/bin/python -m pytest tests/fabric/test_phi_dispatch_chicago.py -v
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
rootdir: /Users/sac/autofde-lab
configfile: pyproject.toml
plugins: anyio-4.14.0, nbmake-1.5.5, cov-7.1.0, xdist-3.8.0, timeout-2.4.0, cases-3.10.1
collected 9 items

tests/fabric/test_phi_dispatch_chicago.py .......ss                      [100%]

=========================== short test summary info ============================
SKIPPED [1] tests/fabric/test_phi_dispatch_chicago.py:177: cmca_rank_cli binary not
  resolvable in this environment (checked CMCA_RANK_CLI_BIN and
  $BCINR_HOME/target/debug/cmca_rank_cli); ranked=True's optional binary-present path is
  skipped, not faked
SKIPPED [1] tests/fabric/test_phi_dispatch_chicago.py:238: cmca_rank_cli binary not
  resolvable in this environment (checked CMCA_RANK_CLI_BIN and
  $BCINR_HOME/target/debug/cmca_rank_cli)
========================= 7 passed, 2 skipped in 3.88s =========================
```

Identical result to the prior session's cited `7 passed, 2 skipped` (only the wall-clock
duration differs: `3.88s` here vs. `7.10s` previously — same collected count, same pass/skip
split, same two named skip reasons at the same line numbers). No source file changed, so an
identical result is exactly what a documentation-only fix predicts; a divergent result would
have been the falsifier.

### Standing

`ALIVE` — scoped narrowly to the documentation-accuracy fix itself: both cited stale
sentences are corrected in place with real commit/file:line citations, confirmed present on
disk by a real `grep` this session, and the pre-existing Chicago test this ticket depends on
for evidence was re-run this session with an identical, real, pasted result. This standing
claim covers only "the two named stale sentences are now accurate and evidenced" — it is not
a claim about `A2A-2605` itself, which this repo still cannot close (see Definition of done
above, unchanged by this update).

## Third-file closure: `docs/ecosystem-standing.md` (this session, 2026-09-16)

The prior entry above named `docs/ecosystem-standing.md` as carrying the same stale
`match_solvers(..., ranked=True)` "accepts the flag and ignores it" / `utils.py:126` claim in
three places (lines 463, 672, 679 at the time) and left it untouched as an explicit
out-of-scope follow-up. That follow-up is closed in this session, on the same branch
(`feat/semantic-model-manufacturing`), as a documentation-accuracy fix only — no source file
and no test was touched.

**What was corrected.** All three occurrences (originally at lines 463, 672, 679; the file's
line numbers shifted slightly as each edit expanded its sentence) now state the same real,
current, environment-gated fact already landed in `.claude/rules/ecosystem-boundary.md` and
`src/autofde_lab/CLAUDE.md` invariant 3: `match_solvers(..., ranked=True)` is implemented, not
a no-op, as of commit `571e834f` ("feat(solvers): implement ranked=True via optional
cmca_rank_cli governed ranking", 2026-08-13, with follow-up fixes `9cfbfdf7` and `a6dd0523`
the same day) — see `src/autofde_lab/utils.py:407-474`. It scores matched solvers via 4 real
class-level measures and, when the optional `cmca_rank_cli` binary is resolvable
(`BCINR_HOME`/`CMCA_RANK_CLI_BIN` convention), reorders the top 8 by its returned share;
otherwise it degrades to existing match order, never raising. The real-CLI success path
remains environment-gated (`cmca_rank_cli` is not resolvable on this machine —
`tests/fabric/test_phi_dispatch_chicago.py` names both skips).

**What was preserved, not deleted.** Every corrected paragraph's surrounding conclusion —
S8's "comparison is measured, not delegated to `match_solvers`" and the Capability Surface
section's "comparison must be genuinely measured (run them, compare plans/costs) or the claim
is empty" — is restated with its stale premise replaced, not removed. The conclusion itself
was already true and remains true: even with `ranked=True` real, its real-CLI path is
unexercised on this machine, so an unmeasured "dominated" verdict here would still be an empty
claim. The `docs/CLAUDE.md` invariant "historical corrections stay visible" is honored — this
is a correction of a stale premise beside its original context, not a silent rewrite.

**Verification (this session).**

```bash
$ cd /Users/sac/autofde-lab && pwd
/Users/sac/autofde-lab
$ grep -n "accepts the flag and ignores it\|ranked.*accepted but ignored\|utils.py:126" docs/ecosystem-standing.md; echo "exit=$?"
exit=1
$ grep -n "571e834f" docs/ecosystem-standing.md
464:no-op (commit `571e834f`, "feat(solvers): implement ranked=True via optional cmca_rank_cli
677:  across the whole registry; as of commit `571e834f` (2026-08-13) `ranked=True` is real, not a
682:1. **`ranked=True` is implemented, not a no-op** — `utils.py:407-474` (commit `571e834f`,
$ .venv/bin/python -m pytest tests/fabric/test_phi_dispatch_chicago.py -v
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.3.5, pluggy-1.6.0
collected 9 items

tests/fabric/test_phi_dispatch_chicago.py .......ss                      [100%]

========================= short test summary info =============================
SKIPPED [1] tests/fabric/test_phi_dispatch_chicago.py:177: cmca_rank_cli binary not
  resolvable in this environment (checked CMCA_RANK_CLI_BIN and
  $BCINR_HOME/target/debug/cmca_rank_cli); ranked=True's optional binary-present path is
  skipped, not faked
SKIPPED [1] tests/fabric/test_phi_dispatch_chicago.py:238: cmca_rank_cli binary not
  resolvable in this environment (checked CMCA_RANK_CLI_BIN and
  $BCINR_HOME/target/debug/cmca_rank_cli)
================== 7 passed, 2 skipped, 5 warnings in 18.38s ===================
```

Identical pass/skip split (7 passed, 2 skipped, same two named-skip reasons at the same line
numbers) to both the prior session's and this ticket's own earlier-cited results — exactly
what a documentation-only, zero-source-file-changed fix predicts.

### Doctrine consistency — all three files now agree

| File | Location | States |
|---|---|---|
| `.claude/rules/ecosystem-boundary.md` | paragraph before "## See also" | `ranked=True` real, commit `571e834f`, `utils.py:407-474`, environment-gated |
| `src/autofde_lab/CLAUDE.md` | invariant 3 | same fact, same commit, same citation |
| `docs/ecosystem-standing.md` | S8 (~line 462-467) and Capability surface (~line 668-693) | same fact, same commit, same citation, in 3 sentences |

All three doctrine files now cite the same real commit (`571e834f`) and the same real
location (`src/autofde_lab/utils.py:407-474`) for `match_solvers(..., ranked=True)`, and all
three state the same environment-gating fact (`cmca_rank_cli` unresolvable on this machine,
per `tests/fabric/test_phi_dispatch_chicago.py`'s two named skips). No file in this repo's
doctrine set still asserts the pre-2026-08-13 no-op behavior.

### Standing (updated)

`ALIVE` — scoped to the documentation-accuracy fix in `docs/ecosystem-standing.md`: all three
cited stale sentences are corrected in place with real commit/file:line citations, confirmed
present on disk by a real `grep` this session (zero stale-string matches, three
`571e834f`-citing matches), and the pinned Chicago test this ticket depends on for evidence
was re-run this session with a result identical in pass/skip shape to the prior verification.
This closes the one remaining out-of-scope item named in the entry above — the stale
`match_solvers(ranked=True)` claim is now corrected identically across all three doctrine
files this repo owns (`.claude/rules/ecosystem-boundary.md`, `src/autofde_lab/CLAUDE.md`,
`docs/ecosystem-standing.md`). It remains, as before, not a claim about `A2A-2605` itself —
this repo still cannot close that ticket (see Definition of done above, unchanged).
