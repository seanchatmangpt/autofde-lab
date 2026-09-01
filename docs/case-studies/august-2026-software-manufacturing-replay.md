# Case study: replaying August 2026 as a software-manufacturing organization

## Question

Can the engineering behavior represented by a 24,340-commit month be compiled into
planning files so heterogeneous agents can enter equivalent worlds and reproduce
full-stack delivery behavior rather than merely imitate commit messages?

## Model

A commit is evidence of a repository transition, not the planning unit. The
compiler admits normalized historical events and groups them into episodes using an
explicit `episode`/`workstream`, PR number, branch/ref, or repository fallback.
Each episode becomes a deterministic partial-order planning file:

```text
historical events
  -> episode inference
  -> intent + engineering-surface inference
  -> dependency/causal edges
  -> planning file
  -> replay world
  -> agent selections
  -> deterministic simulation receipt
```

The surface vocabulary spans source, tests, GitHub, CI/CD, infrastructure as code,
cloud, containers, security, observability, docs, and release behavior. The plan
also records required authority classes, but those classes are descriptive. The
replay world cannot acquire or exercise external authority.

## Historical-count fence

The reported August total and the export evidence count are separate variables:

```text
reported_commit_count = 24,340
observed_commit_count = count(commit events in admitted export)
complete_history_observed = reported == observed
```

This is deliberate. GitHub search surfaces can be capped or incomplete. A compiler
that silently treats a partial search result as the whole month would manufacture
false evidence.

## Agent gym

`ReplayWorld.admissible_actions()` exposes only steps whose declared dependencies
are satisfied. An agent selects a step id; `apply()` records the transition. A
reference policy deterministically chooses the first admissible step until closure.
The resulting receipt is `ALIVE` only when every plan step has been completed and
always reports:

```json
{
  "authority": "NONE",
  "do_authority": false,
  "evidence_kind": "SIMULATION_RECEIPT"
}
```

This lets Claude, Codex, Gemini, symbolic planners, RL policies, or planner leagues
compete over the same planning file without conflating simulation with GitHub,
cloud, deployment, or release authority.

## 24,340-event scale court

The Chicago court constructs 24,340 normalized commit observations, compiles them
in forward and reversed input order, and requires identical corpus and plan
digests. The repeated transition compacts to one plan step while all 24,340 commit
SHAs remain in the historical trace. This validates scale and determinism without
pretending the synthetic scale court is the real August export.

## Next experiment

Materialize the complete August export across repositories and run multiple policies
against the resulting episode set. Compare trajectory closure, surface coverage,
repair frequency, dependency violations, information gain, and option preservation.
The benchmark unit is then an operating software-manufacturing organization, not an
isolated coding issue.
