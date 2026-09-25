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
Provider`, `subject → Subject|Repository`, `episode → Episode`). Per-event cardinalities (for
example `workorder.issue` needs exactly one `originAuthority`) live in the profile file.

Causal edges are derived, never declared: `p → e` iff `e` consumes (`input`/`cause`) an object
that `p` produced (`output`, or `consequence` on `actuate|commit|merge`). Timestamps never
create an edge; a cause produced at or after its consumer is refused as forged.

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
| HIR | post-epoch events with a human causal in-edge / post-epoch events with any causal in-edge |
| ALD | longest chain of consecutive self-generated closed-loop transitions |
| LCR | receipts that close a loop / receipts |
| RR | failures with a machine-caused recovery descendant / failures |
| UAR | actuations whose consequence lacks a later bound `receipt.persist` / actuations — **must be 0** |
| PSR | unavailable providers with a machine-caused `provider.replace` / unavailable providers |

Also reported: cold replay (the receipt holds no wall-clock value; two runs are byte-identical),
exact-subject binding (stale-subject receipts), mutation kill ratio, duplicate consequences,
orphan receipts, unknown-frontier leakage (work orders with no `candidate.admit` ancestor in
their iteration), uncaused actuations, exogenous post-epoch inputs, inter-iteration time.

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
forged authority, future cause or unknown qualifier is admitted; or if two runs over the same
bytes produce different receipts. Each has a committed mutant under
`tests/aloop/fixtures/synthetic/mutants/`.
