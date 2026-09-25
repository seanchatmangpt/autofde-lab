# RFC — Autonomous Loop Courts (ALOOP) v26.9.25

**Status:** FINAL_SPEC candidate
**Scope:** NEXT_CALVER (post-tag; makes no claim about the immutable `v26.9.25` tag standing)
**Implementation standing:** ALOOP-001 implemented (court `aloop-001/v26.9.25-r9`, with the
sealed-recorder profile); ALOOP-002..010 typed obligations

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
| `CONSISTENT_UNDER_ASSUMED_COMPLETENESS` | (since r9) every rule holds, but the log is not sealed and complete, so `AUTONOMOUS` would be a claim about absence the log cannot carry; `rule_class` keeps `AUTONOMOUS` |

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
not self-generated (`UNATTRIBUTED_EXOGENOUS_CAUSE`). Since repair round 8 this is one instance of
the closed-world clause P1 below, which covers every post-epoch link, observations included.

## Fail-closed provenance law

Repair round 8 (court `aloop-001/v26.9.25-r8`) stops closing channels one at a time. Rounds 1-7
each exempted a class of object (by qualifier, type, envelope membership or count) and each
exemption was the next attack surface. Three clauses replace the exemptions; each fails closed.

**P1 closed world** (`UNATTRIBUTED_EXOGENOUS_CAUSE`, `mu_on_O`, `EVIDENCE_FAILURE`). Every
object a post-epoch machine event links, under any qualifier except its own `output` (and an
actuation's `consequence`), must be either
(i) output by a machine event of the same episode that is itself after `t0` and strictly
earlier in time than the linking event, or
(ii) frozen envelope state: declared by the episode's `episode.start` (linked by it under any
qualifier), created at or before `episode.start` (no producer after it), and never modified
after `t0` (no attribute value timed after `t0`, no post-epoch output, no post-epoch or
foreign-episode human link), and (since r9) neither indexed nor varying under P3.
An OCEL `ObjectChange` has no producing event: since r9 a value on a non-envelope object is
attributed only when it is timed exactly at the object's post-epoch machine producer (the event
that created it set it); any other value -- changed after creation, or timed before the object
existed -- is unattributed.
Anything else fails the episode: no producer and no declaration, a producer in another episode,
a pre-epoch producer whose output `episode.start` does not declare, a timestamp-only ordering,
an equal timestamp. The affected work orders are not self-generated (ALD drops) and the episode
is `FAILED` (`unattributed_post_epoch_events` > 0). Human objects, and objects a human act
outputs after `t0` or in another episode, are P2's jurisdiction. A causal flow across episodes
is still refused earlier (`CROSS_EPISODE_CAUSALITY`).

**P2 human taint is qualifier-agnostic** (`HUMAN_CAUSALITY_AFTER_EPOCH`, `R_not_fed_back`).
A post-epoch event is human-caused if any object it links, under any qualifier (`evidence`,
`provider`, `subject` and `originAuthority` included, `episode` excepted), or any object in that
object's O2O component (either direction, every O2O qualifier, any depth, no type exemption):
is a `Human` or has `origin = human`; is linked, under any qualifier, by a `human.intervene`
after the consumer's `t0` (or of another episode) that is no later than the consumer; carries
an attribute value timed after `t0` and exactly at a human act; or (since r9) carries an
attribute value no event attributes (P1 above), timed at or after any post-epoch or foreign
human act -- whatever the nanosecond offset. Any such edge makes the episode
`ASSISTED`. There is no exemption list; only the frozen pre-epoch envelope of the consumer's own
episode is lawful human origin.

**P3 rooted, functional, unindexed cone** (`STALE_REOBSERVE`, `R_not_fed_back`,
`SUBJECT_FAILURE`). A transition `receipt[n] -> reobserve[n+1] -> workorder[n+1]` counts only if:
every hop of the cone of `workorder[n+1]` between `receipt[n]` and `reobserve[n+1]` descends from
`receipt[n]`, and every other hop descends from `reobserve[n+1]` itself (the r7 envelope
derivation, every causal input envelope state and every output an `Objective`/`Authority`, stays
allowed); every causal hop is strictly increasing in time, `reobserve[n+1]` included (G7); the
envelope objects cited in the cone are the same for every transition (invariant); one
`reobserve[n+1]` roots exactly one `workorder[n+1]` (a forked next action is not one
transition); and the envelope is not indexed -- a family of same-typed envelope objects (same
type and `Authority` kind) or an envelope object whose attribute holds more than one value (an
ordered value history) can be indexed per iteration, so it loses the exemption. P3 replaces the
r7 count bound (an invariant envelope at least as large as the candidate count), which candidate
inflation defeated (J3).

Since r9 the indexed and invariant clauses hold over the whole episode, not only the cone of
`workorder.issue`, and they bind P1. Indexed is judged over every object `episode.start`
declares, of any type and under any qualifier (not only `Objective`/`Authority`): a same-typed
family, a multi-valued attribute, or an attribute key outside the profile's closed
`failClosedProvenance.envelopeAttributes` vocabulary for the object's type (a key-indexed
script). Varying: among the post-epoch machine events of one activity that cite envelope objects
(under any qualifier but `episode`), an object cited by some and not all. An indexed or varying
envelope object is not frozen envelope state for P1, so citing it anywhere after `t0` --
`actuate`, `execution.start`, `provider.select`, `commit`, `gap.detect`, `workorder.issue`, under
`input`, `cause` or the non-causal `evidence` -- is `UNATTRIBUTED_EXOGENOUS_CAUSE`.

Evidence ceiling: a script written into one scalar attribute value of a single-valued envelope
object (for example a long `description` string) is not visible to an OCEL court. Neither is a
script of at most one object per (type, `Authority` kind) pair, each cited identically by every
occurrence of an activity, whose step order lives only outside the log. Both are named residuals
(`UNKNOWN`), not claims of absence.

**Automation ≠ Autonomy.** A fixed-task cron whose receipts never feed a
`consequence → observation → new WorkOrder` edge fails with `AUTOMATION_NOT_AUTONOMY`, however
many receipts it writes.

## Non-convergence and the sealed recorder

Repair round 9 stops treating the rules as able to certify autonomy on their own.

**Non-convergence theorem.** Let the log `L` be authored by the party `A` whose process is
judged, and let a court be any predicate `C(L)` over the log bytes. (1) `A` controls every byte
of `L`: qualifiers, types, timestamps, O2O links, attributes, and which events exist. (2) A
human cause that `A` does not record leaves no byte in `L`: for any `L` with a human act `h`
there is `L' = L \ {h}` (with `h`'s outputs re-attributed to machine events) that `A` could have
written. (3) If `C(L') = QUALIFIED` for a faithful fully-autonomous log `L'`, it also holds for
the same bytes written after an unrecorded human step. So no shape rule over `L` certifies the
absence of human causation, and completeness is not observable from `L`. Generate-and-kill over
shape rules cannot converge: every rule's complement is the next attack (rounds 1-9 measured
this: each round's exemption was the next round's attack), and the omission attack needs no
shape at all. `NOT_QUALIFIED` stays sound (a log that incriminates its author is evidence
against it); `QUALIFIED` does not, against an adversarial author.

**Verdict lattice.** `QUALIFIED` (exit 0, episode `AUTONOMOUS`) requires three things: the log
is sealed (below), it is complete against external witnesses, and every ALOOP-001 rule holds.
An unsealed log that passes every rule, or a sealed one without both witnesses, is
`CONSISTENT_UNDER_ASSUMED_COMPLETENESS` relative to `envelope_sha256` (sha256 of the canonical
frozen envelope objects), standing ceiling `PARTIAL_ALIVE`, exit 3; its receipt states the
assumption in `claim`. `NOT_QUALIFIED` (exit 3) and `REFUSED` (exit 2) are unchanged. A sealed
log whose chain, signature, bijection or completeness fails is `REFUSED` (exit 2). The receipt
field `rules_consistent` records the rule verdict alone; mutation kill counts use it, not the
exit code (every unsealed log exits non-zero, so exit status alone would be a vacuous kill).

**Sealed-recorder profile** (`aloop-sealed-recorder/v1`, `src/autofde_lab/aloop/seal.py`). The
recorder, not the judged author, writes the evidence stream: each OCEL event, in log order, is
carried by one record of the `ProvenanceLedger` (`src/autofde_lab/_cache/provenance.py`, its
record type generalized rather than duplicated): `sequence`, `previous_digest` hash chain,
`record_digest`, and an HMAC-SHA256 `AttestationSigner` signature by a recorder key that is not
in the log (key material found in the log or ledger bytes is `SEAL_KEY_DISCLOSED`). A final
`close` record binds sha256 of the whole canonical document, so objects, attribute changes and
O2O are sealed too. The verifier checks, in order: the chain and signatures under its own
keyring (`SEAL_CHAIN_INVALID`, `R_missing_identity`); the OCEL<->ledger bijection -- one record
per event, same order, same digest, and the close digest (`SEAL_BIJECTION`); then completeness:
(a) every commit of each named repository's `git rev-list <range>` maps to exactly one sealed
`actuate`/`commit`/`merge` event whose output `Subject` has that `repository` and `sha`
(`SEAL_INCOMPLETE_COMMIT`, `R_missing_consequence`: a missing or duplicated commit event), and
every such event is inside the range of a witnessed repository -- a claim naming a repository
outside the witnessed set is refused too (`SEAL_UNWITNESSED_COMMIT`); (b) every entry of the
supplied human-message ledger -- pre-epoch entries included -- maps to exactly one sealed
`human.intervene` event carrying that `messageId`, whose time equals the message's witnessed
time and which sits on the same side of `episode.start` in log order as its witnessed time is
of `t0`; a `human.intervene` carries at most one `messageId` (`SEAL_INCOMPLETE_HUMAN`,
`mu_on_O`). Matching on `messageId` alone would let the author relabel a mid-loop human message
as pre-epoch goal supply by attaching its id to an earlier event (repair of court attacks A1b,
A3, A4 on `5a1cd259`). (c) The log clock is anchored outside the author's bytes: each sealed
commit event's time equals, to the second, the git committer time of its SHA, and `t0` lies in
`[base committer time, first witnessed commit event]` (`SEAL_CLOCK_MISMATCH`,
`R_missing_identity`). Without (c) the recorder signs whatever times it is handed: on
`f9a1fcd9` shifting every event time one day forward pushed a genuine mid-loop human message
before the declared `t0`, where the old pre-`t0` filter dropped it from the witness set, and the
sealed log exited 0 `QUALIFIED` (court attack C2; API and CLI). A non-empty human ledger over an
unanchored clock (no git clock supplied, or an empty witnessed range) is `complete = None`,
never `QUALIFIED`. CLI: `--seal LEDGER --key-file F --key-id ID --git REPO_ID=PATH:RANGE
--human-ledger FILE`; `--git` reads the range's committer clock and its base's (`git_witness`).

**Claim scope.** A `QUALIFIED` verdict says: the recorder holding the key emitted exactly these
events, nothing in the witnessed git range and nothing in the witnessed human-message ledger is
missing from them, and the recorded causal graph satisfies P1-P3 and the thresholds. It does not
say the recorder itself saw every human act (a human channel outside the message ledger is
outside the witness), nor that the key was not shared with the judged party, nor that the git
committer clock is honest (it is the anchor, see Residuals).

**Residuals.** Inside a sealed envelope, whether a declared `Objective` is a goal or a script
(a script in one scalar attribute, or one object per type cited invariantly) remains reviewer
judgement relative to `envelope_sha256`; the court pins the envelope's content hash so that
judgement is about named bytes. Human channels not in the message ledger and key custody are
out of scope (`UNKNOWN`), not claims of absence. The epoch anchor is the git committer clock,
which the committing party sets at commit time (`GIT_COMMITTER_DATE`): a judged party that
forges committer dates when committing can still move the epoch; a forge receive time (push or
check-run timestamps) or a recorder-stamped clock is the stronger anchor and is
`UNSUPPORTED(gap: forge-clock anchor)` here. A witnessed human message between the base commit
and the first witnessed commit can be sealed as pre-epoch; it is then judged by P1-P3 as a
pre-epoch human act (it may only supply the frozen envelope).

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
reason carries a `broken_term` (Chatman taxonomy) and an RFC-0004 §39 failure class. Since r9 the
receipt also carries `rules_consistent`, `envelope_sha256`, `claim` and `sealing` (the seal
report: profile, ledger sha256, key ids, sealed, complete, witnesses, records, tail digest).
Exit codes: `0` qualified (sealed, complete, every rule holds -- the only route to 0), `3` not
qualified or `CONSISTENT_UNDER_ASSUMED_COMPLETENESS` (typed; distinguished by `verdict`), `2`
refused (malformed or forged log, or a sealed log failing chain, signature, bijection or
completeness).

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
`docs/rfcs/aloop/ALOOP-001-chatman-root-crown-v26.9.25.json` (regenerated by the r9 court; the
trace is unsealed, `sealing.sealed = false`, so even a rules pass would be capped at
`CONSISTENT_UNDER_ASSUMED_COMPLETENESS`): `NOT_QUALIFIED`, `rules_consistent = false`, ALD 0,
episode `FAILED` with `UNRECEIPTED_ACTUATION` (the inter-run commit and the tag creation have no
receipt in the admitted inputs), `UNAUTHORIZED_ACTUATION`, `UNATTRIBUTED_EXOGENOUS_CAUSE` (since r8: post-epoch links to objects neither
produced in the episode nor declared by its `episode.start`), `HUMAN_CAUSALITY_AFTER_EPOCH` (the release-crown environment approval that the
tag decision names) and `AUTOMATION_NOT_AUTONOMY` (receipts do feed the next observation through
`previous_receipt_digest`, but no WorkOrder is ever issued). The verdict is about the recorded
process, not about the tag's release standing.

## Non-goals

- Proving that any real system is autonomous from synthetic fixtures (they are a falsifier
  corpus for the court only).
- Granting authority: court verdicts carry `authority = NONE`.
- Treating OCEL as proof: it is the flight recorder; a log that omits a human act is a forged
  log. Since r9 omissions are detected only against independent observation -- the sealed
  recorder's external witnesses (git rev-list, human-message ledger) -- never from the log's own
  bytes; an unsealed log is at most `CONSISTENT_UNDER_ASSUMED_COMPLETENESS`.

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
envelope, leaves the work orders citing it self-generated; if a post-epoch machine event links
an object that is neither output by an earlier machine event of its episode (strictly earlier in
time) nor frozen envelope state -- a producer-less per-iteration object reaching the next action
through a hop between `receipt[n]` and the reobserve, a post-epoch attribute change on the
envelope, a reobserve timestamped equal to `receipt[n]`, an undeclared pre-epoch script -- and
the episode is not `FAILED` (P1); if a Human reached over any E2O qualifier (`evidence`,
`provider`), any O2O relation to an object of any type, or an attribute change co-timed with a
human act after `t0`, leaves the episode anything but `ASSISTED` (P2); or if a forked next
action (one reobserve rooting two work orders), an indexed envelope (a family of bound
`Objective`s, whatever the candidate count) or an envelope attribute holding an ordered value
history still counts as a transition (P3); if a declared envelope object indexed per iteration
-- a same-typed family of any type, an out-of-vocabulary attribute key, or an object cited by
some occurrences of an activity and not others -- reaches any post-epoch event (an actuation,
`execution.start`, `gap.detect`, a work order under `evidence`) and the episode is not `FAILED`
(P1+P3, r9); if an attribute value no event produces reaches a post-epoch event and the episode
is not `FAILED` (P1, r9), or follows a post-epoch human act and the episode is not `ASSISTED`
(P2, r9); or if two runs over the same bytes produce different receipts. Each has a mutant in
the regenerated corpus whose sha256 is committed in
`tests/aloop/fixtures/synthetic/MANIFEST.json` (65 mutants, 65 killed by the rules:
`rules_consistent = false` for each). Disabling any one of P1,
P2, P3 lets at least one mutant qualify again.

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

Repair round 8 (court version `aloop-001/v26.9.25-r8`) replaced the channel-by-channel
exemptions with the fail-closed provenance law (P1, P2, P3 above) after the finish adversarial
court r3 refused round 7 with J1: a post-epoch `Objective` O2O `boundTo` the Human, produced by
no event, caused every reobserve and returned exit 0 `QUALIFIED`, ALD 100 (the reobserve was a
segment stop and the O2O walk never entered an `Objective`). Eleven new mutants -- J1, J1b (the
same with an `Authority`), J2 (a producer-less script consumed by a machine `reconcile` between
`receipt[n]` and the reobserve), J3 (r7's X1 plus candidate inflation), J3c (inflation alone, a
forked next action), F6 (post-epoch human memo under `evidence`), F9 (post-epoch envelope
attribute change, no event), H7 (the same change co-timed with a human act), H8 (human-picked
`Provider` under `provider`), G7 (reobserve timestamp equal to the receipt's) and the r7
script-in-attributes residual (a 101-value history on the bound goal's attribute) -- each
return exit 0 `QUALIFIED`, ALD 100 on the r7 court (`faaad7ab`) and exit 3 `NOT_QUALIFIED` on
r8. Ablation: without P1, J2 and F9 qualify; without P2, F6 and H8 qualify; without P3, J3, J3c,
X1, H1-H3, X5 and script-in-attributes qualify. P1 refuses four earlier mutants before the cone
law runs (the pre-epoch machine and human scripts `episode.start` never declares); they now list
`UNATTRIBUTED_EXOGENOUS_CAUSE` instead of `STALE_REOBSERVE`. A post-epoch human act on the
envelope policy itself now cuts the chain at 0, not 49: the policy is no longer frozen for any
work order. The positive log genuinely violated P1: its first provider (`prov-claude`) entered
at the first `provider.select` with no producer and no declaration. `episode.start` now declares
it under `provider`; the positive fixture's bytes change for that one link and it stays
`QUALIFIED`, `AUTONOMOUS`, ALD 100. Controls still qualify: the envelope lease, the goal cited by
every work order, the objective re-read by every reobserve, a single-valued goal description.
Known residual, not closed here: a script in one scalar attribute value of a single-valued
envelope object (evidence ceiling above).

Repair round 9 (court version `aloop-001/v26.9.25-r9`) closed the finish adversarial attacks-r8
K1, K4b, K8 and K9 (plus K3, K4, K5, K6), each exit 0 `QUALIFIED`, `AUTONOMOUS`, ALD 100 on
r8. K1 (`admission_vacuous`): a pre-epoch human act minted 101 per-iteration `Objective`
steps, `episode.start` declared them, and `actuate[n]` (or `execution.start`, `provider.select`,
`commit`) took step-n as input -- r8 applied its indexed clause only inside the cone of
`workorder.issue`, and its P1 frozen exemption never consulted it. K4b (`admission_vacuous`):
the same with `Plan` steps, outside the `Objective`/`Authority` set r8 indexed, cited by every
work order under the non-causal `evidence` qualifier. K8 (`mu_on_O`): a post-epoch human act
outputs a no-op memo and 1 ns later a machine-produced candidate gains `choice = human-n`; r8
caught only a change co-timed to the nanosecond. K9 (`mu_on_O`): the same change with no human
act; r8 checked modification only on envelope objects. Round 9 closes P1-P3 over the whole
episode (indexed over every declared object, closed attribute-key vocabulary, per-activity
citation invariance; the P1 exemption is frozen AND unindexed AND invariant) and over OCEL
`ObjectChange` values (attributed only at the producing machine event; unattributed after a
human act is P2 human contact). Nine new mutants -- K1 on `actuate` and on `execution.start`,
K3 (machine `Plan` script into `execution.start`), K4b, K5 (step-n on `gap.detect` under
`evidence`), K6 (101 attribute keys on the goal), a five-object script of five distinct types
(the varying clause alone), K8 and K9 -- each return exit 0 `QUALIFIED`, ALD 100 on the r7
(`faaad7ab`) and r8 (`a44b03a1`) courts and exit 3 `NOT_QUALIFIED` on r9 (K8 `ASSISTED`, the
rest `FAILED` `UNATTRIBUTED_EXOGENOUS_CAUSE`). Six earlier mutants (r7 H1/H2/H3/X1, r8 J3 and
script-in-attributes) are now refused by P1 before the cone law runs and list
`UNATTRIBUTED_EXOGENOUS_CAUSE` instead of `STALE_REOBSERVE`. Ablation: without P1, K1, K3, K4b,
K5, K9, the distinct-types script, F9 and J2 qualify; without P2, F6 and H8 qualify; without
P3, every K script, K6, J3, J3c, H1-H3, X1, X5 and script-in-attributes qualify. The positive
log does not violate P1-P3 (`rules_consistent`, rule class `AUTONOMOUS`, ALD 100); unsealed it
is `CONSISTENT_UNDER_ASSUMED_COMPLETENESS` (exit 3), and its sealed variant bound to 101 real git
commits (dated by their committer clock) with an empty human ledger is `QUALIFIED` (exit 0). Controls still pass every
rule: every `actuate` citing the goal (an invariant citation), a candidate attribute timed
exactly at its producing machine event, a single in-vocabulary goal `description`.

The same round adds the sealed-recorder falsifiers (`tests/aloop/test_aloop_seal.py`, real git
repositories and a random recorder key per test): the architecture is falsified if an unsealed
log exits 0 or classifies an episode `AUTONOMOUS`; if a sealed log qualifies with a post-t0
human message the log omits, an event deleted or an object edited after sealing, a record's
`previous_digest` forged, a record dropped, a wrong verification key, a re-seal by the author
under its own key, a git commit no sealed event produced (synthetic and real `git rev-list`), a
duplicated commit event, a commit claim outside the witnessed range, a commit claim naming an
unwitnessed repository, the recorder key inside the log, or a witnessed human message sealed
under the wrong time or position: a post-t0 message carried by a new pre-epoch event (A1b),
relabelled onto the pre-epoch goal act (A3), two post-t0 messages absorbed by one event (A4), a
post-t0 message sealed one nanosecond off its witnessed time, or a message at exactly `t0`
omitted (A5); or a log clock off the git clock: the whole log shifted one day to hide a mid-loop
message (C2, API and CLI), the same shift with the message sealed pre-epoch at its true time,
`t0` after the first commit, `t0` before the base commit, a commit event one second off its
committer time, or a pre-epoch witnessed message omitted. Each of these 25 is `REFUSED` (exit
2) with its typed code; a non-empty human ledger without the git clock is never complete (exit
3); the sealed positive exits 0, also with its pre-epoch goal message sealed on `h-pre`;
sealed without witnesses it is `CONSISTENT_UNDER_ASSUMED_COMPLETENESS`; four sealed, complete
K-mutants stay `NOT_QUALIFIED` (sealing certifies authorship and completeness, not the rules).
K-mutant witness (`docs/rfcs/aloop/ALOOP-001-r9-k-mutant-witness.json`): the nine K-class
synthetic mutants exit 0 `QUALIFIED` on the r8 court (`a44b03a1`) and are rule failures on r9.
