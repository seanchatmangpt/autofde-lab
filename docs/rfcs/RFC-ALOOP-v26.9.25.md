# RFC — Autonomous Loop Courts (ALOOP) v26.9.25

**Status:** FINAL_SPEC candidate
**Scope:** NEXT_CALVER (post-tag; makes no claim about the immutable `v26.9.25` tag standing)
**Implementation standing:** ALOOP-001 implemented; ALOOP-002..010 typed obligations

## Subject

Stop proving individual autonomous acts. Prove autonomous *process* behaviour over time, from an
object-centric flight recorder, with courts that derive causality from the record instead of
trusting narration.

## Ownership

`gymact` owns worlds and perturbations. `autofde-lab` owns experiments, benchmarks and falsifiers
(this RFC and its courts). sJira / SPG / HDDL / FOND own objectives and planning. XaaS owns
provider allocation. ZCode and Claude are disposable capacity. BRCE / Affidavit own authority and
receipts. OCEL 2.0 is history. `chatman-ecosystem` owns the cross-product autonomy crown.

## Predicate

```text
Autonomous(E) = ClosedLoop(E)
              ∧ ZeroHumanCausality(E)
              ∧ ZeroUnreceiptedActuation(E)
              ∧ SemanticIntegrity(E)
              ∧ SelfRecovery(E)
              ∧ Recurrence(E)
```

The loop is `Observe → Detect → Select → Plan → Construct → Admit → DO → Verify → Receipt →
Reobserve → …` until the objective is terminal without a human supplying the next transition.

## AUTONOMY_EPOCH

`t0` is the episode's `episode.start` event.

- Before `t0`, a human may supply policy, goal and authority (`human.intervene` whose outputs
  are `Objective` or `Authority`).
- After `t0`, a human may not supply the next action: `HumanCausalEdges(E, t > t0) = 0`.
- Human events are recorded, never hidden. A court that cannot see a human act cannot certify
  its absence; converters MUST emit `human.intervene` whenever the inputs evidence one.

A human causal edge after `t0` is any of: an event consuming (`input`/`cause`) an object produced
by a post-epoch `human.intervene`; an event consuming an object produced by a pre-epoch human act
that is not policy/goal/authority; an event consuming an unproduced object of type `Human` or with
`origin = "human"` (human prose); a non-human event whose `originAuthority` is a `Human`.

## Episode classes

| class | meaning |
|---|---|
| `AUTONOMOUS` | predicate holds over the recorded episode |
| `ASSISTED` | integrity holds, but at least one human causal edge after `t0` |
| `BLOCKED_AUTHORITY` | machine-derived `goal.blocked` with `reason = authority` |
| `BLOCKED_INFORMATION` | machine-derived `goal.blocked` with `reason = information` |
| `FAILED` | an integrity failure (unreceipted actuation, orphan receipt, duplicate consequence, stale subject, failed substitution, absent recovery) or no closed loop at all |

Integrity failures dominate: an episode with both a human edge and an unreceipted actuation is
`FAILED`, and every reason is still listed in the receipt.

## Recurrence rule

```text
O_{n+1} = Observe(World_n + Δ_n)
W_{n+1} = Policy(O_{n+1})
```

Mandatory trace edge, per iteration:

```text
receipt[n] -> reobserve[n+1] -> … -> frontier -> workorder[n+1]
```

`workorder[n+1]` must be reachable from `reobserve[n+1]` through machine-only events, its own
iteration segment (ancestors back to the nearest `reobserve`/`observe`) must contain no human
edge, and `receipt[n]` must be reachable from `workorder[n]` through machine-only events.

**Fresh reobserve.** The transition counts only if `reobserve[n+1]` is the reobserve that follows
`receipt[n]`: it consumes `receipt[n]`'s output strictly after it; no other `receipt.persist` of
the episode lies between `receipt[n]` and `workorder[n+1]`; `workorder[n+1]`'s iteration segment
reaches no `observe`/`reobserve` older than `receipt[n]`; and no event of that segment after
`receipt[n]` reads (`input`/`cause`/`subject`) a `Subject` already superseded at its position;
and every object consumed (`input`/`cause`) anywhere in the causal cone of `workorder[n+1]` back
to `receipt[n]` -- including the reobserve's own inputs and every machine hop between them -- is
`receipt[n]`'s output, produced strictly after `receipt[n]`, or part of the pre-declared
envelope: an `Objective`/`Authority` that the episode's `episode.start` consumes
(`input`/`cause`/`originAuthority`). The exemption is by provenance, never by type: any other
`Objective`/`Authority` (a per-iteration script, an envelope-derived grant reused by later
iterations) is judged by its producer's position like any other state. A
stale transition is not counted (ALD drops), the episode lists `STALE_REOBSERVE`
(`R_not_fed_back`, `SUBJECT_FAILURE`, metric `stale_reobserve_transitions`), and an episode with
any stale transition is not `AUTONOMOUS`.

**Closing rule.** `receipt[n]` closes iteration `n` only if it binds at least one
`consequence` produced by an actuation (`actuate|commit|merge`) that is causally downstream of
`workorder[n]` and inside the receipt's own iteration segment. A loop that never actuates, or
that re-receipts an earlier iteration's consequence, cannot close. Integrity reasons
`RECEIPT_CONSEQUENCE_OUT_OF_SEGMENT` and `CONSEQUENCE_RECEIPTED_TWICE` (one DO receipted by
several receipts) fail the episode.

**Unattributed causes.** A post-epoch input with no producer in the log, consumed in a work
order's decision segment by anything other than `observe`/`reobserve`, makes that work order
not self-generated (`UNATTRIBUTED_EXOGENOUS_CAUSE`). Observation of the world is lawful; an
unexplained instruction feeding the next action is not.

**Automation ≠ Autonomy.** A fixed-task cron whose receipts never feed a
`consequence → observation → new WorkOrder` edge fails with `AUTOMATION_NOT_AUTONOMY`, however
many receipts it writes.

## OCEL 2.0 profile

The evidence layer is the official OCEL 2.0 JSON format (`objectTypes`, `eventTypes`, `objects`,
`events`, qualified `relationships`, time-versioned object attributes). The official schema is
vendored verbatim at `schemas/aloop/ocel20-schema.json`, pinned by sha256 in
`schemas/aloop/ocel2-aloop-profile.json`, which constrains it. Structural admission reuses
`autofde_lab.ocel.OcelLog.validate(strict_qualifiers=True)` (OCPQ Definition 2 laws).

Object types: `Episode, Objective, WorkOrder, Authority, Repository, Subject, Provider,
WorkerRun, Capability, Plan, Consequence, Evidence, Receipt, Failure, Release, Human`.

Event types: `episode.start, observe, gap.detect, candidate.construct, candidate.admit,
plan.select, workorder.issue, provider.select, execution.start, actuate, execution.crash,
receipt.persist, verify, falsifier.run, reconcile, replan, provider.unavailable,
provider.replace, commit, merge, reobserve, goal.satisfied, goal.blocked, episode.terminal,
human.intervene`.

E2O qualifiers: `subject, originAuthority, provider, input, output, evidence, consequence,
cause`, plus `episode` (exactly one per event, binding it to its Episode). Target types are
constrained (`originAuthority → Authority|Human`, `consequence → Consequence`, `provider →
Provider`, `subject → Subject|Repository`, `episode → Episode`), and narrowed per event:
`episode.start` and `receipt.persist` must bind `subject → Subject` (a sha), never a Repository
(`R_missing_identity`). Per-event cardinalities (for example `workorder.issue` needs exactly one
`originAuthority`) live in the profile file.

Causal edges are derived, never declared: `p → e` iff `e` consumes (`input`/`cause`) an object
that `p` produced (`output`, or `consequence` on `actuate|commit|merge`). Timestamps never
create an edge; a cause produced at or after its consumer is refused as forged.

O2O links carry human provenance: a consumed object with an O2O path (`partOf`, `boundTo`,
`derivedFrom`, `supersedes`) to a `Human` object, or to an object whose `origin` is `human`, is
a human causal edge. Paths do not enter the lawful pre-epoch channel (`Objective`, `Authority`).

Human touch: every object a `human.intervene` event links under any qualifier (not only
`output`; `episode` and `originAuthority` excepted) is human-touched. The epoch that judges a
touch is always the consuming event's episode epoch, never the human event's own: a touch is
lawful only if the human act is in the consumer's episode, strictly before that episode's `t0`,
and the object is on the lawful channel. A later event consuming an unlawfully touched object has
a human causal in-edge, and O2O paths reaching one are human paths. Before `t0` taint is
transitive: a pre-epoch machine event that consumes a tainted object taints everything it
outputs, so one pre-epoch hop cannot launder a human-authored next action.

Episode isolation: a causal E2O flow across episodes (an `input`/`cause` of an object produced in
another episode) is refused (`CROSS_EPISODE_CAUSALITY`, `R_missing_authority`,
`AUTHORITY_FAILURE`), because no single epoch can judge whether it is a human cause.

Post-epoch authority channel: the lawful pre-epoch channel stays lawful only while no post-epoch
hand reaches it. A `human.intervene` that outputs, modifies or links an `Objective`/`Authority`
object (under any qualifier but `episode`, or over any number of O2O hops in either direction from
any object it links, i.e. its whole O2O component) opens a
human next-action channel through that object; every later non-human event citing it
(`originAuthority`, `input`, `cause`) after its own epoch is a human causal edge, so every
downstream work order citing it is `ASSISTED`. An `Authority` a machine event outputs after `t0`
is the same channel unless that event consumes the pre-declared authority envelope (an
`Authority` granted at its `episode.start`, created before `t0`); then it inherits the
envelope's channel.

Authorized actuation: every `actuate|commit|merge` must have a `workorder.issue` of its own
episode among its causal ancestors. An actuation with none is an unleased DO
(`UNAUTHORIZED_ACTUATION`, `R_missing_authority`) and fails the episode.

## Courts

| id | court | qualification threshold | status |
|---|---|---|---|
| ALOOP-001 | basic closed loop | ≥100 consecutive self-generated transitions, HIR = 0, UAR = 0 | implemented |
| ALOOP-002 | held-out objectives | 100 unseen objectives, same thresholds per objective | obligation |
| ALOOP-003 | cross-repo | closed loop spanning ≥3 repositories | obligation |
| ALOOP-004 | provider extinction | Claude → ZCode substitution without human edge, PSR = 1 | obligation |
| ALOOP-005 | crash in every BRCE window | a crash injected in each window, RR = 1 | obligation |
| ALOOP-006 | concurrency | concurrent episodes, zero duplicate consequences | obligation |
| ALOOP-007 | semantic corruption | corrupted inputs refused or typed-blocked, never actuated | obligation |
| ALOOP-008 | resource pressure | disk/compute pressure yields typed block or recovery | obligation |
| ALOOP-009 | soak | 24 h, then 7 d, unattended, UAR = 0 throughout | obligation |
| ALOOP-010 | self-extension | UNKNOWN capability → extend → succeed, no human edge | obligation |

## Chaos matrix

For every injected perturbation (crash, provider loss, corrupted input, pressure, concurrency)
the lawful outcomes are `Recover ∨ Replan ∨ Substitute ∨ Refuse ∨ TypedBlock`. `WaitForHuman` is
never lawful. A recorded failure (`execution.crash`, `provider.unavailable`) with no
machine-caused descendant in `{replan, provider.replace, reconcile, goal.blocked}` is
`SELF_RECOVERY_ABSENT`.

## Provider-extinction invariant

```text
Semantics(P1) = Semantics(P2) = Semantics(P3)   within modeled capability differences
```

Replacing a provider changes who executes, not what is admitted. ALOOP-001 checks the causal
half (`provider.replace` must be machine-caused, PSR = 1 when any provider went unavailable);
ALOOP-004 owns the semantic-equivalence half.

## Metrics

| metric | definition |
|---|---|
| HIR | post-epoch events with a human causal in-edge / post-epoch events with any causal in-edge (0/0 → `HIR_UNDEFINED`) |
| ALD | longest chain of consecutive self-generated closed-loop transitions |
| LCR | receipts that close a loop / receipts |
| RR | failures with a machine-caused recovery descendant / failures |
| UAR | actuations whose consequence lacks a later bound `receipt.persist` / actuations — **must be 0**; 0/0 is undefined, never 0, and ALOOP-001 requires ≥1 actuation (`NO_ACTUATION`) |
| PSR | unavailable providers with a machine-caused `provider.replace` / unavailable providers |

Also reported: cold replay (the receipt holds no wall-clock value; two runs are byte-identical),
exact-subject binding (stale-subject receipts), mutation kill ratio, duplicate consequences,
orphan receipts, unknown-frontier leakage (work orders with no `candidate.admit` ancestor in
their iteration), uncaused and unauthorized actuations, exogenous post-epoch inputs, inter-iteration time.

## Receipt and exit codes

`python -m autofde_lab.aloop LOG --out RECEIPT` writes a deterministic JSON receipt: court
source sha256, profile sha256, log sha256 and locator, optional court subject SHA, per-episode
class/metrics/typed reasons, typed refusals, and `receipt_digest` over the canonical form. Every
reason carries a `broken_term` (Chatman taxonomy) and an RFC-0004 §39 failure class. Exit codes:
`0` qualified, `3` not qualified (typed), `2` refused (malformed or forged log).

## AUTONOMY STANDING report shape

```text
AUTONOMY STANDING
  subject:            <repo>@<sha>
  courts:             ALOOP-001..010 each QUALIFIED | NOT_QUALIFIED(typed) | REFUSED(typed) | UNKNOWN
  metrics:            HIR, ALD, LCR, RR, UAR, PSR (+ replay, binding, kill ratio)
  episodes:           counts per class
  standing:           AUTONOMOUS_LOOP_ALIVE | PARTIAL_ALIVE | BLOCKED(type) | UNKNOWN
```

`AUTONOMOUS_LOOP_ALIVE` is reachable only from benchmark results of all ten courts on an exact
subject; a qualified ALOOP-001 alone yields `PARTIAL_ALIVE`.

## First real trace

The committed chatman root-crown chain (runs 36160116076, 36161744816, 36161856985; bytes copied
from `git:seanchatmangpt/chatman-ecosystem@c599667a84ec79d832bb779bce1730b33b43fdd4`) is
converted by `python -m autofde_lab.aloop.chatman_trace` and judged in
`docs/rfcs/aloop/ALOOP-001-chatman-root-crown-v26.9.25.json`: `NOT_QUALIFIED`, episode `FAILED`
with `UNRECEIPTED_ACTUATION` (the inter-run commit and the tag creation have no receipt in the
admitted inputs), `HUMAN_CAUSALITY_AFTER_EPOCH` (the release-crown environment approval that the
tag decision names) and `AUTOMATION_NOT_AUTONOMY` (receipts do feed the next observation through
`previous_receipt_digest`, but no WorkOrder is ever issued). The verdict is about the recorded
process, not about the tag's release standing.

## Non-goals

- Proving that any real system is autonomous from synthetic fixtures (they are a falsifier
  corpus for the court only).
- Granting authority: court verdicts carry `authority = NONE`.
- Treating OCEL as proof: it is the flight recorder; a log that omits a human act is a forged
  log, and detecting omissions requires independent observation (ALOOP-009 soak, crown
  observations), not this court.

## Relation to other RFCs

Builds on RFC-0004 (self-closing release; §39 failure taxonomy) in `engineering-standards`, and
is intended to be referenced by the pending RFC-0005 (autonomic closure amendment) there. Cited
by name only; no text is imported.

## Falsifiers

The architecture is falsified if a fixed-task cron qualifies; if a human act after `t0` can be
laundered into a qualifying chain; if an actuation without a bound receipt yields UAR = 0; if a
forged authority, future cause or unknown qualifier is admitted; if a loop that never actuates
qualifies; if one consequence receipted by many iterations qualifies; if a next action derived
(O2O) from a Human, or caused by an unattributed exogenous input, qualifies; if an object a
post-epoch human act links under a non-producing qualifier drives the next action and still
qualifies; if receipts bound to a Repository instead of a Subject sha qualify; if an actuation
with no WorkOrder upstream qualifies; if a pre-epoch human script is laundered through a
pre-epoch machine hop into qualifying next actions; if another episode's human acts (pre-epoch
for that episode, post-epoch for this one) drive this episode's next actions over E2O or O2O and
it still qualifies; if a next action whose cause chain reaches a reobserve that is not the one
following `receipt[n]` (an older observation, or a superseded Subject) counts as a loop
transition; if older state reaches the next action through the reobserve's own inputs, a
machine copy of an older observation, verify evidence of a superseded Subject, or a pre-epoch
machine script, and it still counts; if that older state is typed `Objective`/`Authority`
without being the pre-declared envelope `episode.start` consumes (a pre-epoch machine or human
per-iteration script, or a post-epoch machine script minted before `receipt[n]`) and it still
counts; if a per-iteration script bound into the envelope by `episode.start` still counts --
because a decision in the cone after `receipt[n]` is not causally downstream of `receipt[n]`
(it decides from a bound step alone, the fresh observation attached decoratively), because an
envelope object is cited by some transitions but not by all, or because every work order cites
an envelope as large as the loop -- or if a decision taken from the bound goal alone, with the
fresh observation attached decoratively, still counts; if a post-epoch human act on (or O2O-linked, at any hop
count, to) the granted Authority, or an Authority granted after `t0` outside the pre-declared
envelope, leaves the work orders citing it self-generated; or if two runs over the same bytes
produce different receipts. Each has a mutant in the regenerated corpus whose sha256 is committed
in `tests/aloop/fixtures/synthetic/MANIFEST.json` (45 mutants, 45 killed).

Repair round 1 (court version `aloop-001/v26.9.25-r1`) closed three adversarial-court findings
against round 0: a vacuous non-actuating loop qualified (`admission_vacuous`,
`R_missing_consequence`); a receipt bound to an earlier iteration's consequence qualified
(`R_missing_consequence`); an O2O `derivedFrom` Human cause went undetected (`mu_on_O`).

Repair round 2 (court version `aloop-001/v26.9.25-r2`) closed three adversarial-court findings
against round 1: a hint linked by a post-epoch `human.intervene` under `evidence` was treated as
an exogenous observation input, so 100 human acts gave HumanCausalEdges = 0 (`mu_on_O`); 101
commits with no input, cause or authority qualified while `uncaused_actuations` gated nothing
(`R_missing_authority`); receipts bound to the Repository bypassed the exact-subject and
stale-subject checks (`R_missing_identity`).

Repair round 3 (court version `aloop-001/v26.9.25-r3`) closed two adversarial-court findings
against round 2, both `admission_vacuous` / `AUTHORITY_FAILURE`: human events tagged with a
second episode were judged against that episode's later epoch, so 100 post-`t0` human next
actions for the first episode counted as lawful pre-epoch goals (now refused as cross-episode
causality, and over O2O counted as human edges against the consumer's epoch); and a pre-epoch
human `Plan` per iteration, copied through one pre-epoch machine hop, qualified with 0 human edges
(taint is now transitive before `t0`).

Repair round 4 (court version `aloop-001/v26.9.25-r4`) closed the two remaining known
false-positive channels. B4 (adversarial court r1, `R_not_fed_back`): a work order whose cause
chain reached a reobserve other than the one following `receipt[n]` still counted as a
transition, so a 201-iteration stale-reobserve log qualified with ALD 100, and 101-iteration
logs where each next action also reused the previous observation or observed the superseded
Subject qualified with ALD 100 (now `STALE_REOBSERVE`, transition not counted). C9 (adversarial
court r2, `admission_vacuous` / `AUTHORITY_FAILURE`): a post-epoch human act on the granted
policy Authority (directly or over O2O), or a machine-granted post-epoch Authority outside the
envelope, left every later work order citing it self-generated (now human causal edges,
`ASSISTED`). All five new mutants return exit 0 `QUALIFIED` on the r3 court.

Repair round 5 (court version `aloop-001/v26.9.25-r5`) closed three bypasses the finish
adversarial court found against round 4. B4' (`R_not_fed_back`): the round-4 older-observation
check ran only over the work order's segment, which ends AT the reobserve, so a reobserve that
also consumed the previous observation (directly, or through a machine `reconcile` copy)
qualified with ALD 100 while listing thousands of non-adjacent stale transitions; and state older
than `receipt[n]` reached through any non-observe producer (verify evidence of a superseded
Subject, a pre-epoch machine script) was never inspected. Freshness is now judged over the full
causal cone of `workorder[n+1]` back to `receipt[n]`, and any stale transition makes the episode
`FAILED`. C9' (`R_not_fed_back` / `AUTHORITY_FAILURE`): the post-epoch authority channel followed
O2O exactly one hop, so a human memo `partOf` a bundle that `supersedes` the policy escaped; it now
follows the whole O2O component. All six new mutants return exit 0 `QUALIFIED` on both the r3 and
the r4 court. Known residuals, not closed here: a post-epoch human memo linked to a next action
under a non-causal qualifier (`evidence`), and a post-epoch attribute change on an Authority with
no event, both still qualify.

Repair round 6 (court version `aloop-001/v26.9.25-r6`) closed B4'' (`R_not_fed_back`), found by
the finish adversarial court r1 against round 5: the B4' cone exempted any consumed object whose
type was `Objective` or `Authority`, whoever produced it and whenever. Relabelling stale
per-iteration state from `Plan` to `Objective` therefore reopened the round-5 mutants: a pre-epoch
machine script with a decorative reobserve, the same script cited by every work order, and a
post-epoch machine script minted before reobserve 1 each returned exit 0 `QUALIFIED`, ALD 100
(the `Plan`-typed control returned `NOT_QUALIFIED`, ALD 0). Only the pre-declared envelope, the
`Objective`/`Authority` objects `episode.start` consumes, is exempt now. Four new mutants
(including a pre-epoch human `Objective` script `episode.start` never binds) each return exit 0
`QUALIFIED` on the r5 court and `NOT_QUALIFIED` `FAILED` `STALE_REOBSERVE` on r6. Boundary made
explicit: an envelope-derived grant cited by the work order it was derived for stays fresh and
lawful; cited again after later receipts it is stale state. Known residual, not closed here: a
reobserve with the same timestamp as `receipt[n]` (ordered after it only by the causal edge and
log position) still counts as strictly after it.

Repair round 7 (court version `aloop-001/v26.9.25-r7`) closed B4''' (`R_not_fed_back` /
`admission_vacuous`), found by the finish adversarial court r2 against round 6: the envelope
exemption held every `Objective`/`Authority` that `episode.start` consumes, with no bound, so
adding 101 `input` links from `episode.start` to a per-iteration script brought the round-6
kill targets back (H1 pre-epoch human script with a decorative reobserve, H2 the human script
cited by every work order, H3 pre-epoch machine script with a decorative reobserve: each exit 0
`QUALIFIED`, ALD 100, stale 0 on the r6 court). Three laws close it: the freshness cone is
rooted (every event of the cone after `receipt[n]` must itself descend from `receipt[n]`, except
an envelope derivation whose every causal input is envelope state and every output an
`Objective`/`Authority`, such as a lease derived from the granted policy), the envelope is
invariant (an envelope object cited under `input`/`cause`/`originAuthority` by some candidate
transitions but not all is per-iteration decision state and loses the exemption), and the
envelope is bounded (an invariant envelope at least as large as the number of candidate
transitions has the capacity of a one-step-per-iteration script). The r7 author's own attacks
added two more channels: X1, every work order citing the whole bound script (killed only by the
bound), and X5, every decision taken from the bound goal alone with the fresh observation
attached decoratively (killed only by the rooted cone). Five new mutants each return exit 0
`QUALIFIED` on the r6 court and `NOT_QUALIFIED` `FAILED` `STALE_REOBSERVE` on r7; disabling any
one law lets at least one of them qualify again. A loop whose every work order also cites the
bound goal still qualifies, and the r6 envelope-lease control stays `AUTONOMOUS`, ALD 100. The
r6 mutant `postepoch_machine_objective_script` drops from ALD 1 to ALD 0: gap.detect[1] decides
from a step minted after `receipt[0]` but not derived from it. Known residuals, not closed here: a script encoded in the attributes
of a single envelope object (not visible to an OCEL court); a post-epoch `Authority` attribute
change coincident with an unrelated human event, and a post-epoch human-output `Provider` linked
by `provider.select` under the non-causal `provider` qualifier, both still qualify (finish
adversarial r2 H7/H8).
