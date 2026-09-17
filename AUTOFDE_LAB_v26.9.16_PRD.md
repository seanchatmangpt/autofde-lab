# AutoFDE Lab v26.9.16 — Product Requirements Document

> **AutoFDE Lab v26.9.16 closes the local machine-experience loop: admitted semantic change can trigger deterministic Knowledge Hooks, synthesize non-authoritative intent, traverse explicit authority and BRCE, produce receipted consequence, and feed resulting semantic change back into a bounded reflex until quiescence. The Lab remains EXPLORE/qualification infrastructure; production authority remains outside it.**

**Version:** `v26.9.16`
**Status:** Tag Candidate
**Product:** `autofde-lab`
**Release theme:** **Machine Experience → Semantic Reflex**

---

## 1. Product Thesis

AutoFDE Lab exists to reduce the amount of intelligence required by future executions.

Its primary transformation is:

$$
\boxed{
UNKNOWN
\rightarrow
EXPLORE
\rightarrow
FALSIFY
\rightarrow
ADMIT
\rightarrow
FORMALIZE
\rightarrow
MANUFACTURE
\rightarrow
MACHINE
}
$$

v26.9.16 extends this into:

$$
\boxed{
UNKNOWN
\rightarrow
KNOWN
\rightarrow
FORMALIZED
\rightarrow
PORTABLE
\rightarrow
REACTIVE
\rightarrow
AUTONOMIC
}
$$

A successfully solved class SHOULD cease requiring equivalent exploratory cognition.

The desired long-run relation is:

$$
\boxed{
\frac{\partial I_{\mathrm{required}}}
{\partial MachineExperience}<0
}
$$

and, where deterministic machinery is sufficient:

$$
Allocation_{LLM}(KNOWN)=0
$$

---

## 2. Product Boundary

`autofde-lab` is the **EXPLORE / qualification environment**.

It MAY contain:

* planners and solver leagues;
* DSPy, LLMs, RL, TPOT2 and other exploratory machinery;
* GymAct and real-world falsification;
* ForwardBench and benchmark environments;
* process mining / OCEL;
* PSRO, self-play and cross-play;
* GraphLaw;
* Semantic A2A qualification machinery;
* Knowledge Hooks;
* experiment design;
* formal planning;
* synthesis;
* falsifiers;
* semantic admission;
* portable execution qualification.

It MUST NOT become production authority.

The canonical deployment topology remains:

$$
\boxed{
autofde\text{-}lab
\xrightarrow{\text{qualified cognition}}
ggen
\xrightarrow{\text{deterministic manufacture}}
autofde/BRCE
}
$$

Production MUST NOT require runtime access to Lab, DSPy, GymAct Python, general-purpose LLM reasoning, exploratory planners, or other EXPLORE machinery.

---

## 3. v26.9.16 Product Objective

v26.9.16 SHALL demonstrate that AutoFDE Lab can compile observed semantic experience into a **bounded autonomic reflex**:

$$
\boxed{
O^*
\xrightarrow{\Delta}
KnowledgeHook
\rightarrow
SemanticIntent
\rightarrow
Authority
\rightarrow
BRCE
\rightarrow
DO
\rightarrow
Receipt
\rightarrow
\Delta O^*
}
$$

The loop SHALL terminate through:

$$
Quiescence
$$

or:

$$
Depth=D_{\max}
$$

No hook SHALL itself possess consequence authority.

---

## 4. User / Machine Outcome

A machine operating through AutoFDE Lab SHOULD progressively experience:

```text
First occurrence:
UNKNOWN
→ expensive exploration
→ candidate solution
→ falsification
→ admission

Subsequent occurrences:
known semantic class
→ admitted hook/rule/plan
→ deterministic route
→ receipt
```

The product therefore optimizes for **avoided rediscovery**, not maximum runtime intelligence.

---

## 5. Required v26.9.16 Capabilities

### 5.1 Semantic Admission

The Lab SHALL support candidate-to-admitted transitions over semantic state with fail-closed validation.

$$
Received\neq Admitted
$$

$$
Candidate\neq Fact
$$

Invalid or unverifiable semantic objects MUST NOT acquire standing.

### 5.2 GraphLaw Bridge

The Lab SHALL expose GraphLaw as an executable semantic kernel capable of supporting at least:

```text
validation
canonical graph identity
semantic hook evaluation
content hashing
GraphLaw implementation identity
```

Portable execution SHOULD use the existing `praxis-graphlaw-wasm` substrate where applicable.

### 5.3 Knowledge Hooks

A Knowledge Hook SHALL map an admitted graph transition to candidate operational intent:

$$
Hook:(O_t^*,\Delta O^*)\rightarrow Intent
$$

and SHALL preserve:

$$
Hook\neq DO
$$

$$
Intent\neq Authority
$$

Hook evaluation SHALL be deterministic for identical admitted inputs and hook identity.

### 5.4 Reactive Semantic Loop

The Lab SHALL expose a bounded loop:

$$
O^*
\rightarrow
\Delta
\rightarrow
Hook
\rightarrow
Intent
\rightarrow
Authority
\rightarrow
BRCE
\rightarrow
Receipt
\rightarrow
\Delta'
$$

Receipt-derived deltas MAY trigger additional admitted hooks.

Recursion MUST remain bounded.

### 5.5 Authority Separation

The following MUST remain structurally distinct:

$$
Planner\neq Policy\neq Role\neq Agent\neq Authority
$$

and:

$$
Hook\neq Authority
$$

$$
Plan\neq Authority
$$

$$
Proof\neq Authority
$$

$$
SemanticIntent\neq Authority
$$

### 5.6 Zero Unreceipted Actuation

Every consequence-bearing path SHALL traverse BRCE.

$$
Attempted(a)\Rightarrow PreparedReceipt(a)
$$

No Lab subsystem MAY introduce a second DO path.

### 5.7 Formal Planning

The Lab SHALL continue routing known planning problems to appropriate formal machinery, including FOND/HDDL, PDDL-family planners, SAT/SMT/CP or other admitted solvers where applicable.

General inference SHALL NOT replace a known formal solver merely because it is available.

### 5.8 Semantic A2A Qualification

Semantic A2A inside `autofde-lab` SHALL be treated as a **qualification subject**, not as an ambient authority mechanism.

The Lab SHOULD be capable of testing preservation of:

$$
Identity
\land Admission
\land Closure
\land Planning
\land Authority
\land Receipt
$$

across heterogeneous runtimes and hosts.

### 5.9 Cross-Runtime Semantic Portability

The qualification target SHALL be:

$$
Runtime_A\neq Runtime_B
$$

while:

$$
SemanticArtifact_A=SemanticArtifact_B
$$

and, for admitted fixtures:

$$
Admission_A=Admission_B
$$

$$
CanonicalPostState_A=CanonicalPostState_B
$$

Negative fixtures SHALL also preserve equivalent refusal behavior.

### 5.10 Typed Non-Success

The Lab SHALL retain distinct terminal states:

```text
UNKNOWN
PARTIAL_ALIVE
ALIVE
BLOCKED
BUILD_BROKEN
UNSUPPORTED
REFUSED
```

`UNKNOWN` SHALL NOT imply admission.

`UNSUPPORTED` SHALL NOT imply refusal.

`BLOCKED` SHALL NOT imply semantic invalidity.

---

## 6. Machine Experience Compilation

The preferred successful learning path is:

$$
\boxed{
UNKNOWN
\rightarrow
CandidateKnowledge
\rightarrow
Admission
\rightarrow
\{
Ontology,
Shape,
Rule,
Hook,
Plan,
Generator
\}
}
$$

A qualified result SHOULD reduce future reliance on the discovery machinery that originally produced it.

The Lab SHALL therefore measure success partly by whether repeated inference is replaced by:

```text
reuse
→ compose
→ extend
→ invent
```

in that order.

---

## 7. Planner League Role

Planner League remains **EXPLORE machinery**, not the production architecture.

It exists to determine which bounded policy succeeds under which admitted world:

$$
Policy=
Planner
\times Parameters
\times Objective
\times ObservationProjection
\times ActionProjection
$$

Its outputs are candidates until admitted.

Planner League success SHOULD eventually permit policy knowledge to compile downward into deterministic planning, hooks, rules, schedules, or manufactured operators.

---

## 8. GymAct Role

GymAct remains the real-world / provider-physics falsification surface.

It MUST NOT grant production authority to solver output.

The intended relation remains:

$$
PlannerCandidate
\rightarrow
GymAct
\rightarrow
ObservedExecution
\rightarrow
IndependentVerification
\rightarrow
Evidence
$$

not:

$$
Planner\rightarrow ProductionAuthority
$$

---

## 9. Product Acceptance Criteria for v26.9.16

The tag is product-complete when the exact tagged subject can demonstrate:

1. semantic admission with fail-closed refusal;
2. GraphLaw bridge execution;
3. Knowledge Hook → `SemanticIntent` generation with no side effect;
4. Authority Broker separation;
5. BRCE-only consequence execution;
6. durable receipt before consequence;
7. receipt-derived semantic delta;
8. bounded reactive cascade;
9. observed quiescence;
10. deterministic CLI execution of hook evaluation and reflex;
11. passing repository-native SA2A/Knowledge Hook qualification;
12. exact Git tag → exact commit identity;
13. release receipt that separates local evidence from CI, publication and production standing.

Current supplied evidence includes **101 passing `tests/sa2a/` tests**, a locally observed CLI reflex reaching `EXECUTED` and quiescence, and a successful native GraphLaw release build.

The tag itself SHALL NOT inherit standing merely from those pre-tag observations. Exact-tag verification is required.

---

## 10. Product Falsifiers

The v26.9.16 thesis is falsified for a tested subject if any of the following occurs:

```text
Hook directly actuates.
Intent self-grants authority.
A consequence occurs before prepared receipt.
A receipt cannot identify the semantic subject that caused it.
A cascade exceeds its declared depth/fan-out bound.
A failed admission mutates canonical state.
Equivalent admitted graph inputs produce host-dependent semantic identity.
A known formal problem silently routes back to unbounded inference.
A solved semantic class requires equivalent exploratory reasoning indefinitely.
Production execution depends on autofde-lab being online.
```
