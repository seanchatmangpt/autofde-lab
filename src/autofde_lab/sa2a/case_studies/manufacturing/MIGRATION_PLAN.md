# MIGRATION_PLAN — sa2a-mfg-01 scratch prototype into a permanent package

Status of this document: **design only**, per the harness task. Nothing under
`src/autofde_lab/sa2a/case_studies/manufacturing/` is created or moved by
writing this file. It is the exact, minimal-diff plan for MFG-01A (baseline
artifact admitted into repo) — one of four planned phases (MFG-01A..D) — and
it deliberately does not implement, generalize, or improve anything the
scratch prototype at `.claude/scratch/sa2a-mfg-01/` already does. Acceptance
per the task: the current evidence (three seeded OCEL traces, byte-for-byte
replay determinism, the three independently-checked invariants) is
**preserved exactly**, not changed.

Source read in full before writing this plan: `CONTRACT.md`,
`ocel_adapter.py`, `resource_agent.py`, `authority_agent.py`, `actuator.py`,
`verifier.py`, `runtime.py` (all seven files under
`.claude/scratch/sa2a-mfg-01/`), plus `src/autofde_lab/sa2a/__init__.py`,
`src/autofde_lab/sa2a/experience/__init__.py` (style reference), the repo
root `CLAUDE.md`, `src/autofde_lab/CLAUDE.md`, and `docs/STATUS.md`'s current
pass-section format.

---

## 0. Standing this migration may claim (stated up front, so no file below
   overclaims it)

Per `.claude/rules/standing-law.md`, split by dimension:

- `technicalStanding`: **PARTIAL_ALIVE**. The scratch prototype's own
  evidence is real (observed multi-agent execution, real OCEL 2.0 output,
  replay-determinism, three independently-checked BRCE-adjacent invariants —
  see §4's test suite, which re-derives all three from durable log data
  alone, never from the runtime's internal counters). It is `PARTIAL_ALIVE`
  and not `ALIVE` because the larger claim — that this case study
  generalizes beyond the hardcoded M1-M4 plant, or that its HDDL/POWL/FOND
  projection exists — does not follow from today's evidence. This
  migration changes *where the code lives*, not what it can prove.
- `organizationalStanding`: **UNKNOWN** (no accountable customer acceptance
  of this case study exists; not moved by this migration).
- `enterpriseStanding`: **UNKNOWN** (requires the above two `ALIVE`; not
  claimed here).

Every docstring this plan proposes below states explicitly: today's
`BASELINE` dict, `RESOURCE_IDS` tuple, and rule-based agent policies are the
**paper-fixture baseline** for a fixed four-machine plant, not yet
generator-driven (`G(seed, θ) → W`, planned MFG-01B), and this package
contains no HDDL/POWL/FOND projection (planned MFG-01C) and no frontier
falsifier (planned MFG-01D). None of those three later phases exist after
this migration; the docstrings must not imply they do.

---

## 1. Target file list — exact renames, exact destinations

Renames follow this repo's real package convention (read from
`src/autofde_lab/sa2a/experience/`, `src/autofde_lab/sa2a/release/`): a
package directory with `__init__.py` re-exporting the module's public
surface, module docstrings that open with the module's own name and its
governing spec/PRD-style reference, `from __future__ import annotations`,
and real type hints (`dict[str, Any]`, `tuple[dict, dict | None]`, etc. —
not the scratch prototype's bare `dict`/`list` in a couple of spots).

| # | Scratch source (`.claude/scratch/sa2a-mfg-01/`) | Permanent destination (`src/autofde_lab/sa2a/case_studies/manufacturing/`) | Rename rationale |
|---|---|---|---|
| 1 | `CONTRACT.md` | `CONTRACT.md` (same name, same directory) | Kept verbatim as the binding interface spec this package implements; it is documentation, not code, so it is copied unchanged except for the one path fix in §2 row 1. |
| 2 | `ocel_adapter.py` | `ocel_adapter.py` | No rename — already the correct, singular, non-colliding name. Becomes a sibling module in the new package, not the standalone top-level module the scratch version was. |
| 3 | `resource_agent.py` | `resource_agent.py` | **No rename needed on this file** — the scratch file is already named `resource_agent.py` singular. (The task's naming-collision warning refers to the module's own internal docstring line 1, which literally says `"""resource_agents.py — ...` — a stale filename reference left over from an earlier draft, even though the actual file on disk is `resource_agent.py` singular. Fix: update that one docstring line to say `resource_agent.py`, per §2 row 3 — this is the "avoid the resource_agent/resource_agents collision" the task names, resolved by making the docstring agree with the filename that is already canonical, not by renaming the file.) |
| 4 | `authority_agent.py` | `authority_agent.py` | No rename. |
| 5 | `actuator.py` | `actuator.py` | No rename. |
| 6 | `verifier.py` | `verifier.py` | No rename. |
| 7 | `runtime.py` | `runtime.py` | No rename. |
| 8 | `round14_e2o.mmd` | `fixtures/round14_e2o.mmd` | Moved into the fixtures subpackage (§3), not left at the case-study root. |
| 9 | `round14.mmd` | `fixtures/round14.mmd` | Same. |
| 10 | `episode_seed1.ocel.json` (1.8 MB) | **not committed** — regenerated on demand by the test (§3, §4) | Full per-seed logs stay out of git; only a compact slice is committed (§3). |
| 11 | `episode_seed2.ocel.json` (1.8 MB) | **not committed** — same reason | |
| 12 | `episode_seed3.ocel.json` (1.8 MB) | **not committed** — same reason | |
| — | *(new)* | `__init__.py` | New file — re-exports the public surface (`ResourceAgent`, `AuthorityAgent`, `Actuator`, `VerifierAgent`, `run`, `LogRef`, the domain constants), following the `sa2a/experience/__init__.py` style: one paragraph module docstring naming the governing spec (`CONTRACT.md`, in this package, rather than a PRD/ARD section number — this case study has no PRD/ARD entry, and the docstring must say so) plus an explicit `__all__`. |
| — | *(new)* | `MIGRATION_PLAN.md` | This file. |

No file is deleted from `.claude/scratch/sa2a-mfg-01/`; migration is an
additive copy-and-fix into the permanent location, leaving the scratch
directory in place as the historical record of the independently-written
prototype (it is untracked (`.claude/scratch/` — see this session's git
status) so it carries no history to preserve by deleting it, but deleting it
is out of scope for this plan and not required for acceptance).

---

## 2. Exact minimal changes required per file

Stated as literal per-file diffs — import-path and packaging fixes only,
**never** a logic rewrite. The task's acceptance criterion is that current
evidence is preserved exactly; every change below is mechanical.

### 2.1 `CONTRACT.md`
- One line changes: the "Base directory" path in the header
  (`/Users/sac/autofde-lab/.claude/scratch/sa2a-mfg-01/`) becomes
  `src/autofde_lab/sa2a/case_studies/manufacturing/` (repo-relative, matching
  how other `sa2a` subpackages reference themselves — no absolute
  `/Users/sac/...` path appears anywhere else in `src/autofde_lab/sa2a/`).
- Its final "See also" section, which currently says this simulation "is not
  wired into `openclaw_bridge.py` or any real actuation surface, and carries
  no admission/receipt authority outside this directory" — kept verbatim;
  it is still true and is exactly the actuation-boundary statement
  `.claude/rules/actuation-boundary.md` requires.
- **Add** one new closing section, "## 9. Phase status (MFG-01A)", stating
  in the standing-law vocabulary from §0 above that this contract's own
  domain constants (§0 of the contract) are the paper-fixture baseline, and
  cross-referencing the roadmap (MFG-01B generator, MFG-01C generated
  HDDL/POWL/FOND, MFG-01D frontier falsifier) by name only, with an explicit
  "none of these exist yet" statement — so a future reader of `CONTRACT.md`
  alone, without this migration plan, still gets the honest standing.

### 2.2 `ocel_adapter.py`
- Replace the `sys.path.insert` shim:
  ```python
  # before (scratch — path relative to a file 4 dirs under .claude/scratch/)
  _REPO_ROOT = Path(__file__).resolve().parents[3]
  _SRC = _REPO_ROOT / "src"
  if str(_SRC) not in sys.path:
      sys.path.insert(0, str(_SRC))

  from autofde_lab.ocel.log import OcelLog
  from autofde_lab.ocel.model import OcelAttribute, OcelAttributeValue, OcelObject
  ```
  becomes a real package-relative import (this module is now itself inside
  `autofde_lab`, so it needs no `sys.path` surgery at all):
  ```python
  from autofde_lab.ocel.log import OcelLog
  from autofde_lab.ocel.model import OcelAttribute, OcelAttributeValue, OcelObject
  ```
  Delete the `import sys`, `from pathlib import Path`, and the whole
  `_REPO_ROOT`/`_SRC` block — `pathlib.Path` is still needed by `write_json`,
  so keep that one `from pathlib import Path` import, just drop the
  sys.path lines.
- Module docstring's "Deviation from CONTRACT.md §6" note is kept verbatim
  (still an accurate, load-bearing record of a real deviation that happened
  during the scratch build).
- No other line changes. Every function body, every OCEL vocabulary
  constant, every signature is byte-identical.

### 2.3 `resource_agent.py`
- Line 1 docstring fix (the naming-collision note from §1 row 3): change
  `"""resource_agents.py — the ResourceAgent builder module for sa2a-mfg-01.`
  to
  `"""resource_agent.py — the ResourceAgent builder module for the sa2a manufacturing case study.`
- Import line changes from the flat-module scratch convention to the real
  package's relative-import convention (matching how `sa2a/experience/`
  submodules import each other, e.g. `from autofde_lab.sa2a.experience.types
  import ...`):
  ```python
  # before
  from ocel_adapter import LogRef, record_observation
  # after
  from autofde_lab.sa2a.case_studies.manufacturing.ocel_adapter import (
      LogRef,
      record_observation,
  )
  ```
- No change to `BASELINE`, `RESOURCE_IDS`, `UPTIME_TARGET`,
  `ADJUSTMENT_ENERGY_FRACTION`, `ADJUSTMENT_UPTIME_GAIN`, `DRIFT_MEAN`,
  `DRIFT_STDDEV`, the `ResourceAgent` class body, or `seed_all_agents`. The
  docstring's "Deviations" discussion of the module-name collision the task
  flags is retired (the collision never existed on disk — see §1 row 3) but
  the rest of the docstring (the rule-based-not-scripted explanation) is
  kept verbatim.

### 2.4 `authority_agent.py`
- Same import-line fix pattern:
  ```python
  # before
  from ocel_adapter import LogRef, record_authority_decision
  # after
  from autofde_lab.sa2a.case_studies.manufacturing.ocel_adapter import (
      LogRef,
      record_authority_decision,
  )
  ```
- No other change. `ENERGY_BUDGET_PER_ROUND_KWH`,
  `AUTHORITY_MAX_SHARE_OF_REMAINING_BUDGET`, and the full `decide_round`
  body are byte-identical to the scratch version.

### 2.5 `actuator.py`
- Same import-line fix pattern (`from ocel_adapter import LogRef,
  record_actuation` → the fully-qualified relative-package form). No other
  change to `BASELINE`, `RESOURCE_IDS`, the hashing logic, or
  `Actuator.apply_round`/`Actuator.snapshot`.

### 2.6 `verifier.py`
- Same import-line fix pattern for its `ocel_adapter` import. No change to
  the three re-derivation procedures (zero-unreceipted-actuation, energy
  budget, authority closure) — these are exactly what §4's test suite below
  calls independently.

### 2.7 `runtime.py`
- Import-line fixes for all four sibling modules:
  ```python
  # before
  sys.path.insert(0, str(Path(__file__).resolve().parent))
  import ocel_adapter
  from actuator import Actuator
  from authority_agent import AuthorityAgent
  from resource_agent import ResourceAgent
  # after
  from autofde_lab.sa2a.case_studies.manufacturing import ocel_adapter
  from autofde_lab.sa2a.case_studies.manufacturing.actuator import Actuator
  from autofde_lab.sa2a.case_studies.manufacturing.authority_agent import (
      AuthorityAgent,
  )
  from autofde_lab.sa2a.case_studies.manufacturing.resource_agent import (
      ResourceAgent,
  )
  ```
  Delete the `import sys`, `from pathlib import Path`, and the
  `sys.path.insert` line — no longer needed once this is a real
  installed-package module.
- The module docstring's `Invocation: python runtime.py <seed>
  <output_ocel_json_path>` line is updated to the real invocation form
  (`python -m autofde_lab.sa2a.case_studies.manufacturing.runtime <seed>
  <output_ocel_json_path>`, following this repo's `python -m` convention
  per `.claude/rules/architecture.md`'s "no packaged console script exists
  yet" note) if `runtime.py` keeps a `if __name__ == "__main__":` CLI entry
  point — kept verbatim in every other respect: `run()`'s full body,
  `BASELINE`, `RESOURCE_IDS`, `ENERGY_BUDGET_PER_ROUND_KWH`,
  `UPTIME_TARGET`, `STABLE_ROUNDS_TO_STOP`, `MAX_ROUNDS`, and the entire
  round loop are byte-identical.

### 2.8 New `__init__.py`
Not a change to an existing file — a new ~20-line file. Docstring states
the paper-fixture-baseline standing from §0, references `CONTRACT.md`, and
exports:
```python
from autofde_lab.sa2a.case_studies.manufacturing.actuator import Actuator
from autofde_lab.sa2a.case_studies.manufacturing.authority_agent import AuthorityAgent
from autofde_lab.sa2a.case_studies.manufacturing.ocel_adapter import LogRef, new_log_ref
from autofde_lab.sa2a.case_studies.manufacturing.resource_agent import ResourceAgent
from autofde_lab.sa2a.case_studies.manufacturing.runtime import run
from autofde_lab.sa2a.case_studies.manufacturing.verifier import VerifierAgent

__all__ = [
    "Actuator",
    "AuthorityAgent",
    "LogRef",
    "ResourceAgent",
    "VerifierAgent",
    "new_log_ref",
    "run",
]
```
(`VerifierAgent` export assumes that is the real class name in
`verifier.py` — confirmed by reading the file: the module docstring names
`VerifierAgent(log_ref)` as its constructor signature.)

No other file under `src/autofde_lab/sa2a/case_studies/manufacturing/`
changes. In particular, **zero changes** to any domain constant
(`BASELINE`, `RESOURCE_IDS`, `ENERGY_BUDGET_PER_ROUND_KWH`,
`UPTIME_TARGET`, `STABLE_ROUNDS_TO_STOP`, `MAX_ROUNDS`,
`ADJUSTMENT_ENERGY_FRACTION`, `ADJUSTMENT_UPTIME_GAIN`, `DRIFT_MEAN`,
`DRIFT_STDDEV`, `AUTHORITY_MAX_SHARE_OF_REMAINING_BUDGET`) and **zero
changes** to any decision rule, hashing rule, or clock rule — this
preserves byte-for-byte replay determinism for a given seed, which is
exactly the property the acceptance criterion requires unchanged.

---

## 3. Compact reproducible fixture — exact paths

The three full per-seed logs (`episode_seed{1,2,3}.ocel.json`, 1.8 MB each)
are **not** committed. Per the task, they are regenerable on demand by the
test (§4) — `runtime.run(seed=...)` is deterministic and cheap enough
(≤200 rounds × 4 resources, pure Python, no I/O) to re-run in a test, so
committing static 1.8 MB blobs would be pure duplication of what the code
itself can reproduce, and would drift the moment any of §2's byte-identical
files stopped being byte-identical — exactly the dual-bookkeeping failure
`.claude/rules/no-dual-bookkeeping.md` names for derived state.

What *is* committed, under a new `fixtures/` subpackage of this case study
(not `docs/evidence/sa2a-mfg-01/`, to keep the fixture co-located with the
code that consumes it — matching how other `sa2a` subpackages that need
fixture data keep it inside their own tree rather than under `docs/`):

| Path | Content | Size class | Purpose |
|---|---|---|---|
| `src/autofde_lab/sa2a/case_studies/manufacturing/fixtures/__init__.py` | empty/docstring-only | tiny | makes `fixtures` a real subpackage |
| `src/autofde_lab/sa2a/case_studies/manufacturing/fixtures/round14.mmd` | copied verbatim from scratch | 4 KB | the existing Mermaid slice of round 14's object/event graph — human-readable evidence artifact, kept exactly as produced |
| `src/autofde_lab/sa2a/case_studies/manufacturing/fixtures/round14_e2o.mmd` | copied verbatim from scratch | 4 KB | the existing event-to-object Mermaid slice for round 14 |
| `src/autofde_lab/sa2a/case_studies/manufacturing/fixtures/round14_ocel_slice.json` | **new** — hand-extracted slice: every OCEL event/object/relationship touching `round_index == 14` only, sliced from a fresh `runtime.run(seed=1)` re-run at migration time, written via `ocel_adapter.write_json` on a log rebuilt from just that round's events/objects | a few KB (bounded: 4 resources × 1 round of events/objects, not 200 rounds) | the "small representative OCEL JSON slice" the task asks for — committed because it is small and because it is what `round14.mmd`/`round14_e2o.mmd` were rendered from, so keeping the JSON slice next to its own Mermaid rendering lets a reader check the diagram against real data without regenerating anything |

The full 1.9 MB per-seed logs remain only in
`.claude/scratch/sa2a-mfg-01/episode_seed{1,2,3}.ocel.json` (untracked,
per this session's git status) as the historical record of the original
independent build, and are not referenced by anything under `src/` or
`tests/` after migration — the test suite (§4) regenerates equivalent logs
fresh, in-memory, every run.

---

## 4. Chicago-style pytest suite — exact path and test names

**Path**: `tests/sa2a/case_studies/test_manufacturing_baseline_chicago.py`

(New directory `tests/sa2a/case_studies/` with an `__init__.py`, matching
the existing `tests/sa2a/{composition,episode,experience,release}/`
subdirectory convention already used in this test tree — confirmed by
listing `tests/sa2a/`.)

No mocking anywhere in this file — it exercises the real
`autofde_lab.sa2a.case_studies.manufacturing.runtime.run` function, the real
`OcelLog` it produces via `ocel_adapter`, and asserts on real parsed JSON
state, never on the runtime's own internal counters (`RunResult`'s
`round_summaries`/`final_plant_state` are read only to compare against the
independently re-derived values, never trusted alone) — satisfying both the
global and repo `testing-chicago-style.md` rules.

```python
"""Chicago-style baseline evidence tests for the sa2a manufacturing case study.

MFG-01A acceptance: re-derive every invariant claim from the real OCEL 2.0
JSON the real runtime produces -- never from runtime.py's own in-memory
counters -- and confirm byte-for-byte replay determinism. See
src/autofde_lab/sa2a/case_studies/manufacturing/MIGRATION_PLAN.md and
CONTRACT.md for what this package is and is not (paper-fixture baseline
only; no generator, no HDDL/POWL/FOND, no frontier falsifier yet).
"""
```

Test functions (module-level, real `pytest` functions — no test class
needed, matching several existing `tests/sa2a/*_chicago.py` files' own
style):

1. `test_runtime_run_executes_and_produces_valid_ocel_log()` —
   runs `runtime.run(seed=1)` once for real, asserts `stop_reason` is one
   of `{"stable", "max_rounds"}`, `rounds_executed >= 1`, and that
   `ocel_adapter.OcelLog.validate()`-equivalent structural validity holds
   by independently re-parsing the JSON `to_ocel2_json()` output the run
   returns (via its `ocel_log_digest`-bearing log) with the stdlib `json`
   module and asserting the top-level OCEL 2.0 keys (`objectTypes`,
   `eventTypes`, `objects`, `events`) are present and non-empty.

2. `test_zero_unreceipted_actuation_from_real_ocel_json()` — runs the real
   simulation for `seed=1`, writes its log to a real temp file via
   `ocel_adapter.write_json`, re-opens and re-parses that file with plain
   `json.load` (independent of any in-memory object the runtime built),
   and asserts: **every** event of type `sosa:Actuation` in the parsed
   JSON has exactly one `prov:generated` relationship to an object that
   exists in the parsed `objects` list with `type == "Receipt"`, and that
   receipt's `applied` attribute matches the event's own `applied`
   attribute — reproducing `verifier.py`'s invariant 1 as an independent
   from-scratch JSON walk, not a call into `verifier.py` itself (both are
   valuable; this test is the one that must never trust any Python object
   the run produced beyond the written file).

3. `test_zero_authority_violations_from_real_ocel_json()` — same
   re-parse-from-disk discipline; walks every `odrl:Permission` /
   `odrl:Prohibition` event per round in emission order, independently
   recomputes the running `remaining_budget_kwh` chain from the parsed
   `granted_energy_kwh` attributes, and asserts it is never negative and
   that no `admitted` grant exceeds
   `AUTHORITY_MAX_SHARE_OF_REMAINING_BUDGET * remaining_before` (the
   constant imported from the real
   `autofde_lab.sa2a.case_studies.manufacturing.authority_agent` module,
   never hand-retyped in the test).

4. `test_energy_budget_never_exceeded_per_round()` — independently sums
   `granted_energy_kwh` across every `odrl:Permission` event within each
   `round_index`, parsed from the same on-disk JSON, and asserts the sum is
   `<= ENERGY_BUDGET_PER_ROUND_KWH` (imported constant, `450.0`) for every
   round present in the log — the exact "energy<=450/round" acceptance
   criterion from the task, checked from durable JSON, not from
   `AuthorityAgent`'s live `remaining` variable.

5. `test_replay_is_byte_for_byte_deterministic_for_same_seed()` — runs
   `runtime.run(seed=7)` twice, independently, in the same test (two
   separate fresh `LogRef`/agent/authority/actuator object graphs — no
   object reused across the two runs), writes both resulting logs to two
   separate real temp files via `ocel_adapter.write_json`, and asserts the
   two files' raw byte contents (`Path.read_bytes()`) are **exactly
   equal** — the literal "byte-for-byte replay determinism" claim, checked
   as bytes on disk, not as digest equality alone (though it also asserts
   `ocel_log_digest` equality between the two `RunResult`s as a second,
   cheaper corroborating check).

6. `test_different_seeds_produce_different_traces()` — a deliberate
   falsifier-style negative check: runs `seed=1` and `seed=2`, asserts
   their `ocel_log_digest` values differ and their byte-written JSON files
   differ — guards against a degenerate implementation that ignores the
   seed and would otherwise pass test 5 vacuously (e.g. an implementation
   that always emits the same log regardless of seed would still pass a
   same-seed-replay check; this test specifically rules that out).

7. `test_fixture_round14_slice_matches_a_fresh_run()` (fixture-integrity
   check) — runs `runtime.run(seed=1)`, slices round 14 out of the fresh
   log the same way `fixtures/round14_ocel_slice.json` (§3) was produced,
   and asserts the freshly-sliced round-14 event/object set is consistent
   in shape (same event types, same object types, same count) with the
   committed fixture — catching drift between the committed fixture and
   the live code, per `.claude/rules/no-dual-bookkeeping.md`'s "the graph
   is right by construction" principle applied to a committed slice.

All seven tests are real end-to-end executions of the actual package code
(`autofde_lab.sa2a.case_studies.manufacturing.runtime.run`); none imports
`unittest.mock`. Verification command, to be run for real once the files
above exist (not run by this planning step, since this step does not yet
create the files):

```bash
grep -rn "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" tests/sa2a/case_studies/test_manufacturing_baseline_chicago.py
.venv/bin/python -m pytest tests/sa2a/case_studies/test_manufacturing_baseline_chicago.py -v
```

---

## 5. `docs/STATUS.md` entry text (new dated pass section)

To be inserted at the top of `docs/STATUS.md`, immediately after the file's
existing header paragraph and before the current "Last update: **pass 43**"
entry, following the exact format that entry uses (bold pass number + date +
title line, then prose paragraphs, ending with a standing table where this
repo's convention calls for one). Text as it will be written (not yet
written to `docs/STATUS.md` by this planning step):

```markdown
Last update: **pass 44** (2026-09-18) — **MFG-01A: sa2a manufacturing case
study admitted into the repo as a committed baseline (PARTIAL_ALIVE).**
Migrates the independently-written sa2a-mfg-01 scratch prototype (six
Python modules — `ocel_adapter.py`, `resource_agent.py`,
`authority_agent.py`, `actuator.py`, `verifier.py`, `runtime.py`, plus
`CONTRACT.md` — previously at `.claude/scratch/sa2a-mfg-01/`, untracked)
into a permanent package at
`src/autofde_lab/sa2a/case_studies/manufacturing/`. This is phase MFG-01A of
a four-phase roadmap (MFG-01A baseline → MFG-01B generative worlds
`G(seed, θ) → W` → MFG-01C generated HDDL/POWL/FOND closure → MFG-01D
frontier falsification); **only MFG-01A is claimed here.** The migration is
import-path fixes only — every domain constant, decision rule, hashing
rule, and clock rule is byte-identical to the scratch version, so the
existing evidence (a real 200-round-bounded seeded multi-agent simulation
over a fixed 4-machine M1-M4 plant, real OCEL 2.0 output via
`autofde_lab.ocel.log.OcelLog`, confirmed byte-for-byte replay determinism
for a fixed seed, three invariants independently re-derived from durable
OCEL JSON rather than trusted from runtime state) is preserved exactly, not
improved. New Chicago-style test suite,
`tests/sa2a/case_studies/test_manufacturing_baseline_chicago.py` (7 tests,
zero mocking — `grep` confirmed), re-derives zero-unreceipted-actuation,
zero-authority-closure-violations, and energy<=450kWh/round independently
from freshly-written, freshly-re-parsed OCEL JSON on disk, and asserts
replay determinism as byte-equal files, not digest-only. Compact fixture
(`fixtures/round14.mmd`, `fixtures/round14_e2o.mmd`, a new small
round-14-only OCEL JSON slice) is committed; the three full 1.8 MB
per-seed logs are **not** committed — they are regenerable on demand by
the test suite, so committing them would be exactly the
dual-bookkeeping/drift risk `.claude/rules/no-dual-bookkeeping.md` warns
against for derived artifacts.

**Standing, by dimension (`.claude/rules/standing-law.md`):**

| Claim | Standing | Evidence |
|---|---|---|
| Observed multi-agent execution (real, non-hardcoded seeded trajectories) | ALIVE | `runtime.run(seed=...)` executed this session against the real `autofde_lab.ocel.log.OcelLog` |
| Real OCEL 2.0 output | ALIVE | `ocel_adapter.write_json` output re-parsed independently by the new test suite |
| Replay determinism | ALIVE | byte-for-byte file comparison across two independent runs of the same seed, this session |
| BRCE-adjacent invariants (zero unreceipted actuation, authority closure, energy budget) | ALIVE | re-derived from parsed JSON, not from runtime counters, this session |
| Generative world model `G(seed, θ) → W` beyond the fixed M1-M4 plant | UNSUPPORTED — not yet attempted (MFG-01B) | no code exists; not silently implied by this package's docstrings |
| Generated HDDL/POWL/FOND projection from an admitted world model | UNSUPPORTED — not yet attempted (MFG-01C) | no code exists |
| Frontier falsifier / UNKNOWN→KNOWN retirement loop | UNSUPPORTED — not yet attempted (MFG-01D) | no code exists |
| `organizationalStanding` / `enterpriseStanding` | UNKNOWN | no accountable customer acceptance; not computed by anything in this repo per `.claude/rules/standing-law.md` |

Nothing pushed, no PR opened, no tag created — this pass is local-checkout
only, per the actuation boundary.
```

---

## 6. Ordering and falsifier for this phase alone

Per the task's own dependency law (`Baseline → Generator → FormalClosure →
Falsifier`, not the reverse), this plan is scoped **only** to the Baseline
step. Its own falsifier, restated concretely: after §1-§4 are executed for
real, deleting `.claude/scratch/sa2a-mfg-01/` entirely and re-running the new
`tests/sa2a/case_studies/test_manufacturing_baseline_chicago.py` suite from
a clean checkout must still pass — i.e. the permanent package must not
secretly depend on anything left behind in the scratch directory (no
leftover `sys.path` hack, no import of a scratch-relative path). This
falsifier is not run by this planning step; it is the acceptance check for
whoever executes this plan.

## See also

- `CONTRACT.md` (this package, once migrated) — the binding interface
  contract these six modules independently satisfy.
- `.claude/rules/standing-law.md`, `.claude/rules/no-dual-bookkeeping.md`,
  `.claude/rules/absence-is-not-evidence.md`,
  `.claude/rules/level4-completion-law.md` — the four always-in-force
  evidence rules this plan and its docstrings are written against.
- `.claude/rules/testing-chicago-style.md` — the no-mocking discipline
  §4's test suite is designed to satisfy.
- `docs/STATUS.md` — where §5's entry lands once this plan is executed.
