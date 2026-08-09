# Lane C — a real, non-LLM planner-driven attempt against sregym

**Status at time of writing: build complete, real live trial in flight.** This document
covers the investigation and design; the trial's real terminal result is appended once it
lands (see "Real trial result" below — filled in after the run completes, never
pre-written).

## Why this exists

Direct instruction this session, mid-investigation of the `stratus`/LiteLLM tool-calling
crash (`docs/2026-08-09-sregym-stratus-llm-attempt-terminal-result.md`): "you should not
default to LLM always. use all the planning available." This repo's own `fabric catalog`
(run live this session) already registers real, non-LLM planners (`Astar`, `BFWS`, `IW`,
`RIW`, `MCTS`, `POMCP`) and a bounded-structured solver (`DSPyPolicy`) — none of them had
ever been pointed at a real external benchmark task.

## Investigation, real and cited (4 parallel Explore agents, this session)

1. **sregym's real MCP tool server** (`vendor/gyms/sregym/mcp_server/*.py`) is a genuine
   SSE-over-HTTP server; every tool implementation (`get_traces`, `get_services`,
   `get_metrics`, `exec_kubectl_cmd_safely`, `submit`, ...) is a plain, LLM-free Python
   function — zero `litellm`/LLM code in any server-side implementation, confirmed by direct
   grep. `exec_kubectl_cmd_safely` is real (AST-parsed via `bashlex`, single-command-only,
   no pipes/redirects) with an optional whitelist gate that is **off** in the real deployed
   config.
2. **sregym's fault-type space**: 60 real `recover_<fault_type>` methods across 10 injector
   classes; 123 real registered `problem_id`s (this repo's own prior "~90/~34-Ported" figures
   were undercounts, corrected here). Mitigation grading is **mechanical/LLM-free for all
   123** active problems (`kubectl`/Prometheus state comparison). Diagnosis grading is
   **LLM-judged free text for 96/97** active diagnosis-graded problems
   (`LLMAsAJudgeOracle`) — the fault itself is mechanically detectable (deterministic image-
   string/status-reason signals), but the *scoring* of the diagnosis submission is not.
3. **`DSPyPolicy`** (`src/autofde_lab/hub/solver/dspy_policy/dspy_policy.py`) is already
   wired to the same local server (`default_lm()`, line 56-62) and is architecturally immune
   to the crash that killed `stratus`: it drives the model via `dspy.Predict` over a typed
   `dspy.Signature` (DSPy's own text-completion/structured-parsing layer), never OpenAI-
   native `tool_calls`/`bind_tools`. Not used in this build (see "Scope" below) but confirmed
   as a real, available escalation path if a future sregym problem's decision complexity
   ever warrants search/generation rather than a closed-form rule.
4. **`k8s_goat_rbac_escalation`** (this repo's own in-repo gym) is confirmed synthetic
   (in-memory, no live cluster), Astar-solved (real, re-run this session, 1 passed in
   0.20s) — real evidence planning works on this problem *shape* in principle, not evidence
   against a live cluster. `GymProcedureDomain` is the real, reusable Recipe-based pattern
   all 5 existing gym domains converged on.

## Design: what was actually built

`vendor/gyms/sregym/clients/autofde_lab_planner/driver.py` (committed locally within the
submodule, never pushed to `origin/SREGym-SREGym`) — a new sregym agent, registered in
`agents.yaml` as `autofde_lab_planner` (`container_isolation: false`, matching the vendored
`tierzero` agent's precedent, no container image build needed).

**It makes zero LLM calls.** The `misconfig_app` fault class has a closed-form correct
answer — one deployment's running image diverges from its own app's canonical baseline — so
it is solved by a real, typed, observation-driven decision procedure, not by LLM generation:

- **Diagnosis stage** (read-only, matching `diagnosis_agent_config.yaml`'s own
  `exec_read_only_kubectl_cmd` tool restriction): lists the real, live hotel-reservation
  deployments (`kubectl get deployments`), observes each one's real running image, and
  mechanically flags whichever diverge from
  `sregym.service.apps.hotel_reservation.HOTEL_RESERVATION_APPLICATION_IMAGE` (the app's own
  canonical config). Submits a diagnosis built only from those observations.
- **Mitigation stage** (matching `mitigation_agent_config.yaml`'s mutating
  `exec_kubectl_cmd_safely`): for each mismatched deployment, observes its real container
  name and executes `kubectl set image deployment/<name> <container>=<canonical> -n
  hotel-reservation`, then submits.

**Integrity constraint, load-bearing and checked by `tests/sota/
test_sregym_autofde_planner_decision_chicago.py`**: this driver never reads any
fault-injector's precomputed fault target (`inject_app.py`'s `service` parameter) or any
oracle's precomputed answer (`root_cause`, `expect()`, `actual_images`). Every decision comes
only from tool calls a real competing agent could make — the real, live deployment list, each
deployment's real running image, and the app's own *public* canonical baseline. Concretely
this means the driver never hardcodes "geo" as the affected service (even though this
session's own earlier debugging incidentally observed that fact in a log) — it scans **every**
real hotel-reservation deployment and lets the real, live evidence decide. This generalizes,
unmodified, to all 4 sregym problems sharing this exact oracle class (`misconfig_app`,
`incorrect_image`, `faulty_image_correlated`, `update_incompatible_correlated`), not just
`misconfig_app_hotel_res`.

Real conductor-orchestration mechanics (agent registry via `agents.yaml`, the `/get_app`,
`/status`, `/submit` HTTP surface, the kubectl/submit MCP tool SSE endpoints) were read
directly from `main.py`, `sregym/conductor/conductor_api.py`, and the real precedent drivers
`clients/autosubmit/autosubmit_agent.py` (simplest real example) and `clients/demo/driver.py`
(real MCP SSE call pattern) — not guessed.

## Verified this session, before the live trial

- `tests/sota/test_sregym_autofde_planner_decision_chicago.py`: **10/10 passing** under
  `vendor/gyms/sregym/.venv/bin/python` (the real runtime this driver actually executes
  under); **9/10 passing + 1 typed `UNSUPPORTED` skip** under this repo's own `.venv` (one
  test needs the real `kubernetes` package, which lives only in sregym's own venv — named
  precisely, not silently xfailed). Zero mocks.
- The judge preflight/grading call path (`run_judge_preflight_check()`,
  `DiagnosisJudge.judge_detailed()`) was confirmed, by direct source read, to call
  `.inference(messages)` with **no `tools=` argument** — meaning it never reaches
  `ChatLiteLLM.bind_tools(...)`, the exact code path that crashed for `stratus`. This is why
  diagnosis grading is expected to work against the local server even though `stratus`'s
  tool-calling agent loop did not.
- Both the kind cluster (4 nodes, all `Ready`) and the real `mcp-server` pod in the `sregym`
  namespace survived the earlier crash's teardown — only the `hotel-reservation`/`observe`
  app namespaces needed redeployment, which `main.py`'s own driver does automatically on
  launch.

## Scope — what this explicitly does not do yet

- No search-based planner (`Astar`/`BFWS`/`DSPyPolicy`) is actually invoked. This task's
  decision complexity is a single closed-form rule, not a search problem — reaching for
  search machinery here would be an unsupported abstraction, contradicting this session's own
  "extract existing choices before inventing new choices" discipline. `DSPyPolicy` remains
  the real, available escalation path (item 3 above) for a future sregym problem whose
  decision complexity actually warrants it.
- Diagnosis text is optimized to be honest and evidence-grounded, not to game the LLM judge's
  scoring checklist — no attempt was made to reverse-engineer what phrasing the judge scores
  highest.

## See also

- `docs/2026-08-09-sregym-stratus-llm-attempt-terminal-result.md` — the LLM-driven attempt
  this pivot replaces for the decision-making role (the judge LLM call is still used, for
  grading only, per the analysis above).
- `docs/2026-08-08-decision-basis-lane-b.md` — the `DecisionBasis` vocabulary this new
  `Planner` point (`sregym:autofde_lab_planner`, non-LLM) will attach to.
- `.claude/rules/absence-is-not-evidence.md` / `no-dual-bookkeeping.md` — the integrity
  disciplines this driver's "never read the answer key" constraint instantiates.

## Real trial result

**Run 1** (`results/0809_0123/`): real, honest, recorded negative — a launcher-level defect,
not a defect in the planner logic. `agents.yaml`'s `kickoff_command: python -m
clients.autofde_lab_planner.driver` resolved `python` against `agent_launcher.py`'s inherited
`os.environ.copy()` (no venv activation applied by the launcher), and bare `python` was not on
that `PATH`: `/bin/sh: python: command not found`, agent process exit code 127, empty result.
**Fixed**: `kickoff_command` now uses the absolute interpreter path
(`/Users/sac/autofde-lab/vendor/gyms/sregym/.venv/bin/python -m
clients.autofde_lab_planner.driver`), matching how `main.py` itself was invoked. The real
kind cluster and deploy/fault-injection sequence worked correctly up to that point (fault
injected, "Deployment complete. Ready for submission. Current stage is: diagnosis" — real,
observed) — only the agent process launch itself failed.

**Run 2** (`results/0809_0128/`): real PASS on the benchmark's own terminal scoring
(`Diagnosis.success=True`, composite 0.89; `Mitigation.success=True`), but a real, second
defect surfaced by the same run: the mismatch scan compared *every* real k8s Deployment's
image against the single canonical baseline, without first restricting to genuine
application microservices. It correctly found `geo` (the real injected fault) but also
incorrectly flagged and "fixed" 11 real infrastructure/dependency sidecars (`consul`,
`jaeger`, three `memcached-*`, six `mongodb-*`) — mutating their images too, since
`exec_kubectl_cmd_safely`'s optional whitelist gate is off in the real deployed config. The
benchmark's own **independent LLM judge caught this convergently**: `D3 Scope Precision`
scored 0.67/1.00 — "The agent lists many other deployments (consul, jaeger, mongodb, etc.) as
being part of the mismatch/fault." Since the whole `hotel-reservation` app namespace is torn
down at the end of every run regardless of outcome, the mutations never persisted beyond the
trial and the mechanical mitigation oracle's own narrow scope (`geo` only) was unaffected —
but the defect was real, not merely cosmetic, and is fixed below, not excused.

**Fix, attempt 1** (`filter_traced_application_deployments`, Jaeger-`get_services()`-based
ALLOW-list): real logic, real regression tests (12/12 passing) — but **Run 3**
(`results/0809_0137/`) exposed a *third* real defect: immediately after a fresh deployment,
before the workload generator has produced enough traffic, Jaeger had traced only 1 of 8 real
microservices (`['reservation']`, observed live). Gating solely on "has this been traced"
excluded `geo` — the actual injected fault — from scope entirely, producing a false "no
mismatch" diagnosis. Real, honest result: `Diagnosis.success=False`,
`Mitigation.success=False`.

**Fix, attempt 2** (final): a deterministic deny-list of well-known, generic OSS
infra/datastore product name tokens (`consul`, `jaeger`, `mongodb`, `memcached`, ...) as the
**primary** signal — available immediately, no traffic-timing dependency — with the real
traced-service signal retained only as a supplementary ALLOW override, never a gate. 3
regression tests added, one per defect found (14/14 total, all real, zero mocks, run against
both this repo's own `.venv` and `vendor/gyms/sregym/.venv`).

**Run 4** (`results/0809_0143/`, final): **real, clean, complete PASS.**
`Diagnosis.composite_score = 1.00` (D1 Fault Localization 1.00, D2 Fault Characterization
1.00, D3 Scope Precision 1.00 — the exact dimension the earlier defect broke, now clean),
`Diagnosis.success = True`, `Mitigation.success = True`, `TTL = 49.8s`, `TTM = 51.2s`. Real,
on-disk CSV:
`vendor/gyms/sregym/results/0809_0143/autofde_lab_planner/misconfig_app_hotel_res/
misconfig_app_hotel_res_autofde_lab_planner_results.csv`. A genuine, real, non-LLM-decided
solve of a real, live, unmodified external benchmark task, scored by the benchmark's own real
evaluators — zero paid credential, zero LLM call anywhere in the decision-making loop.

## Precision on the "beats SOTA" question — not yet established, named honestly

A real, cited WebSearch this session found sregym's real published numbers
([SREGym leaderboard](https://sregym.com/leaderboard),
[arXiv:2605.07161](https://arxiv.org/abs/2605.07161)): diagnosis success rates of **38.9% to
72.6%** and mitigation success rates of **57.3% to 78.5%**, reported as **aggregate rates
across the full 90-problem suite**, from frontier paid models (Sonnet-4.6, GPT-5.4, Kimi
K2.5) driving the real `stratus`/Claude Code/Codex agents.

**This session's real result is one complete win on one task, not an aggregate rate on a
comparable sample.** Reporting "100% > 72.6%, SOTA beaten" would compare a single,
well-shaped, favorable task against a 90-problem aggregate — exactly the register mismatch
`.claude/rules/no-overclaiming-conversational.md` and `criticism-discipline.md` (rule 2,
register parity) forbid. What IS established, precisely: a genuine, non-LLM,
planning-driven agent can reach a perfect score on a real sregym task using this repo's own
architecture — a real, positive existence proof, not yet a SOTA comparison. The real next
step, already scoped and not yet executed: run this same driver (which was deliberately built
to generalize, never hardcoding "geo") across the 3 other real sregym problems sharing this
exact oracle class (`incorrect_image`, `faulty_image_correlated`,
`update_incompatible_correlated`) to get a genuine, if still narrow, aggregate rate — and,
beyond that, a representative sample of the full 90-problem suite for a comparison that
would actually be commensurate with the published figures.
