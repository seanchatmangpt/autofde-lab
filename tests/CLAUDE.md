# Role

The evidence layer. A status claim about this repo is only as strong as the test that was
actually executed for it — `.claude/rules/standing-law.md` requires a run, not a survey.

# Authority

- Establish `ALIVE` / `PARTIAL_ALIVE` / `BUILD_BROKEN` for repo-local behaviour, when executed
  this session with output observed.
- Record negatives: a test that names its exact blocker is evidence, and a deliberately red
  test is a legitimate artifact.

# Non-authority

- A green test here says nothing about cross-repository consequence. That is
  `tests/ecosystem/` and `docs/ecosystem-standing.md`.
- Queued CI, a merged PR, and a green synthetic check are not evidence. Only an executed job
  against the exact commit is.

# Inputs

The package under `src/autofde_lab/`, compiled hub `.so`, PDDL/RDDL corpora under
`tests/domains/python/pddl_domains/`, optional extras.

# Outputs

Pass/fail with named blockers; the witnesses quoted into `docs/STATUS.md`.

# Invariants

**Test taxonomy — strictly ordered, never conflated:**

| Level | Drives | Establishes |
|---|---|---|
| unit checkpoint | one implementation property, in isolation | that property |
| integration checkpoint | bounded set of real components | their composition |
| Chicago test | the real system for its scope, real consequence observed | the scoped behaviour |
| crown | the whole causal chain, independent evidence | end-to-end closure |

1. **No test may carry "chicago" in its name unless it exercises the real components for its
   scope.** The worked example: `tests/domains/python/test_career_admission_unit.py` was
   `test_career_admission_chicago.py`; it exercised one solver against one in-repo domain and
   touched no sibling repo, so it was renamed and given an explicit scope warning. The test was
   fine; citing it as ecosystem evidence was the error.
2. A domain/solver claim is `ALIVE` only with a test constructing a real domain and running
   `solve()`, executed this session.
3. Skips gated on missing extras (`z3-solver`, `optuna`, `plado`, Node.js, macOS `libomp`
   segfault) are environment gates — `UNSUPPORTED`, not incomplete work.
4. **Whole-suite collection is `BUILD_BROKEN`. Run by path.** Four files error at collection,
   re-verified 2026-08-06:
   - `tests/solvers/python/test_pomcp.py` collides on basename with
     `tests/solvers/cpp/test_pomcp.py` (no package markers to disambiguate);
   - `test_self_play_dspy_advanced_planning_chicago.py`,
     `test_self_play_dspy_all_domains_chicago.py`,
     `test_self_play_dspy_turbofieldfare_chicago.py` all fail to import.
   Do not report "Chicago-test infra is healthy" — three of them do not import.

# Neighboring components

`autocast/`, `domains/`, `solvers/{python,cpp}/`, `fabric/`, `scheduling/`,
`flight_planning/`, `ecosystem/` (see `ecosystem/CLAUDE.md`), `conftest.py`;
`.claude/skills/chicago-domain-solver`.

# Verification

```bash
uv run pytest tests/domains tests/fabric tests/ecosystem -v        # by path
uv run pytest tests --collect-only -q                              # expect the 4 errors above
```

# Standing ceiling

Strongest establishable claim from this directory alone: **`ALIVE` for a named repo-local
behaviour, at this commit, in this environment, with the command and output quoted.**

Not establishable here: cross-repo closure; that CI would agree (the suite does not collect
whole); that a passing unit checkpoint upgrades to a Chicago claim by renaming it. Absence of a
failing test is not evidence of correctness — an untested path is `UNKNOWN`.

# Update obligations

- Adding a domain/solver → add the fixture + test in the same change, not a follow-up.
- Renaming a test across taxonomy levels → state the demotion/promotion reason in the file's
  docstring and ledger it in `docs/STATUS.md`.
- Fixing or worsening whole-suite collection → update invariant 4 here **and**
  `.claude/rules/standing-law.md`, which restates it (crown-level; it must not live only here).
