# Planner-Sovereign Actuation — migration spec

Status: SPEC (UNADMITTED). Source: user directive 2026-09-03, grounded in the Claude Insights
report `~/.claude/usage-data/report-2026-09-03-180152.html` (frictions: over-broad actions,
stale premises, correction loops, unbounded goals, build collisions) and Crown-2 attempt-1
falsifier findings (`/Users/sac/crown-2-integration/STANDING.post-fleet.md`).

## The law

Only an admitted planner policy may select an actuation. Claude, Fable, ChatGPT and humans
supply observations, hypotheses, goals, candidate capabilities and authority constraints;
none selects the next consequential action.

For every consequential action `a`, `ActionStarted(a)` requires exactly one triple
`(p, r, b)`:

```text
SelectedByPlanner(a, p)
PlannerSelectionReceipt(r, p, a)
PredictionFrozenBefore(r, a)
BRCEGranted(b, a)
```

and `SelectedBy(a, Claude|Fable|ChatGPT|Human) => REFUSED[NON_PLANNER_ACTUATION]`.

Two-key DO boundary: `PlannerSelectionReceipt + BRCEExecutionPermit -> gymact DO`. Neither key
alone is sufficient.

## DfCM is a planner, not a hidden scorer

Rejected shape: planners return plans, a Python scorer picks one, DO. Required shape: an
explicit `DfCMPortfolioPlanner` in autofde-lab selects among `PlanCandidate[]` from A*, MCTS,
IW, ... so a planner still selects the transition.

Common feature vector `V(s,a)`: GoalProgress, Reversibility, InformationGain,
FutureReachability, OptionDiversity, EvidenceStrength, Manufacturability, Qualifiability,
-AuthorityConsumption, -Irreversibility, -BlastRadius, -ComputeCost. Hard feasibility first
(Evidence ∩ Compatibility ∩ AuthorityPotential ∩ Manufacturability ∩ Qualifiability), then keep
the Pareto frontier. Planner adapters project the vector (A*/AO*: edge cost + admissible
heuristic; MCTS: rollout reward; RTDP/LRTDP/VI: value; BFWS/IW: novelty features; belief
RTDP: belief value + information gain). The raw vector survives into every receipt even when
a planner needs a scalar.

## Contracts

```text
PlannerPolicy:  planner_implementation, implementation_sha, parameters, objective,
                observation_projection, action_projection, domain_digest, random_seed,
                compute_budget, dfcm_projection
PlanCandidate:  ordered_actions, predicted_world_states, terminal_standing, dfcm_vectors,
                planner_value, assumptions, receipt
Goal (admission): terminal_predicate, horizon_or_budget, standing_semantics, falsifier
                  — else REFUSED[UNBOUNDED_GOAL]
```

LLM maximum authority: OBSERVE, HYPOTHESIZE, DISCOVER, EXTRACT, MANUFACTURE_CANDIDATE,
FALSIFY. Never SELECT_ACTION. An LLM emits CandidateObservation / CandidateCapability /
CandidateTransition; the Domain admits or refuses; a planner decides.

## gymact refuses raw commands

```text
execute(PlannerSelectionReceipt, BRCEExecutionPermit):
  !planner_receipt.valid                         -> REFUSED[NO_PLANNER_SELECTION]
  !authority_permit.valid                        -> REFUSED[NO_AUTHORITY]
  planner_receipt.world_digest != world.digest   -> REFUSED[STALE_WORLD_STATE]
  else                                           -> DO
```

## OCEL provenance and exact cardinality

Chain per action: WorldStateObserved -> PlannerInvoked -> PlanCandidateProduced ->
DfCMEvaluated -> PlanSelected -> PredictionFrozen -> AuthorityEvaluated ->
AuthorityGranted|AuthorityRefused -> ActionStarted -> ActionCompleted -> WorldStateObserved
-> PredictionCompared -> ReceiptIssued. Cardinality: 1 ActionStarted -> exactly 1 SelectedPlan
-> exactly 1 PlannerPolicyReceipt -> exactly 1 applicable AuthorityDecision (closes WS10's
"one AuthorityEvaluated licenses many actions").

## Adversarial fixtures from real history (Insights report)

| id | world | what the planner must show |
| --- | --- | --- |
| A blast radius | `git add <paths>` vs `git add -A` (871 files staged) | B dominated on BlastRadius/OptionDestruction before BRCE |
| B self-destruction | `rm -rf target/` removes the binary the running MCP server needs | FutureReachability collapse detected; refused or dominated |
| C stale premise | `PlanCandidate.world_digest != WorldState.digest` | REFUSED[STALE_WORLD_STATE] -> re-observe -> re-plan |
| D build collision | `beam4pm_build_slot = OCCUPIED` | wait / isolated target / alternate worktree / other work — never a second build |
| E unbounded goal | "be the #1 GitHub project" | REFUSED[UNBOUNDED_GOAL] at admission |

## Migration order (each step has an exit gate; no step inherits standing)

```text
P0 planner census      exact registry/build surface, per solver: implementation, language,
                       import standing, domain class, stochastic?, state repr, params,
                       fixtures; standing EXECUTION_PROVEN | IMPORT_ONLY | PRESENT_UNPROVEN |
                       BROKEN | UNSUPPORTED. No count inferred from filenames/docs.
                       Standing is RELATIONAL, never a scalar per solver:
                       EXECUTION_PROVEN(p, D, c, e) with fields planner, implementation_sha,
                       domain, domain_digest, parameters, seed, environment_digest, budget,
                       solve_invoked, plan_found, result_digest. "A* = EXECUTION_PROVEN" is
                       not a valid census row; "A* on Crown2Beam4pmDomain@<digest> under
                       receipt r" is. The admitted set is
                       P_admitted = { p | exists (D,c,e): EXECUTION_PROVEN(p,D,c,e) }.
P1 receipt contract    wrap execution-proven planners (A*, AO*, MCTS, LRTDP, BFWS, IW, VI,
                       RTDP-Bel per Crown work); exit: every plan has a PlannerPolicyReceipt.
P2 DfCM adapter        DfCMFeatures / DfCMVector / DfCMHardConstraints / DfCMProjection.
P3 DfCMPortfolioPlanner exit: ActionSelectedByPlanner = true; ActionSelectedByAgent impossible.
P4 two-key gymact      the actual migration point.
P5 conformance+falsifier agent-selected action, missing/fake planner receipt, stale world,
                       prediction after ActionStarted, authority reused, refusal then execution,
                       implementation mismatch, wrong subject digest, unbounded plan.
P6 remaining portfolio only after P0; per-implementation admission receipts.
```

## Next crown: PLANNER_SOVEREIGN_ACTUATION

Isolated world with fixtures A–E; run the execution-proven portfolio. Require:
planner_invocations > 1; plan_candidates > 1; DfCM vectors 100%; selected plans linked to
planner 100%; actions selected by LLM/human = 0; PredictionFrozen before ActionStarted 100%;
>= 1 real AuthorityRefused with 0 refused actions executed and replan_after_refusal > 0; stale
plan refused; consequential actions with both keys 100%; OCEL conformance violations = 0.
Then and only then: `ALIVE[PLANNER_ONLY_ACTUATION]`.

## Two planners, not one (added 2026-09-03 from the ChatGPT S4/NI discussion)

The law above governs the inner loop only. The outer loop — which planner runs next, which
experiment, when ggen manufactures, when a crown is promoted — is still selected by the
LLM authoring the workflow script. That is the same sovereignty leak one level up.

```text
Domain planner    plans the subject   (beam4pm gates; S4 protocol discovery)
Workflow planner  plans the program   (actions: InvokePlanner(p), RunExperiment(e),
                                       Manufacture(ggen, manifest), Qualify(subject),
                                       PromoteCrown(c); goal: a bounded ObjectiveReceipt)
```

Representation: a third Domain of the same shape as `tools/crown2/domain/beam4pm_domain.py`
(observe -> discover_actions -> plan -> typed NoPlanFound). The workflow planner's output is
an `ExecutionSchedule`; the LLM executes only actions present in it. Claude/Fable become a
tool adapter plus one candidate-cognition source. Falsifier rules are unchanged: a schedule
with `SelectedBy(LLM)` is `REFUSED[NON_PLANNER_ACTUATION]` at this level too.

Sovereignty residue (must be named, not hidden by the planner metaphor): the author of the
action list and the projection `rho` still decides what is plannable. Crown-2 evidence:
`mix deps.get` was invisible until WS2-style extraction surfaced it (ACTION_DISCOVERY_GAP).
So the residue lives in WS2 extractors and admission, and the outer-loop crown must show
at least one action discovered from a surface, not authored, on the schedule's path.

The residue is receipted, not removed. Required OCEL chain before any PlannerInvoked:

```text
SurfaceObserved -> CandidateActionDiscovered
  -> CandidateActionAdmitted | CandidateActionRefused
  -> ActionProjectionBuilt -> PlannerInvoked
```

Law: `SelectedAction(a) => exists r: ActionAdmissionReceipt(r, a)`. An LLM or human may
hypothesize a capability (CandidateActionDiscovered with `source=authored`); it may never
make it plannable by writing an `:action`. Only admission does that.

```text
authored candidate        permitted
authored plannable fact   forbidden   -> REFUSED[UNADMITTED_ACTION]
discovered candidate      permitted
admitted candidate        plannable
```

Shaping the decision space and selecting from it are different authorities; the receipt
chain is what lets the first be observed and falsified instead of concealed.

No third selector. The league model `M_league = P(p | DomainFeatures, Goal, WorldState,
History)` learned by beam4pm is EVIDENCE supplied to the admitted WorkflowPlannerPolicy,
never a selector: `WorkflowPlanner(O*, M_league) -> InvokePlanner(p)`. Exactly two selection
events exist and both are traceable: `SelectedWorkflowTransition` and
`SelectedSubjectTransition`. A separate meta-planner choosing `p` would recreate dual
sovereignty over one decision and restart the recursion.

Standing of the NI/S4 planner-family mapping (A*/AO*/BFWS/MCTS/LRTDP/SARSOP per decision
class): SPECULATIVE until P0 census gives each solver `EXECUTION_PROVEN`. Fixture F for
the crown: S4 as a second subject Domain (descriptors/control/output/audio predicates,
discovery actions with epistemic effects), used to show a replan after an observed state
diverges from the frozen prediction.

## Crown after PLANNER_SOVEREIGN_ACTUATION: LEGACY_DEVICE_RECONSTITUTION (S4 MK1, M3)

Gated behind P0–P5. No S4 code exists in the ecosystem index as of 2026-09-03 (lumen
search for Traktor/S4/descriptor returned only adapter probes). Every row below is
SPECULATIVE until its falsifier has run against the physical device.

| claim | what must be observed | falsifier |
| --- | --- | --- |
| manufacture against reality | a generated driver moves Mixxx state from a physical jog turn, and a Mixxx action changes a physical LED | either direction fails on hardware while the generated tests pass |
| knowledge reconstitution | every protocol fact in the S4 ontology has a receipt: trace, Linux source line, or experiment id | a fact with `source=authored` and no receipt |
| semantic leverage | one admitted ontology change regenerates decoder, simulator, fixture, mapping, doc; ratio `L = verified downstream surfaces / canonical changes` recorded per change | a surface edited by hand to make the regenerated set pass |
| action space grows from evidence | `SendLedReport` (or equivalent) absent from the first ActionProjection, present after an admitted experiment, via the admission chain above | the action appears without a `CandidateActionAdmitted` event |
| planner-only discovery | experiment order selected by the planner league; at least one `PlanRefused` when no admitted next action exists | any `SelectedBy(LLM|Human)` edge, or an LLM-improvised experiment after refusal |
| gym correspondence | `s4gym` replays recorded packets; a plan proven in the gym is re-run on hardware and the frozen prediction matches | gym pass, hardware mismatch, no divergence receipt |
| cognition compilation | a fact discovered in episode N is consumed from the ontology in episode N+1 with zero planner/LLM rediscovery events | the same fact re-derived in a later episode |
| negative fixture law | a failed physical experiment produces a constraint and a generated rejecting test | the same wrong manufacture admitted twice |

Generalization claim (Device B via the same factory) is out of scope for this crown; it
is the first candidate crown after it.

## Planner league (empirical planner selection)

Same (Domain, WorldState, Objective, ActionProjection) across admissible policies; record
planner, plan_found, time, nodes, frontier quality, predicted vs actual consequence, receipt
coverage, goal result, option topology after action. beam4pm accumulates payoff into
`M_league`, which the WorkflowPlanner consumes as evidence (see "No third selector" above).
No LLM picks the planner; no meta-planner does either.
