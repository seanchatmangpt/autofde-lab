# AutoFDE Lab v26.9.16 — Architecture Requirements Document

> **AutoFDE Lab v26.9.16 closes the local machine-experience loop: admitted semantic change can trigger deterministic Knowledge Hooks, synthesize non-authoritative intent, traverse explicit authority and BRCE, produce receipted consequence, and feed resulting semantic change back into a bounded reflex until quiescence. The Lab remains EXPLORE/qualification infrastructure; production authority remains outside it.**

**Version:** `v26.9.16`
**Status:** Tag Candidate
**Architecture:** Semantic Machine Experience Qualification and Compilation

---

## 1. Architectural Objective

AutoFDE Lab SHALL implement the EXPLORE side of the canonical AutoFDE architecture:

$$
\boxed{
PublicOntology
\rightarrow
O
\rightarrow
O^*
\rightarrow
Explore
\rightarrow
Falsify
\rightarrow
Admit
\rightarrow
Plan
\rightarrow
Manufacture
\rightarrow
Qualify
}
$$

and SHALL export only sufficiently admitted/qualified cognition toward manufacture and production.

The Lab MUST preserve the architectural distinction:

$$
\boxed{
EXPLORE\neq EXPLOIT
}
$$

---

## 2. System Topology

```text
                    ┌─────────────────────────────┐
                    │         autofde-lab         │
                    │                             │
Observation ───────►│ Admission                   │
                    │ GraphLaw                    │
                    │ Knowledge Hooks             │
                    │ Planner League              │
                    │ FOND/HDDL                   │
                    │ DSPy/TPOT2/UNKNOWN search   │
                    │ GymAct / falsification      │
                    │ OCEL / evidence             │
                    │ semantic qualification      │
                    └──────────────┬──────────────┘
                                   │
                            admitted cognition
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │            ggen             │
                    │ deterministic manufacture   │
                    └──────────────┬──────────────┘
                                   │
                            immutable artifact
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │       autofde / BRCE        │
                    │ EXPLOIT / Authority / DO    │
                    │ Receipt / Replay            │
                    └─────────────────────────────┘
```

---

## 3. Canonical Semantic State

Candidate observations SHALL begin as:

$$
O
$$

Admission SHALL produce:

$$
O^*=\alpha_B(O)
$$

Only \(O^*\) SHALL participate in canonical deterministic semantic operation.

The system SHALL separately represent:

```text
observed
inferred
candidate
admitted
selected
constructed
authorized
executed
changed
verified
refused
blocked
unsupported
```

No state transition SHALL silently collapse these distinctions.

---

## 4. GraphLaw Architecture

GraphLaw SHALL serve as the deterministic semantic transition kernel.

Its responsibilities include:

$$
\boxed{
structure
+
invariants
+
closure
+
falsification
+
hook evaluation
+
canonical semantic identity
}
$$

GraphLaw SHALL NOT be an authority broker or consequence engine.

Where WASM is used, the exact executable SHALL be content-addressed.

Host-specific glue MUST NOT become the semantic source of truth.

---

## 5. Knowledge Hook Architecture

A Knowledge Hook SHALL contain enough admitted identity to answer mechanically:

```text
Which hook is this?
Which semantic condition caused evaluation?
Which admitted graph revision was evaluated?
Did it fire?
Which intent was synthesized?
Which receipt records the evaluation?
```

The hook engine SHALL operate over admitted semantic input.

Its output SHALL be:

$$
SemanticIntent
$$

with no ambient authority.

The reference invariant is:

$$
\boxed{
\Delta O^*
\rightarrow
KnowledgeHook
\rightarrow
SemanticIntent
}
$$

not:

$$
\Delta O^*
\rightarrow DO
$$

---

## 6. Reactive Loop Architecture

The reference reflex is:

$$
\boxed{
O^*_t
\xrightarrow{\Delta}
Hook
\xrightarrow{SELECT/CONSTRUCT}
Intent
\xrightarrow{Authority}
BRCE
\xrightarrow{DO}
Receipt
\xrightarrow{}
\Delta O^*_{t+1}
}
$$

A `ReactiveSemanticLoop` SHALL:

* evaluate admitted hooks;
* synthesize intents;
* resolve explicit authority;
* route all consequences through BRCE;
* collect final receipts;
* project resulting receipt/state deltas;
* re-enter hook evaluation when lawful;
* terminate on quiescence or explicit bound.

The cascade MUST enforce:

$$
Depth\le D_{\max}
$$

and SHOULD additionally admit explicit fan-out and parallelism bounds where applicable.

---

## 7. Authority Architecture

Authority SHALL be an explicit relation independent of intelligence.

$$
\frac{\partial Authority}{\partial Intelligence}=0
$$

The Authority Broker SHALL evaluate an exact tuple equivalent to:

$$
(actor,\ action,\ target,\ context,\ grant)
$$

A missing explicit `grant_id` MAY resolve only through deterministic lookup of already registered matching grants.

Lookup SHALL NOT manufacture authority.

---

## 8. BRCE Architecture

BRCE remains the sole consequence-bearing path.

The architectural pipeline is:

$$
SELECT
\rightarrow
CONSTRUCT
\rightarrow
Authority
\rightarrow
PreparedReceipt
\rightarrow
DO
\rightarrow
FinalReceipt
$$

A consequence SHALL NOT execute unless durable receipt preparation succeeds first.

No GraphLaw rule, Knowledge Hook, planner, model, proof, CLI command, or Semantic A2A message may bypass BRCE.

---

## 9. Planner Architecture

Planning projections SHALL be derived from admitted state.

$$
P=\pi_{\mathrm{plan}}(O^*)
$$

The semantic graph remains authoritative.

Plans are disposable projections.

$$
Plan\neq SemanticTruth
$$

$$
Plan\neq Authority
$$

Planner outputs remain candidate-only until the appropriate admission boundary is crossed.

---

## 10. UNKNOWN Architecture

When existing admitted machinery is insufficient:

$$
state=UNKNOWN
$$

UNKNOWN MAY route to:

```text
LLM
DSPy
TPOT2
planner search
RL
theorem prover
synthesis
experiment
GymAct
other bounded discovery
```

The result SHALL return as a candidate.

$$
UNKNOWN
\xrightarrow{Intelligence}
Candidate
\xrightarrow{Admission}
KNOWN
$$

Discovery machinery SHALL NOT self-admit.

---

## 11. Portable Semantic Execution

The cross-runtime target architecture is:

```text
                    same semantic artifact
                            │
                   ┌────────┴────────┐
                   ▼                 ▼
              Runtime A         Runtime B
                   │                 │
                   ▼                 ▼
             GraphLaw WASM     GraphLaw WASM
                   │                 │
                   └────────┬────────┘
                            ▼
                     compare evidence
```

For a conformance fixture:

$$
WASM_A=WASM_B
$$

$$
InputIdentity_A=InputIdentity_B
$$

SHALL imply equivalent admitted semantic outcomes, subject to the supported GraphLaw profile.

The qualification SHALL compare semantic identity/evidence, not presentation formatting.

---

## 12. Semantic A2A Architecture

Within AutoFDE Lab, Semantic A2A SHALL define the qualified machine boundary:

$$
Message
\rightarrow
Candidate
\rightarrow
Admission
\rightarrow
O^*
$$

and never:

$$
Message\rightarrow Fact
$$

The primary Lab concern is preservation of semantic law across boundaries, not messaging convenience.

Therefore Semantic A2A qualification SHOULD test:

$$
\boxed{
SemanticLaw
\times Runtime
\times Host
\times World
\times AuthorityProfile
}
$$

---

## 13. Manufacturing Boundary

Lab results SHALL NOT be copied into production as manually maintained implementations where lawful generation exists.

The target flow is:

$$
O^*
\rightarrow
query
\rightarrow
ggen
\rightarrow
formal\ admission
\rightarrow
runtime
\rightarrow
BRCE
\rightarrow
receipt
$$

Generated artifacts are projections.

Correction occurs in:

$$
O^*
$$

or:

$$
\mu
$$

not by establishing a second manually edited semantic truth.

---

## 14. Evidence Architecture

Evidence SHALL preserve exact subject identity.

At minimum a qualification receipt SHOULD identify:

```text
repository
branch
exact SHA
tag
semantic revision
GraphLaw revision
WASM digest where applicable
hook identity
planner/domain identity
authority profile
validator identities
commands
exit codes
test counts
runtime identity
observed receipt identities
evidence class
```

The following remain non-equivalent:

$$
LocalTest\neq HostedCI
$$

$$
HostedCI\neq Deployment
$$

$$
Build\neq RuntimeAlive
$$

$$
RuntimeAlive\neq Publication
$$

$$
Publication\neq Merge
$$

---

## 15. Release Architecture Invariants

The `v26.9.16` exact tagged tree SHALL preserve:

$$
\boxed{
Hook\neq DO
}
$$

$$
\boxed{
Intent\neq Authority
}
$$

$$
\boxed{
Planner\neq Authority
}
$$

$$
\boxed{
Agent\neq Authority
}
$$

$$
\boxed{
SELECT\neq CONSTRUCT\neq DO
}
$$

$$
\boxed{
Received\neq Admitted
}
$$

$$
\boxed{
LLMOutput\Rightarrow Candidate
}
$$

$$
\boxed{
Executed\Rightarrow Authorized
}
$$

$$
\boxed{
Executed\Rightarrow PreparedReceipt
}
$$

$$
\boxed{
Receipt\rightarrow ReplayableEvidence
}
$$
