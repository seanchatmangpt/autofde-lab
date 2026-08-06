# scikit-decide

AI framework for Reinforcement Learning, Automated Planning, and Scheduling.
Originally developed by Airbus AI Research. Within the Chatman Ecosystem
portfolio (`FORWARD_DEPLOYMENT.md`), this repository is the canonical
decision, planning, and integration control plane: the lawful selection
surface between admitted operational state and candidate plans. It does not
carry ambient authority to actuate external systems — actuation runs through
OpenClaw (see §4), never through BRCE, which belongs to other systems in the
portfolio and has no role here.

Repository: https://github.com/airbus/scikit-decide | Docs:
https://airbus.github.io/scikit-decide/

## 1. Standing law

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

## 2. Explore register — nano-nonfiction dispatch

Default reasoning mode for investigating a transition, a template, a fixture,
or an OpenClaw boundary is **Explore**: trace where the current design
actually leads before declaring it wrong. Switch to **Exploit** only to
assert current truth about repo state, or when a premise's own internal
parts contradict each other — never because the premise contradicts some
external expectation.

Any Explore-phase report to the user takes the **nano-nonfiction dispatch**
shape already in production use in this repo (see the OpenClaw interop
receipts in PR #8/#9/#10 history for the reference instance):

```text
Standing            — one line, scoped per boundary (§1 vocabulary)
Identity            — repo, branch, base, head, commit count, drift
What changed        — files touched, surfaces added, in plain terms
Admission & bounds  — what's admitted, what's refused, execution limits
Local execution     — command / exit code / observation, one row each
Standing by boundary— ALIVE / PARTIAL_ALIVE / UNKNOWN, broken out
Falsifiers          — named conditions that would overturn this standing
```

Bounded length. Every line is either a command actually run this session
with output observed, or a precisely named blocker — never a self-graded
claim, never hype framing, never a capability survey when a run was asked
for. This is the same discipline as `~/.claude/rules/no-overclaiming-conversational.md`
and `criticism-discipline.md` rules 1–4, restated in this repo's own
vocabulary: don't dismiss an existing mixin/domain/solver design without
checking its actual tests first; a status claim earns a run, not a survey.

## 3. Actuation boundary

Local edits, tests, and notebook runs are Explore-territory — no
confirmation needed. These require it:

- `git push` to a shared branch, opening/merging a PR, a PyPI/conda release,
  docs deploy, or triggering a long CI job.
- Anything that runs through the **OpenClaw bridge** (`integrations/openclaw/`,
  `src/skdecide/openclaw_runtime.py`, `src/skdecide/openclaw_bridge.py`):
  the bridge only admits names already present in scikit-decide's own
  `skdecide.domains` / `skdecide.solvers` entry-point registries, enforces
  bounded execution (episode/step/timeout/output-size caps, subprocess
  isolation), returns typed refusals for anything outside those bounds, and
  emits a SHA-256 receipt for every success, refusal, and failure. A merged
  PR adding OpenClaw surface is `IMPLEMENTATION_ALIVE` at most — the
  exact-host crown (`openclaw plugins install/enable`, `gateway restart`,
  `plugins inspect --runtime`, `mcp doctor --probe`) is a separate,
  unmerged-until-executed boundary. Queued or pending CI is not evidence
  either way.

A planner result is a candidate, not an actuation. `docs/agentic-fabric.md`'s
CLI/MCP/A2A layer calls the existing domain/solver registry; it does not
grant it new authority.

## 4. Architecture — retrieve from source, not from memory

This section is deliberately thin. Treat it as an index into where to look,
not a description to reason from — the source is the witness, this file
drifts.

**Core design**: domains and solvers compose orthogonal builder mixins
(`src/skdecide/builders/domain/`, `src/skdecide/builders/solver/`), one
single-inheritance chain per dimension (agent, concurrency, dynamics,
events, memory, observability, value, initialization). Presets in
`src/skdecide/domains.py` (`Domain`, `RLDomain`, `MDPDomain`,
`GoalMDPDomain`, `DeterministicPlanningDomain`, `POMDPDomain`, ...).

**Three-tier method naming** — read the actual class before assuming a
signature:

```
domain.get_X()    # public API — autocast wrapper, user calls this
domain._get_X()   # LRU-cached middle layer
domain._get_X_()  # override point — implement here
```

`step()`/`reset()` follow the same shape via `_state_step()`/`_state_reset()`.

**Source layout**:

```
src/skdecide/
├── core.py, domains.py, solvers.py, utils.py
├── builders/domain/, builders/solver/   # capability mixins
└── hub/domain/, hub/solver/, hub/space/gym/

cpp/            # C++20 performance solvers — pybind11 wrapper per solver
tests/          # pytest — autocast/, domains/, solvers/, scheduling/, fabric/
notebooks/      # nbmake-tested tutorials
examples/       # 153 example scripts
integrations/openclaw/   # plugin + skill + MCP bridge — see §3
docs/           # explanation and projections; never a standing/authority source
```

**Adding a domain/solver** — nearest working example first
(`src/skdecide/hub/domain/maze/` for domains, any pure-Python solver under
`src/skdecide/hub/solver/` for solvers); close the loop with a fixture +
Chicago-style test in the same change, not a follow-up. C++ solvers follow
one shared architecture (template header, impl, pybind wrapper, `.cc.in`,
`CMakeLists.txt`) — read a sibling solver (A* for simple, MCTS for complex)
rather than re-deriving the pattern here.

**Build**: `uv sync --extra=all -v`; `uv run pytest tests`;
`uv run pytest --nbmake notebooks -v`; `pre-commit run --all-files`. Python
3.10+ (3.12 recommended), CMake/C++20/pybind11 for the compiled extension.

## See also

- `FORWARD_DEPLOYMENT.md` — this repo's role in the Chatman Ecosystem
  portfolio; the `A = μ(O*)`, `R = receipt(A)` law this file's §1–§3
  instantiate locally.
- `docs/agentic-fabric.md` — the CLI/MCP/A2A/DSPy layer over the domain/solver
  registry.
- `docs/STATUS.md` — the live worked example of the §1/§2 ledger discipline.
- `integrations/openclaw/` — the actuation bridge referenced in §3.
- `docs/` (general) — explanation and projections; not an authority for
  standing/proof claims.
- `~/CLAUDE.md`, `~/.claude/CLAUDE.md`, `~/.claude/rules/*.md` — personal/
  global tool defaults and discipline files this repo's §1–§2 restate
  locally.
