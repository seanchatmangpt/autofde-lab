# Level 4 gym migration matrix

Real census, this session, of every GymAct-capable provider reachable from `level4_gymact_bridge.py`, the sibling `~/gymact` package's `gyms/` directory, and `autofde_lab.hub.domain.*` bridges — gathered by 30 real, read-only census agents (out of ~44 dispatched; the workflow was killed mid-run at 46 agents dispatched/31 completed, `w9lme71pm`/`wf_a0bbfca7-d50`) plus 3 real tracer-bullet trials run directly. Every row below is either a real trial result or a real-source-inspection census result — none is inferred from memory.

## Level 4 ALIVE (3)

| Gym | Trial identity | Real finding |
|---|---|---|
| `resource_flow` (TracerBulletA) | seed `3979297810`, trial `5e10eecf-52e6-463f-893c-efa0da93d5a7` | `Conforms: True`, 14/14 falsifiers, destructive verification. See `docs/2026-08-08-level4-shacl-tracer-bullet.md`. |
| `lock_and_key` (TracerBulletB) | seed `3979297810`, `depth=2`, `probe_budget=40`, trial `7ee7eaec-3eff-4b07-b796-6bff521c0ece` | Same, zero kernel edits from A. |
| `switchboard` (TracerBulletC) | seed `3979297810`, `probe_budget=40`, trial `b95bea45-4b18-48f7-9321-934e325ce443` | Same, zero kernel edits from A/B, run by a census workflow agent through the unmodified CLI. |

`THREE_GYM_KERNEL_GATE = PASSED`: `level4_witness.py`, `verify.py`, and `ontology/shapes/{level4,authority,planning}.shacl.ttl` are byte-identical across all three. Zero provider-specific branches exist in any of them (`grep -n "resource_flow\|lock_and_key\|switchboard\|cube_counter\|provider_key ==" src/autofde_lab/evidence/*.py` → zero matches).

## Real, precisely diagnosed: not yet ALIVE

| Gym | Real finding |
|---|---|
| `cube_counter` | **Not a kernel gap, and narrower than "the induction can't generalize numeric effects."** `TypedDomain`'s effect representation already generalizes correctly — `TypedEffect.delta` is a real relative-change value (`counter' = counter + delta`), and `search_plan_typed` does a real forward BFS over `TypedDomain.apply_action`, capable in principle of deriving an unobserved state (e.g. `counter=3`) from a learned `+1` rule without ever having seen that exact transition. Confirmed directly: in this trial's own induced model, `reward` (a `CONTINUOUS` dimension) correctly got `delta=+0.166667`, generalized correctly. The real, exact bug: `counter` itself gets reclassified from `INTEGER` to `CATEGORICAL_ID` by `state_typing.py`'s `_is_categorical_id()` — a heuristic added deliberately to fix `lock_and_key`'s `held_key=-1` "no key held" sentinel (small distinct integer set + a negative value present ⟹ treat as an identity, strip arithmetic). Its own docstring states the premise `_is_categorical_id` relies on: `counter`/`raw`/`output`/`locks_open` are "never negative, so none is caught by this rule." `cube_counter`'s `decrement` action falsifies that premise directly — confirmed live: `classify_observation` on this trial's real observations returns `counter -> CATEGORICAL_ID` (`is_metric: False`) the moment a `decrement`-produced negative value is observed, and `induce_typed_domain` then marks `counter`'s effect `CONTEXT_DEPENDENT` (unclaimed) rather than `delta=+1`/`-1`, so `search_plan_typed` has no rule to extrapolate with and correctly (given that model) returns no plan. This is a real false positive in one classifier heuristic — conflating "a negative value was observed" with "this is an identity-sentinel pattern" — not a missing representational capability. Matches and sharpens pre-existing task #21 ("lock_and_key: prefix-keyed induction + CATEGORICAL_ID dimensions") with an exact second failure mode of the same discriminator. `level4_witness.py`/`verify.py`/SHACL are completely unimplicated — this gym was never reached by the evidence kernel at all, since `run_real_trial` returns before any actuation happens. |
| `cube_container_counter` | Census: `SAFE_EXECUTABLE`, `estimated_migration_difficulty: low`, real dependencies verified live (Docker daemon reachable via colima, `vendor/gyms/cube-standard` submodule checked out, module imports cleanly in `~/gymact/.venv`). Shares `cube_counter`'s goal predicate and oracle — **likely shares the same discovery-termination gap**, not yet run through `run_real_trial` this session to confirm either way. |

## ADAPTER_MISSING (19)

Two distinct sub-populations:

**Individually unwired GymAct providers** (`gymnasium_env`, `terraform_docker_apply`, `ggen_legacy`, `mcp_client_session`, `inspect_evals`, `discovered`) — each absent from `level4_gymact_bridge.py`'s `_PROVIDERS` dict; adding an entry is gym/capability-layer work, not a kernel change.

**The `VendorBenchmarkProvider` family** (`agentbench`, `agentlab`, `asb`, `assetopsbench`, `azuregoat`, `bountytasks`, `crmarena`, `cube-harness`, `cube-standard`, `cybergym-e2e`, `doomarena`, `aiopslab` — 12 of this census's sample; the real class covers 52 pinned vendor revisions total per `gymact.gyms.vendor_benchmarks.VENDOR_REVISIONS`, so most weren't individually censused before the workflow was killed): **one shared, precisely diagnosed root cause**, confirmed by direct source inspection (`agentdojo`'s census result, representative): `level4_gymact_bridge.py`'s `_BRIDGE_SCRIPT` always instantiates providers zero-arg (`provider_cls()`), but `VendorBenchmarkProvider.__init__(self, name: str)` requires a positional `name` — every vendor in this family hits `TypeError: __init__() missing 1 required positional argument: 'name'` before `materialize()` is even reached. This is real DCM leverage: one bridge-construction fix is a prerequisite for all 52, but **not sufficient by itself** — see the two further gaps below, both real and separately diagnosed, not yet collapsed into a smaller basis:

1. **No goal predicate or independent postcondition oracle exists for any vendor benchmark.** `model_goal_predicate`/`predict_step_postconditions` in `level4_crown.py` both hard-raise `UNSUPPORTED_PROVIDER_FOR_GOAL`/`UNSUPPORTED_PROVIDER_FOR_POSTCONDITION_PREDICTION` for any `provider_key` outside the 5 already-wired names. `VendorBenchmarkEnvironment.observe()` returns only `{vendor, revision, root, last_result}` — no task id, no pass/fail signal, no security-check outcome; a real goal predicate per vendor would need each benchmark's own evaluator/expected-state/test-oracle output, which is not currently surfaced through the generic `run-native` capability at all.
2. **Real, materially higher risk than any currently-wired gym.** `VendorBenchmarkEnvironment.actuate()`'s one capability (`run-native`) executes an arbitrary native subprocess (`asyncio.create_subprocess_exec`) bounded only by an argv[0]-path guard — it can write files anywhere under the vendor checkout and make real outbound LLM-API calls (OpenAI/Anthropic/Cohere/Google, confirmed present in several vendors' own dependency lists) using whatever credentials are ambient. This is qualitatively different from the 5 wired gyms, which mutate only in-memory episode state. Per this session's own explicit instruction: do not let `SUPPORTED` become `EXECUTE IT` — this family needs an explicit budget/authority abstraction before any real actuation, not just a constructor fix.

## AUTHORITY_REQUIRED (2)

`cloudgoat`, `cloudfoxable` — real cloud-infrastructure attack-simulation benchmarks; census flags real-world mutation risk requiring deliberate authority scoping beyond the current `AllowListAuthorityResolver({one static ref})` pattern.

## CAPABILITY_MISSING (5)

`azuregoat_privesc`, `browsergym`, `codebase`, `kubernetes_reconciliation`, `multicloud` — registered in the sibling `gymact` package or as a separate autofde-lab bridge (`azuregoat_privesc`), but not reachable through the existing `RealBlindEnvironment`/`_PROVIDERS` construction path for provider-specific reasons (each census result names its own).

## DEPENDENCY_BLOCKED (1)

`androidworld` — real external dependency absent locally.

## Not captured

The workflow was killed (`status: killed`, not `completed`) partway through the census fan-out — 31 of 46 dispatched agents returned a result (one, `gym_id: null`, was malformed/truncated and is not included above); the remaining ~13-15 in-flight census agents and the entire migration-attempts phase never ran. Given the `VendorBenchmarkProvider` family alone covers 52 pinned vendor revisions (most uncensused), the true total gym surface is larger than this table shows. This table is a real, honest partial census, not a complete one.

## What this session did NOT do, deliberately

- Did not fix the `_BRIDGE_SCRIPT` constructor-signature mismatch. It is a real, precisely diagnosed, single-point defect blocking ~52 vendor benchmarks, but fixing it without also resolving the goal-oracle and authority gaps would just move the failure mode from "won't construct" to "constructs, then either can't be graded or can execute unbounded native commands" — not real progress.
- Did not hand-write per-vendor goal predicates. Per this session's own explicit instruction, that would be exactly the `if vendor == "foo": ...` anti-pattern this kernel's design forbids. Whether vendor benchmarks' own evaluator/expected-state/test-oracle output can be projected through a small number of shared semantic categories (not 52 individual cases) is real, unstarted design work.
- Did not attempt `cube_container_counter` (its dependency chain — Docker/colima — makes a failed attempt more expensive to clean up than `cube_counter`'s pure in-memory case, and it likely shares `cube_counter`'s exact discovery-termination gap, so root-causing that gap once is worth more than a second confirming trial right now).

## See also

- `docs/2026-08-08-level4-shacl-tracer-bullet.md` — the three real ALIVE tracer bullets, in full.
- `docs/STATUS.md` Pass 10 — the ledger row.
- Repo task #21 — the pre-existing, still-open "lock_and_key: prefix-keyed induction" item this pass's `cube_counter` finding is the same character of gap as.
