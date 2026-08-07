# scikit-decide

AI framework for Reinforcement Learning, Automated Planning, and Scheduling.
Originally developed by Airbus AI Research. Within the Chatman Ecosystem
portfolio (`FORWARD_DEPLOYMENT.md`) — the "Forward Deployment OS," whose
canonical portfolio narrative lives in `seanchatmangpt/chatman-ecosystem` —
this repository is the foundation layer: the canonical decision, planning,
and integration control plane, the lawful selection surface between admitted
operational state and candidate plans.

**It computes candidate plans. It does not actuate.** A planner selects; a
broker authorizes; an executor performs; a verifier evaluates. Nothing here
carries ambient authority to change the world, and nothing here should be
given receipt, admission, or actuation semantics. Actuation runs through
OpenClaw, never through BRCE (which belongs to other systems in the
portfolio and has no role here).

Repository: https://github.com/airbus/scikit-decide | Docs:
https://airbus.github.io/scikit-decide/

## Always in force

@.claude/rules/standing-law.md

That file is imported, not merely referenced, because every status claim in
every session needs it.

Everything below is **path-gated**, not imported. Each `.claude/rules/*.md`
carries YAML `paths:` front-matter and loads only when a matching file is
read. This distinction is load-bearing and was got wrong once: an `@` import
is expanded into `CLAUDE.md` at session start, so splitting a long file into
six imports reorganises text without reducing anything. A rules file with no
`paths:` gate also loads unconditionally. The table below is a routing hint
for a human reader; the gates are what actually control loading.

## Working across the ecosystem

Cross-repo claims require the sibling repos' own doctrine, not just their
code. `--add-dir` grants file access but **not** instruction loading — that
needs an environment variable:

```bash
CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1 claude \
  --add-dir ~/mfw --add-dir ~/bcinr --add-dir ~/praxis \
  --add-dir ~/ggen --add-dir ~/ggen-create --add-dir ~/ggen-legacy \
  --add-dir ~/wasm4pm --add-dir ~/wasm4pm-compat
```

Without it, you read sibling code with none of its rules — the exact
condition that produced a false ecosystem-wide claim from a search that had
never looked at `~/bcinr`. Verify with `/memory` and `/context`, don't assume.

## Look this up when you are doing that

| When you are… | Read |
|---|---|
| reporting status, or writing any Explore-phase report to the user | `.claude/rules/explore-register.md` |
| about to `git push`, open/merge a PR, release, deploy docs, trigger long CI, or call the OpenClaw bridge | `.claude/rules/actuation-boundary.md` |
| adding or modifying a domain, solver, or C++ hub solver; or looking for where anything lives | `.claude/rules/architecture.md` |
| making any claim that spans `~/mfw`, `~/ggen`, `~/ggen-create`, `~/ggen-legacy`, or `~/bcinr` | `.claude/rules/ecosystem-boundary.md` **and** `docs/ecosystem-standing.md` |
| touching `fabric/pddl_engine.py`, `fabric/powl.py`, PDDL requirements, or the capability ontology | `.claude/rules/ecosystem-boundary.md` |
| reaching for a project skill or agent instead of re-deriving a workflow | `.claude/rules/project-tooling.md` |
| filing what you just did into the in-repo ledger | `docs/STATUS.md` |

## Four rules that do not fit in a table

These are the ones most likely to be violated by someone who read only this
page, so they stay inline.

1. **A solver/domain claim is `ALIVE` only with a Chicago-style test
   exercising `solve()` on a real domain, run this session.** Never
   "compiles," never "the happy path works." Queued CI, a merged PR, and a
   green synthetic check are not evidence — only an executed job against the
   exact commit is.

2. **Projection is not execution.** `fabric/powl.py` writes
   `plan.powl.ttl`; that manufactures a document, it does not run a
   workflow. An earlier pass in this repo let the projector stand in for an
   executor and had to be retracted. As of 2026-08-06 no component in the
   portfolio executes a POWL plan end to end — see `docs/ecosystem-standing.md`.

3. **Never remove the PDDL requirements gate in `fabric/pddl_engine.py`.**
   The C++ backend parses `:derived-predicates`, `:constraints` and
   `:preferences` and implements none of them, silently — so planning would
   return a confident, plausible, *wrong* plan. A wrong plan that can be
   admitted downstream is strictly worse than a refusal.

4. **Capability claims must be ontology-backed.**
   `ontology/skdecide-capabilities.ttl` is generated
   (`python -m autofde_lab.fabric.ontology ontology/skdecide-capabilities.ttl`) —
   regenerate it, never hand-edit, and note that `tests/ecosystem/` fails if
   it drifts from the registry. This is an epistemic control, not
   documentation: a false ecosystem claim was made in this repo's history
   from a search that had simply never looked at one of the repositories.

## Build

`uv sync --extra=all -v`; `uv run pytest tests`;
`uv run pytest --nbmake notebooks -v`; `pre-commit run --all-files`.
Python 3.10+ per `pyproject.toml`; the verified working dev environment is
3.13.9 — treat 3.13 as current, not merely supported. CMake/C++20/pybind11
for the compiled extension.

Whole-suite collection is currently `BUILD_BROKEN` — run new suites by path.
Details and the exact failing files are in `.claude/rules/standing-law.md`.

## See also

- `docs/ecosystem-standing.md` — cross-repository standing ledger: per-stage
  `ALIVE`/`BLOCKED`/`UNSUPPORTED`, the per-transition proof that nothing
  executes a POWL plan, and repair plans RP-1…RP-7. Read before making any
  cross-repo claim.
- `docs/STATUS.md` — the in-repo WIP ledger and the worked example of the
  measured-win / recorded-negative discipline.
- `FORWARD_DEPLOYMENT.md` — this repo's role in the portfolio; the
  `A = μ(O*)`, `R = receipt(A)` law the rules files instantiate locally.
- `docs/agentic-fabric.md` — full design of the CLI/MCP/A2A/DSPy layer.
- `docs/chatman-ecosystem-wasm.md` — the WASM adapter surface, using an
  `ALIVE`/`REFUSED`/`BUILD_BROKEN` vocabulary that explicitly rejects
  `BLOCKED` — narrower than the standing law here; don't conflate them.
- `docs/guide/chatman-clean-session.md` — `ChatmanCleanSessionDomain`;
  documents BRCE as the portfolio's actuation DO-boundary, not this repo's.
- `docs/` (general) — explanation and projections; never an authority for
  standing or proof claims.
- `~/CLAUDE.md`, `~/.claude/CLAUDE.md`, `~/.claude/rules/*.md` — personal and
  global defaults that `.claude/rules/` restates in this repo's vocabulary.
