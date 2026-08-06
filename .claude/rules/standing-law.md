# Standing law — the vocabulary every claim must carry

Every claim about this repo's state gets one of these, **scoped per
boundary** — a change is rarely one status end to end:

- `ALIVE` — the declared consequence works and the required evidence (a
  command actually run this session, output observed) is present.
- `PARTIAL_ALIVE` — a bounded working checkpoint exists but the larger claim
  does not follow from it yet.
- `BLOCKED:<reason>` — a named external prerequisite prevents lawful
  progress (e.g. `BLOCKED:UPSTREAM_ACTIONS_OUTAGE`). Name the exact blocker,
  not "blocked."
- `BUILD_BROKEN` — the relevant build or test suite fails.
- `UNKNOWN` — observation is insufficient to classify standing. Not the same
  as `UNSUPPORTED`.
- `UNSUPPORTED` — the required capability or dependency is absent
  (environment gate, missing optional extra), not incomplete work.

A solver/domain claim is `ALIVE` only with a Chicago-style test exercising
`solve()` on a real domain, run this session — never "compiles" or "the
happy path works." Queued CI, a merged PR, or a green synthetic check are not
evidence; only an executed job against the exact commit is. See
`docs/STATUS.md` for the working ledger convention this maps to: **measured
win** (command run, output quoted, passed), **recorded negative** (attempted,
genuinely blocked, blocker named precisely), **deferred/scoped** (a plan
exists, nothing under it executed yet — treat every line as unverified until
it appears in a ledger with a witness).

### Known standing exception (recorded, not silently omitted)

`uv run pytest tests --collect-only -q` currently fails collection outright
(`BUILD_BROKEN` by this section's own vocabulary) — confirmed this session,
re-verified before writing this line:

- `tests/solvers/python/test_pomcp.py` collides on basename with
  `tests/solvers/cpp/test_pomcp.py` (no package markers to disambiguate).
- `tests/test_self_play_dspy_advanced_planning_chicago.py`,
  `_all_domains_chicago.py`, `_turbofieldfare_chicago.py` — all three fail to
  import. These are the exact Chicago-test files `docs/STATUS.md`'s "close
  WIP with Chicago-style tests" pass references; they don't import cleanly,
  which is worth surfacing precisely so the pass isn't read as "Chicago-test
  infra is healthy across the board."

Don't claim green collection without re-running the command above and
checking the file list still matches.

**Re-verified 2026-08-06** — still exactly these four errors, same files. The
new suites added since (`tests/ecosystem/`,
`tests/domains/python/test_career_admission_unit.py`) collect and pass
independently; run them by path rather than relying on a whole-suite
collection that is still `BUILD_BROKEN`.

## See also

- `CLAUDE.md` — the index; this file is `@`-imported there because every
  session needs it.
- `docs/STATUS.md` — the in-repo ledger applying this vocabulary.
- `docs/ecosystem-standing.md` — the cross-repo ledger applying it wider.
