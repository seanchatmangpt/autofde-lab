# RFC-SA2A-002 v26.9.16

## Chicago Conformance, Falsification, Benchmark, and OCEL v2 Qualification Standard for Semantic A2A Systems

**Status:** Proposed Standard  
**Version:** v26.9.16  
**Category:** Protocol Conformance / Falsification / Process Evidence / Benchmarking  
**Companion specification:** RFC-SA2A-001 v26.9.16 — *Semantic A2A: Admitted Semantic Interoperation for Machine-to-Machine Systems*  
**Intended audience:** Implementers of Semantic A2A peers, semantic runtimes, planners, authority brokers, consequence engines, process-intelligence systems, conformance courts, benchmark harnesses, verifier authors, release engineers, and machine-to-machine platform operators.

> This document uses RFC-style normative language but is not an IETF publication.

---

# Abstract

RFC-SA2A-001 defines the semantic and consequence architecture of Semantic A2A. This companion specification defines **how an implementation earns conformance standing**.

A Semantic A2A implementation MUST NOT be considered conformant merely because its code appears to implement the required architecture, because a unit test passes, because a planner generated a valid plan, because a validator returned success, or because an implementation can serialize a Semantic Envelope.

Conformance is earned by executing a bounded set of **Chicago qualification courts** that attempt to falsify the architecture against the exact implementation subject.

The governing relation is:

```math
\boxed{
Conformant(S)
\Rightarrow
ExactIdentity(S)
\land
FalsifiersAttempted(S)
\land
ForbiddenStandingAbsent(S)
\land
RequiredConsequencesObserved(S)
\land
IndependentEvidence(S)
}
```

For consequence-bearing profiles, the court additionally requires:

```math
\boxed{
Attempted(DO)
\Rightarrow
Authorized
\land
PreparedReceipt
\land
BRCE
\land
IndependentPostcondition
}
```

For Strict conformance, known recurring work MUST demonstrate that admitted machine experience can execute without equivalent exploratory intelligence:

```math
\boxed{
KNOWN \Rightarrow Allocation_{LLM}=0
}
```

where deterministic admitted machinery is sufficient.

The canonical process-evidence format for the court is **OCEL 2.0**. OCEL evidence MUST be generated from the actual execution under test. A conformance test MUST NOT pass by comparing the produced OCEL to a predeclared “golden” execution trace. The court specifies invariants and falsifiers; the process history is an observation.

The central Chicago rule is:

```math
\boxed{
PASS = AttemptObserved \land ViolationDidNotAcquireStanding
}
```

and never:

```math
PASS = \neg ObservedViolation
```

because absence of evidence may mean the relevant machinery never ran.

# 1. Normative Language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** are normative.

Normative requirements in RFC-SA2A-001 remain authoritative. This document does not weaken them. It defines the minimum evidence required to claim that an exact implementation subject satisfies them.

# 2. Relationship to RFC-SA2A-001

RFC-SA2A-001 defines the architecture:

```math
\boxed{
O \xrightarrow{\alpha_B} O^*
\rightarrow SELECT
\rightarrow CONSTRUCT
\rightarrow Authority
\rightarrow BRCE
\rightarrow DO
\rightarrow Receipt
}
```

This document defines the qualification relation:

```math
\boxed{
Implementation
\rightarrow Falsification
\rightarrow Observation
\rightarrow OCEL
\rightarrow IndependentVerification
\rightarrow Standing
}
```

A test in this document MUST be interpreted as a test of the corresponding RFC-SA2A-001 invariant, not as an independent implementation preference.

# 3. Conformance Objective

The purpose of conformance testing is not to maximize the number of green tests.

The purpose is to answer:

```text
Can a concrete counterexample cross the boundary this RFC claims is closed?
```

A newly discovered defect is therefore a successful falsification run, even though the implementation has failed qualification.

A conforming development process SHOULD follow:

```math
\boxed{
Falsifier
\rightarrow Counterexample
\rightarrow BoundaryDiscovery
\rightarrow Repair
\rightarrow PermanentGuard
\rightarrow Requalification
}
```

A falsifier MUST NOT be weakened merely to restore a green suite.

# 4. Terms

For this specification:

- **SUT** — the exact System Under Test.
- **Court** — the machinery that drives qualification and determines standing from evidence.
- **Observer** — a component that records process evidence independently of the component whose self-report is under test.
- **Actuator** — the component that performs a consequence-bearing external mutation.
- **Independent verifier** — a component that observes post-state without relying solely on actuator return values.
- **Exact subject** — repository/revision/artifact/runtime/configuration identities sufficient to distinguish the executed implementation from neighboring revisions.
- **Falsifier** — an executable attempt to violate a normative invariant.
- **Counterexample** — an input, schedule, fault, state, or sequence that would demonstrate violation of an invariant if accepted.
- **AttemptObserved** — positive evidence that the violating path was actually exercised.
- **Falsifier killed** — the violation was attempted and was refused or contained before forbidden standing or consequence was obtained.
- **Falsifier survived** — the violating input or transition obtained standing or consequence that the RFC prohibits.
- **Blind evidence** — process evidence whose complete trace is not prescribed to the SUT in advance.
- **Chicago qualification** — an exact-subject falsification court using real load-bearing collaborators and independent evidence.
- **Chicago Crown** — successful completion of all gates required by the claimed conformance profile.
- **Fresh consumer** — a process or verifier instance that has no access to producer memory and reconstructs standing from durable artifacts only.
- **Benchmark** — a measured qualification run whose environment and exact subject identity are recorded.
- **OCEL** — Object-Centric Event Log 2.0, used as the canonical process-evidence exchange format in this specification.

# 5. Exact-Subject Conformance

Conformance attaches to an exact subject, not to a repository name, branch label, product family, organization, or architecture diagram.

At minimum, an exact subject SHOULD identify:

```text
repository or package identity
source revision / commit digest
release or tag identity, when used
semantic profile version
root-manifest digest
validator / rule-set identities
planner/domain identities, when applicable
manufacturer identity, when applicable
executable artifact digest
runtime identity
configuration digest
relevant environment identity
```

For a release tag:

```math
\boxed{TagCommit = VerifiedCommit}
```

MUST hold.

A mutable branch name by itself MUST NOT confer release conformance.

# 6. Release Identity Discipline

A published final conformance tag SHOULD be immutable.

A project MAY use mutable candidate references such as:

```text
v26.9.16-rc1
v26.9.16-candidate
refs/heads/qualification
```

before qualification.

Once a final tag is used as a conformance identity, moving that tag SHOULD be treated as invalidating prior standing unless all dependent receipts are explicitly revision-bound and the prior identity remains reconstructible.

# 7. Court Roles

A Chicago court distinguishes at least the following roles:

```text
Stimulus / Falsifier Generator
System Under Test
Actuator
Independent Postcondition Verifier
Process Observer
OCEL Validator
Conformance Query Engine
Standing Issuer
```

One implementation MAY host more than one role, but consequence-bearing profiles SHOULD minimize role collapse.

The component whose claim is being verified MUST NOT be the only source of evidence for that claim.

# 8. Anti-Collusion Requirement

The court MUST contain at least one independently implemented or independently state-reading boundary for every consequence claim.

The following is insufficient:

```text
Actuator says success
→ test asserts actuator returned success
```

The required pattern is:

```math
ActuatorReport
\neq
PostconditionObservation
```

For example, a filesystem actuator MAY be verified by a separately instantiated disk reader; a database mutation MAY be verified by an independent query path; an HTTP consequence MAY be verified through the resulting remote state rather than the request response alone.

# 9. Real Collaborator Rule

A Chicago qualification court MUST exercise the load-bearing collaborator whose semantics establish the claim.

If the claim is “the WASM semantic kernel executes identically across two hosts,” both hosts MUST execute the actual WASM artifact.

If the claim is “BRCE prevents unreceipted actuation,” the consequence path MUST traverse the real consequence boundary.

If the claim is “authority fails closed,” the real authority decision path MUST be invoked.

A substitute that bypasses the behavior being qualified invalidates the corresponding claim.

# 10. Zero-Mock Rule

For Chicago Crown gates, the load-bearing path MUST NOT depend on `Mock`, `MagicMock`, `unittest.mock`, monkeypatching, fake broker responses, fake durable storage, or an equivalent test double in place of the component being qualified.

Mocks MAY be used in lower-level unit tests.

Mocks MUST NOT be used as the sole evidence for Chicago standing.

Fault injection is permitted when it changes the environment around a real component rather than replacing the component whose boundary is under test.

# 11. Falsifier Semantics

Each mandatory falsification test MUST declare:

```text
Invariant under attack
Exact subject
Stimulus / mutation
Boundary expected to decide
Forbidden standing or consequence
Positive evidence that the attack was attempted
Evidence used to determine whether it survived
```

The test MUST be written so that removing the targeted guard would cause the falsifier to survive.

A falsification test that continues to pass after the target guard is deleted is presumed vacuous until proven otherwise.

# 12. Attempt-Observed Rule

For every negative conformance test:

```math
\boxed{
PASS = AttemptObserved \land ForbiddenOutcomeAbsent
}
```

The court MUST positively establish that the relevant input reached the boundary under test.

Examples of invalid evidence include:

- no actuation occurred because the test never constructed a request;
- no hook fired because hook evaluation never ran;
- no authority was granted because the broker process was absent and the request never reached it;
- no replay divergence occurred because replay was never attempted;
- no LLM tokens were consumed because the known-class route never executed.

“Nothing bad happened” is not sufficient evidence.

# 13. Blind Evidence Principle

A Chicago process-evidence run MUST be blind with respect to its complete execution trace.

The test author MAY specify:

- the invariant;
- the counterexample to attempt;
- the evidence question to ask after execution;
- the required independence boundaries.

The test author MUST NOT require the SUT to emit one exact predeclared OCEL event sequence merely to satisfy conformance.

The execution history is evidence to be observed, not an answer key to be copied.

# 14. Anti-Oracle Rule

A conformance suite MUST NOT contain a golden OCEL artifact representing the one accepted process history for a falsification test.

The following are prohibited as the primary conformance oracle:

```text
byte-for-byte comparison against a golden OCEL execution file
snapshotting the entire expected event list
hard-coding exact event counts when the invariant does not require them
hard-coding exact timestamps
requiring one implementation-specific event naming scheme
requiring incidental internal steps not mandated by RFC-SA2A-001
```

A golden artifact MAY be used solely to test an OCEL parser or serializer, provided it is not used to establish Semantic A2A process conformance.

# 15. OCEL 2.0 Process Evidence

Chicago process evidence MUST be exportable as valid OCEL 2.0 in at least one standard serialization supported by the OCEL specification, such as JSON, XML, or SQLite.

OCEL 2.0 is used because a Semantic A2A execution is inherently object-centric: one event may relate simultaneously to semantic subjects, tasks, plans, authority grants, receipts, artifacts, actors, and external resources.

The court MUST validate the produced OCEL independently of the producer.

Syntactic OCEL validity is necessary but not sufficient for Semantic A2A conformance.

# 16. OCEL Syntax Validation

The produced OCEL artifact MUST pass a validator appropriate to the chosen OCEL 2.0 serialization.

Validation MUST occur after the execution artifact is durably written.

A producer returning an in-memory structure that “could be serialized as OCEL” does not satisfy this requirement.

The validation receipt SHOULD record:

```text
artifact digest
serialization
validator identity/version
validation result
validation timestamp or logical clock
```

# 17. OCEL Semantic Independence

This specification does not prescribe one exact OCEL event vocabulary, object vocabulary, event order, internal activity count, or serializer layout.

Implementations MAY expose different internal process structures while remaining conformant.

The court MUST instead determine whether the observed log supports or refutes the required process predicates.

Where implementation-specific event or object types are used, the observer or court MAY maintain an admitted mapping from those types to Semantic A2A concepts. Such a mapping MUST be versioned and fixed before the run whose evidence it interprets.

# 18. Evidence Source Independence

For consequence-bearing tests, the process observer SHOULD consume evidence from a surface distinct from the actuator’s direct return value.

A reference topology is:

```text
falsifier
  ↓
real SA2A execution
  ↓
receipts / telemetry / state changes
  ↓
independent process observer
  ↓
OCEL 2.0
  ↓
conformance queries
```

A reference implementation MAY use `beam4pm` as the process observer while `ash_a2a` participates as a Semantic A2A execution system. This is informative, not a requirement to use those projects.

# 19. Evidence Durability

The OCEL artifact and the receipts used to support standing MUST survive termination of the producer process.

Evidence that exists only in process memory cannot satisfy replay or fresh-consumer gates.

The court SHOULD content-address the final OCEL artifact.

# 20. Time and Ordering

OCEL timestamps MAY be wall-clock timestamps, but conformance reasoning MUST NOT depend solely on unsynchronized wall clocks for causal guarantees.

Where the invariant requires ordering, the court SHOULD use durable causal identity, receipt linkage, monotonic sequence, logical clock, or another admitted ordering relation.

For example:

```math
PreparedReceipt \prec Actuation
```

MUST be established by more than incidental millisecond timestamp ordering if the implementation permits clock ambiguity.

# 21. Evidence Provenance

Every conformance run MUST make it possible to determine:

```text
which exact subject was exercised
which court version ran
which falsifier was applied
which observer generated the OCEL
which OCEL validator checked the artifact
which conformance query set was used
which receipts and external-state observations support the verdict
```

Evidence provenance MUST NOT itself grant execution authority.

# 22. Anti-Vacuity Mutation Check

Each mandatory Chicago guard SHOULD have a mutation test demonstrating that the court detects its removal or inversion.

Examples:

```text
remove prepared-receipt check → Gate 7 MUST fail
return true from authority decision → authority falsifier MUST survive
allow direct canonical mutation → canonical-state falsifier MUST survive
invoke LLM on known route → Gate 12 MUST fail
```

Mutation testing is particularly important for “absence” properties.

# 23. Standing Vocabulary

The court MUST keep at least the following states distinct:

```text
UNKNOWN
PARTIAL_ALIVE
ALIVE
BLOCKED
BUILD_BROKEN
UNSUPPORTED
REFUSED
```

Additionally, a conformance suite MAY use:

```text
FALSIFIER_KILLED
FALSIFIER_SURVIVED
CONFORMANT
NONCONFORMANT
REQUALIFYING
```

`ALIVE` is evidence about observed execution of an exact subject.

`CONFORMANT` is a claim that the exact subject passed the required profile court.

Neither claim automatically implies production deployment, publication, merge, hosted CI, or security completeness.

# 24. Evidence Classes

The following MUST remain distinct:

```math
Inspection \neq Execution
```

```math
LocalTest \neq HostedCI
```

```math
HostedCI \neq Deployment
```

```math
Deployment \neq RuntimeObservation
```

```math
RuntimeObservation \neq Publication
```

```math
Publication \neq Merge
```

A conformance receipt MUST state which evidence classes were actually observed.

# 25. Profile-Specific Qualification

RFC-SA2A-001 defines profiles:

```text
SA2A-CORE
SA2A-LOGIC
SA2A-PLAN
SA2A-DO
SA2A-STRICT
```

A system MUST pass every court applicable to the profile it claims.

A lower profile MUST NOT claim a consequence-bearing gate as “passed” merely because the profile has no DO capability. The gate is **not applicable** unless the implementation structurally lacks that capability.

A system claiming `SA2A-STRICT` MUST pass the full Chicago Crown defined by this document.

# 26. SA2A-CORE Qualification

A `SA2A-CORE` implementation MUST pass courts covering:

- semantic identity;
- candidate versus admitted standing;
- canonical graph identity;
- ShEx structural admission;
- SHACL semantic admission;
- SPARQL falsifiers;
- provenance;
- admission receipts;
- fail-closed behavior;
- transport/serialization invariance for the advertised profile;
- invalid-input refusal;
- OCEL evidence validity for the court itself.

No DO capability is required.

# 27. SA2A-LOGIC Qualification

A `SA2A-LOGIC` implementation MUST pass all CORE courts plus:

- Safe Finite Datalog termination and closure;
- N3 rule standing;
- deterministic closure;
- rule provenance;
- prohibition on side-effecting closure;
- refusal of unadmitted rules;
- non-authority of derivation.

# 28. SA2A-PLAN Qualification

A `SA2A-PLAN` implementation MUST pass all LOGIC courts plus:

- admitted planning projection;
- plan identity;
- known capability references;
- bounded fan-out;
- bounded depth;
- bounded parallelism;
- finite resource envelope;
- planner non-authority;
- invalid-plan refusal;
- candidate-only selection.

# 29. SA2A-DO Qualification

A `SA2A-DO` implementation MUST pass all PLAN courts plus:

- explicit Authority Broker;
- capability/authority separation;
- prepared receipt before consequence;
- sole consequence boundary;
- idempotency/replay protection;
- reconciliation;
- independent postcondition verification;
- offline replay without re-actuation;
- fresh-consumer proof.

A DO implementation cannot be declared conformant solely from mocks or in-memory toy actuators when the claimed production consequence boundary differs materially.

# 30. SA2A-STRICT Qualification

A `SA2A-STRICT` implementation MUST pass every prior court plus:

- no runtime semantic invention on consequential paths;
- meta-admission of validators/rules/planners/manufacturers;
- admitted Root Manifest;
- no direct canonical mutation outside consequence law;
- no LLM authority;
- no LLM on production DO path;
- no unbounded production planning loop;
- explicit finite resource bounds for known work;
- zero equivalent exploratory inference on the qualified KNOWN reflex class.

The last requirement is evaluated by Chicago Gate 12.

# 31. Canonical Chicago Crown

The Strict Chicago Crown consists of twelve gates:

```text
1.  Exact Identity Fenced
2.  Executable World Admitted
3.  Real Load-Bearing Collaborators / Zero Mocks
4.  Planning Candidate-Only
5.  Whole Bounded Plan Preflighted
6.  Autonomous Execution Inside Envelope
7.  Sole DO Boundary / Zero Unreceipted Actuation
8.  Independent Postcondition Observation
9.  Complete Receipt Identity Binding
10. Offline Replay Succeeds
11. Fresh-Consumer Proof Succeeds
12. Zero Runtime Inference on KNOWN
```

All applicable gates MUST pass against the same exact subject identity.

# 32. Gate 1 — Exact Identity Fenced

**Test ID family:** `CHI-ID-*`

The court MUST prove that the executed subject is the subject named in the standing receipt.

Mandatory falsifiers include:

- move the branch while retaining an earlier claimed SHA;
- substitute the executable artifact while leaving source revision unchanged;
- alter the root manifest;
- use a different validator/rule-set revision;
- present a tag resolving to a different commit;
- normalize two distinct runtime identities into the same value.

The court passes only when the mismatch is detected before standing is issued.

The OCEL evidence question is implementation-neutral:

```text
Did the execution that produced the claimed standing remain bound to one exact admitted subject identity?
```

# 33. Gate 2 — Executable World Admitted

**Test ID family:** `CHI-ADM-*`

The court MUST attempt to introduce unadmitted semantic state into the executable world.

Falsifiers SHOULD include:

```text
unadmitted ontology term
structurally invalid RDF object
SHACL-invalid object
unadmitted rule
unadmitted validator
unadmitted planner domain
unadmitted semantic mapping
candidate marked directly as canonical
```

The court passes only when:

```math
AttemptObserved \land \neg Standing(candidate)
```

and canonical state remains unchanged.

# 34. Gate 3 — Real Collaborators / Zero Mocks

**Test ID family:** `CHI-REAL-*`

The court MUST verify that the load-bearing execution uses real collaborators.

The qualification receipt MUST identify the real components used for:

```text
semantic engine
admission pipeline
authority broker
consequence boundary
receipt store
actuator
independent verifier
replay engine
process observer
```

The court MUST fail if a load-bearing collaborator is replaced by a mock during the crown run.

# 35. Gate 4 — Planning Candidate-Only

**Test ID family:** `CHI-PLAN-AUTH-*`

The court MUST attempt to obtain consequence solely from planner output.

Falsifiers include:

- valid plan with no authority;
- optimizer-selected action with no authority;
- proof of safety with no authority;
- signed plan with no authority;
- A2A task assignment with no authority.

The required invariant is:

```math
ValidPlan \not\Rightarrow DO
```

The court passes only if the plan can be observed as selected/constructed while consequence remains unavailable without explicit authority.

# 36. Gate 5 — Whole Bounded Plan Preflighted

**Test ID family:** `CHI-PREFLIGHT-*`

Before consequence, the court MUST establish that the admitted execution envelope includes the required bounds.

Falsifiers SHOULD mutate after or around preflight:

```text
fan-out
cascade depth
parallelism
retry count
resource budget
external request count
financial envelope
authority requirement
semantic subject identity
```

If a post-preflight mutation is not covered by the preflight identity/digest, the gate fails.

The court SHOULD test that every field capable of changing consequence is bound by the preflight evidence.

# 37. Gate 6 — Autonomous Execution Inside Envelope

**Test ID family:** `CHI-AUTO-*`

The court MUST demonstrate that an admitted bounded episode can continue to its lawful terminal condition without caller-by-caller reinterpretation.

For reactive systems, terminal conditions include:

```text
quiescence
explicit refusal
resource exhaustion
bounded-depth termination
successful completion
```

The court MUST attempt at least one cascade reaching more than one internal transition where supported.

An implementation that requires unbounded “continue reasoning until complete” control for known production work fails this gate.

# 38. Gate 7 — Sole DO Boundary / Zero Unreceipted Actuation

**Test ID family:** `CHI-BRCE-*`

The court MUST attempt real consequence without durable prepared receipt.

The invariant is:

```math
\boxed{Attempted(a) \Rightarrow PreparedReceipt(a)}
```

Mandatory falsifiers include:

- direct actuator call bypassing BRCE;
- authorized request with receipt store unavailable;
- planner or hook invoking actuator directly;
- replay path attempting to re-actuate;
- crash between preparation and external call;
- duplicate idempotency identity.

The gate passes only if no consequence occurs before durable preparation.

The OCEL query MUST be derived from actual evidence and MUST establish both that the violating path was attempted and that no forbidden DO preceded receipt preparation.

# 39. Gate 8 — Independent Postcondition Observation

**Test ID family:** `CHI-POST-*`

The actuator MUST NOT be the sole attestor of its own success.

The court MUST include at least one discriminating falsifier in which:

```text
actuator reports success but state did not change
or
actuator reports one state while independent state differs
```

A successful actuator return value without independent post-state observation is insufficient.

For reversible fixtures, the court SHOULD also observe the negative control in which the state genuinely changes.

# 40. Gate 9 — Complete Receipt Identity Binding

**Test ID family:** `CHI-RECEIPT-*`

Prepared and final receipts MUST bind sufficient identity to prevent evidence laundering.

The court SHOULD attempt tampering with:

```text
actor
semantic subject
capability/action
input digest
plan digest
projection digest
authority grant
idempotency identity
intended effect
result identity
receipt chain predecessor
```

Tampered evidence MUST NOT retain standing.

One-level nesting, alternate collection types, or serialization variations MUST NOT bypass evidence checks if they are semantically equivalent to the prohibited field.

# 41. Gate 10 — Offline Replay

**Test ID family:** `CHI-REPLAY-*`

A fresh replay engine MUST be able to verify the durable evidence chain without performing external consequence.

Replay SHOULD be able to reconstruct, where applicable:

```text
admission
selection
construction
authority decision
prepared receipt
intended effect
final receipt
observed post-state
```

Falsifiers include:

- missing receipt;
- reordered receipt;
- changed digest;
- changed authority identity;
- duplicate/replayed actuation identity;
- divergent reconstructed root;
- replay path that calls the actuator.

Any replay implementation that re-actuates external consequence fails this gate.

# 42. Gate 11 — Fresh-Consumer Proof

**Test ID family:** `CHI-FRESH-*`

A fresh consumer MUST reconstruct the standing claim from durable serialized artifacts only.

The fresh consumer MUST NOT reuse:

```text
producer process memory
in-process caches
open object references
mutable singleton state
undocumented temporary files
prior test fixture state
```

The court SHOULD terminate the producer process before fresh-consumer verification.

If standing disappears because hidden producer state was required, the gate fails.

# 43. Gate 12 — Zero Runtime Inference on KNOWN

**Test ID family:** `CHI-KNOWN-*`

For a semantic class already qualified as KNOWN and for which deterministic admitted machinery is sufficient, equivalent future execution MUST NOT require equivalent exploratory inference.

The required measurement is:

```math
\boxed{Allocation_{LLM}(KNOWN)=0}
```

and, where a planner was compiled out of the reflex:

```math
PlannerInvocations(KNOWN)=0
```

The court MUST prove positive execution of the known reflex while collecting zero exploratory model/planner usage.

A run that consumes zero tokens because the reflex never executed does not pass.

# 44. Admission Pipeline Court

The admission court MUST exercise the full required pipeline for the claimed profile.

A Strict reference order is:

```math
Candidate
\rightarrow Parse
\rightarrow Identity
\rightarrow ShEx
\rightarrow SHACL
\rightarrow RuleClosure
\rightarrow SPARQLFalsifiers
\rightarrow Provenance
\rightarrow ProfileChecks
\rightarrow MetaAdmission
\rightarrow ADMITTED
```

Failure at a REQUIRED stage MUST leave canonical state unchanged.

# 45. ShEx Structural Falsifiers

The ShEx court SHOULD include:

- missing required predicate;
- excess cardinality;
- wrong datatype;
- wrong node kind;
- invalid nested structure;
- structurally valid but semantically invalid control case.

The last case is required to prove that ShEx and SHACL are not collapsed into one vacuous check.

# 46. SHACL Semantic Falsifiers

The SHACL court SHOULD test at least:

```text
consequence without authority requirement
DO without receipt requirement
plan with unknown capability
private term without namespace admission
resource bound violation
canonical mutation outside consequence law
```

Warnings MUST NOT override a MUST-level violation.

# 47. Safe Datalog Court

For `SA2A-LOGIC` and above, Datalog qualification MUST establish:

```text
function-free behavior
range restriction
finite domain
side-effect freedom
no runtime network access
determinism
finite least-fixpoint termination
```

Falsifiers SHOULD attempt recursion that would require unbounded term creation, non-range-restricted rules, and side-effecting built-ins.

# 48. N3 Court

N3 qualification MUST demonstrate:

- admitted rule identity;
- candidate-only rule output until admission where required;
- no authority derivation from rule execution;
- no direct consequence through side-effecting built-ins;
- deterministic behavior within the declared profile.

A rule producing a semantically valid intent MUST still fail to DO without authority.

# 49. SPARQL Falsifier Court

Mandatory graph-global falsifiers SHOULD be executable as independent queries over the admitted candidate closure.

The court MUST demonstrate that a positive mandatory falsifier blocks admission.

Direct SPARQL Update against canonical admitted state MUST be tested and refused in the Strict profile.

# 50. Canonical Graph Identity Court

Canonical graph identity qualification MUST test more than text ordering.

At minimum the corpus MUST include:

```text
triple reorder
prefix reorder / equivalent prefix aliases
whitespace and serialization variation
blank-node relabeling / RDF dataset isomorphism
semantically distinct graph
malformed RDF
```

The court MUST require:

```math
G_1 \cong G_2 \Rightarrow Digest(G_1)=Digest(G_2)
```

and a malformed graph MUST fail closed rather than silently hash as an empty or unrelated graph.

The canonicalization algorithm and digest function MUST be pinned by the Root Manifest.

# 51. Public-Semantics and Namespace Court

The court SHOULD verify that:

- public IRIs are reused where the profile requires them;
- private terms carry required provenance/scope/version;
- Strict mode refuses runtime invention of operational private vocabulary;
- two peers using different labels do not infer semantic equality from textual similarity;
- explicit mappings are admitted before cross-identity composition.

# 52. Meta-Admission Court

The following machinery MUST itself have standing before it can confer production standing:

```text
ShEx schemas
SHACL shapes
N3 rules
Datalog programs
SPARQL falsifiers
planning domains
generators
authority policies
receipt schemas
semantic mappings
```

The court MUST attempt to substitute at least one unadmitted validator or rule and prove that its apparent validation result cannot admit a production object.

# 53. Root Manifest Court

The Root Manifest court MUST verify:

- content addressing;
- binding of admitted ontology roots;
- semantic profile version;
- canonicalization identity;
- manufacturer identities;
- validator/compiler identities;
- Authority Broker identity;
- BRCE contract;
- receipt law;
- cryptographic algorithm identities;
- version policy.

A use-time component substitution that leaves the earlier manifest receipt untouched MUST be detected.

# 54. Semantic Envelope Court

Inbound Semantic Envelopes MUST be tested for:

```text
missing envelope identity
invalid standing escalation
missing semantic basis
mismatched graph digest
missing provenance
unsupported profile
invalid consequence class
invalid authority requirement
forged receipt references
```

An upstream participant MUST NOT self-assert stronger standing than its receipts establish.

# 55. Extension Negotiation Court

A peer claiming Semantic A2A MUST advertise and negotiate a compatible profile before semantic standing crosses the peer boundary.

The court MUST attempt:

- ordinary A2A traffic presented as Semantic A2A;
- incompatible profile version;
- missing extension advertisement;
- consequence-bearing task without negotiated Strict/DO capability where required.

Silent profile assumption fails this court.

# 56. Downgrade Prevention Court

A Strict peer MUST NOT silently downgrade a consequence-bearing interaction to ordinary A2A semantics.

The court MUST attempt a peer mismatch in which the remote does not support the required Semantic A2A profile.

The expected semantic result is a typed unsupported/refusal outcome, not hidden fallback.

# 57. Capability Court

A capability declaration is not authority.

The court MUST distinguish:

```math
Capability(a,c) \not\Rightarrow Authority(a,c)
```

Falsifiers SHOULD include:

- valid Agent Card capability without grant;
- caller-supplied capability name;
- unknown capability in plan;
- mismatched capability precondition/effect contract;
- capability composition that attempts to raise authority ceiling.

# 58. Plan Package Court

A production plan package MUST be tested for the required identity and bounds, including:

```text
semantic goal
initial admitted state identity
planning-domain identity
action/method identities
preconditions/effects
nondeterministic outcomes
consequence class
required capabilities
fan-out/depth/parallelism
resource envelope
authority requirements
receipt obligations
planner identity
plan digest
```

A missing required production bound MUST cause refusal in Strict mode.

# 59. Planner Non-Authority Court

The court MUST include a plan that is:

```text
syntactically valid
semantically admitted
feasible under the planning model
```

but lacks execution authority.

The plan MAY reach `SELECTED` or `CONSTRUCTED` standing.

It MUST NOT reach DO solely because it is valid or optimal.

# 60. Knowledge Hook Court

Where Knowledge Hooks are implemented, the following MUST hold:

```math
Hook \neq DO
```

```math
HookOutput \Rightarrow SemanticIntent
```

```math
SemanticIntent \not\Rightarrow Authority
```

The court MUST attempt a hook that produces consequence-bearing intent without grant and prove zero consequence.

A hook MAY create a planning or coordination obligation. It MUST NOT bypass admission, authority, or BRCE.

# 61. Hook Meta-Admission Court

Hooks themselves are semantic artifacts.

The court MUST verify hook identity, provenance, condition identity, and admitted standing before a hook can participate in canonical production reflex.

An unadmitted hook that happens to match a graph delta MUST NOT fire with production standing.

# 62. Hook Determinism and Idempotency Court

For identical admitted base state, delta, hook revision, and deterministic environment, hook evaluation SHOULD produce equivalent verdict and intent identity.

The court MUST test:

```text
same delta replay
triple ordering variation
idempotency identity reuse
unrelated graph delta
condition false control
```

Duplicate delivery MUST NOT silently multiply consequence when the semantic action is idempotent by contract.

# 63. Reactive Cascade Court

Reactive systems MUST enforce admitted cascade bounds.

At minimum:

```math
Depth \le D_{max}
```

Where fan-out and parallelism are supported:

```math
FanOut \le F_{max}
```

```math
Parallelism \le P_{max}
```

The court MUST attempt a cycle or self-trigger capable of exceeding the bound.

The lawful result is bounded termination, refusal, or quiescence—not unbounded recursion.

# 64. Authority Court

Authority MUST be tested as a scoped, explicit, bounded, attributable, and receipted relation.

The court MUST distinguish authorization from:

```text
identity
authentication
capability
task assignment
plan validity
proof
model confidence
agent-card declaration
transport verification
```

# 65. Authority Non-Implication Falsifiers

The court MUST attempt at least the following:

```text
authenticated principal with zero grant
principal granted capability A attempting capability B
valid task with no grant
valid plan with no grant
valid proof with no grant
trusted transport identity requesting consequence
```

Each attempt MUST reach the authority boundary and be refused without consequence.

# 66. Confused Deputy Court

The court MUST verify that a peer does not use its own authority merely because another peer requested an operation.

A token or grant identity MUST remain bound to the admitted subject/capability/context required by the authority policy.

The court SHOULD test token rebinding, subject substitution, capability substitution, and delegated-envelope widening.

# 67. Grant Lifecycle Court

Where grants are revocable or time-bounded, the court MUST test:

```text
issue
authorize before expiry
refuse after expiry
revoke
refuse after revocation
restart / durable reload, where durable grants are claimed
broker unavailable
```

A storage or broker failure MUST fail closed.

Carrying an expiry only in an unused verification path does not satisfy this court; the real dispatch path MUST enforce it.

# 68. BRCE Court

BRCE is the sole reference consequence-bearing boundary.

The court MUST attempt bypass from at least:

```text
planner
hook
generated artifact
A2A task handler
direct internal mutation path
replay path
```

A path capable of external consequence without BRCE violates SA2A-DO/STRICT conformance.

# 69. Prepared Receipt Court

Before external actuation begins, the durable prepared receipt MUST bind at least the identities required by RFC-SA2A-001.

The court MUST include a storage-failure falsifier.

If durable preparation cannot be established, consequence MUST NOT begin.

# 70. Crash and Reconciliation Court

The court SHOULD inject crashes at consequence-critical boundaries, including:

```text
before receipt preparation
after preparation / before external call
during external call
after external response / before finalization
after finalization / before caller acknowledgement
```

The system MUST preserve enough evidence to distinguish at least:

```text
not attempted
prepared but unknown outcome
executed
failed
reconciled
compensated
```

where the external domain permits those distinctions.

# 71. Idempotency and Replay Protection Court

Consequence-bearing requests MUST carry stable actuation and idempotency identities.

The court MUST submit duplicate requests and verify that duplicate transport or replay does not create an unintended second consequence.

Where an external system supports an idempotency token, the SA2A actuation identity SHOULD be bound to it.

# 72. Attestation Court

An attestation MUST NOT claim more than was observed.

The court SHOULD attempt to promote:

```text
local test → hosted CI
hosted CI → deployment
deployment → runtime observation
runtime observation → publication
publication → merge
```

without new evidence.

Such promotion MUST be refused or remain unclaimed.

# 73. Independent Post-State Court

Post-state verification MUST be capable of contradicting the actuator.

A verifier that reads only the actuator’s return object is not independent.

The court SHOULD include both:

```text
false-positive actuator report
true-positive control
```

so the verifier proves discrimination rather than permanent refusal.

# 74. Fresh Consumer and Durable Evidence Court

The durable evidence package SHOULD be sufficient for a fresh consumer to answer:

```text
What semantic object was acted on?
Why did it have standing?
Which plan selected the operation?
Which authority grant permitted it?
Was receipt preparation durable before actuation?
What consequence was independently observed?
Can the evidence chain be replayed without DO?
```

If any REQUIRED question depends on hidden producer state, the relevant standing MUST NOT be inferred.

# 75. Transport Independence Court

Semantic interpretation MUST remain invariant across advertised A2A bindings.

Where two transport bindings are claimed, the court SHOULD send semantically equivalent envelopes over both and compare admitted semantic outcomes.

Transport metadata MUST NOT silently alter semantic meaning or authority.

# 76. Cross-Runtime Portable Semantic Execution Court

Where an implementation claims portable semantic execution, the strongest court uses one exact content-addressed semantic executable across heterogeneous hosts.

Reference relation:

```math
Runtime_A \neq Runtime_B
```

```math
Artifact_A = Artifact_B
```

and for each conformance fixture:

```math
Admission_A = Admission_B
```

```math
CanonicalPostState_A = CanonicalPostState_B
```

Equivalent negative fixtures SHOULD produce equivalent refusal classes.

Two independent reimplementations do not prove the same claim; they test implementation equivalence, not one-artifact portability.

# 77. Generated Projection Court

Generated code, plans, manifests, queries, or other projections MUST NOT become independent semantic truth.

The court MUST modify a generated projection manually and prove that the change does not mutate canonical `O^*` or automatically acquire production standing.

Correction belongs in admitted semantics or the lawful manufacturer.

# 78. Canonical Mutation Court

Strict mode MUST refuse direct canonical mutation outside admitted transition/consequence law.

The court SHOULD attempt:

```text
SPARQL Update against canonical graph
direct datastore write
projection-to-canonical promotion
message-to-canonical shortcut
LLM-output-to-canonical shortcut
```

Staging graphs MAY be mutated as allowed by profile, but staging MUST remain distinguishable from canonical admitted state.

# 79. UNKNOWN Court

When admitted machinery cannot classify, plan, or construct a lawful solution, the state MAY become `UNKNOWN`.

The court MUST prove:

```math
UNKNOWN \not\Rightarrow DO
```

and that outputs of discovery return as candidates requiring admission.

# 80. CMCA / Resource Allocation Court

Where a resource allocator is implemented before UNKNOWN resolution, the court MUST verify that the discovery engine cannot self-increase its own budget.

The falsifier SHOULD request resources beyond the admitted envelope.

The lawful result is a new allocation decision, refusal, or blocked-resource state—not implicit escalation.

# 81. LLM Boundary Court

An LLM MAY produce candidates.

The court MUST attempt model-generated:

```text
fact
ontology term
rule
shape
plan
code
authority claim
root-manifest change
```

and verify that model output alone does not acquire canonical standing or DO authority.

The invariant is:

```math
LLMOutput \Rightarrow Candidate
```

never:

```math
LLMOutput \Rightarrow Standing
```

# 82. Machine Experience Qualification

A successful UNKNOWN resolution SHOULD be capable of compiling into reusable admitted machinery such as:

```text
ontology
shape
rule
hook
plan
generator
verifier
```

The court SHOULD preserve a fixture representing the solved semantic class and rerun it through the compiled route.

The benchmark target is:

```math
\frac{\partial I_{required}}{\partial MachineExperience}<0
```

# 83. Resource Bounds Court

Known production work MUST declare finite resource envelopes where resource use is under protocol control.

The court SHOULD separately test exhaustion of:

```text
execution count
fan-out
concurrency
memory
runtime
retries
external requests
financial expenditure
model tokens
```

Exhaustion MUST fail closed or transition to a typed blocked/refused outcome.

# 84. Benchmark Philosophy

Semantic A2A benchmarks are subordinate to correctness.

No throughput number can compensate for a survived authority, receipt, standing, or canonical-state falsifier.

Benchmark runs MUST preserve the same semantic invariants as qualification runs.

Performance claims MUST identify the exact environment and exact subject.

# 85. Benchmark B1 — Admission Latency and Throughput

**Benchmark ID:** `SA2A-B1`

Measure:

```text
candidate parse latency
canonicalization latency
ShEx latency
SHACL latency
closure latency
falsifier latency
provenance/profile latency
total admission latency
admissions per second
refusals per second
```

The benchmark MUST include both valid and invalid candidates.

Invalid candidates MUST not be skipped from cost reporting.

# 86. Benchmark B2 — Logic Closure

**Benchmark ID:** `SA2A-B2`

For LOGIC profiles, report:

```text
fact count before closure
rule count
closure iterations
fact count after closure
wall time
peak memory
```

The corpus SHOULD include shallow, recursive, and near-bound finite programs.

Termination is mandatory; faster nontermination is not a valid result.

# 87. Benchmark B3 — Knowledge Hook Reflex

**Benchmark ID:** `SA2A-B3`

Where hooks are implemented, measure:

```text
delta size
hooks evaluated
hooks fired
intent count
hook-evaluation latency
intent-construction latency
idempotency-check latency
```

Include:

```text
no-match control
single-match
multi-match within bound
replay of same delta
```

# 88. Benchmark B4 — Planning

**Benchmark ID:** `SA2A-B4`

Report separately:

```text
planning projection time
planner invocation time
plan-admission time
plan size
fan-out/depth/parallelism bounds
resource envelope
```

The benchmark MUST distinguish planner computation from authority and DO latency.

# 89. Benchmark B5 — Authority and BRCE

**Benchmark ID:** `SA2A-B5`

Measure:

```text
authority decision latency
prepared-receipt durability latency
actuator latency
final-receipt latency
independent postcondition latency
end-to-end consequence latency
```

Report authorized, refused, expired, revoked, and broker-unavailable paths separately.

# 90. Benchmark B6 — Reactive Cascade

**Benchmark ID:** `SA2A-B6`

Measure cascade behavior as a function of admitted bounds:

```text
cascade depth
fan-out per depth
parallelism
receipts produced
time to quiescence
memory
```

The benchmark MUST include a cycle-inducing fixture to prove the bound is enforced.

# 91. Benchmark B7 — Cross-Runtime Portability

**Benchmark ID:** `SA2A-B7`

For one exact semantic artifact executed by heterogeneous hosts, report:

```text
host identities
artifact digest
fixture count
admission-equivalence count
refusal-equivalence count
post-state-equivalence count
latency per host
memory per host
```

A disagreement is a conformance defect before it is a performance result.

# 92. Benchmark B8 — Replay

**Benchmark ID:** `SA2A-B8`

Report:

```text
receipt-chain length
serialized evidence size
replay verification time
peak memory
fresh-consumer startup time
```

Replay MUST perform zero external consequence.

# 93. Benchmark B9 — OCEL Evidence Overhead

**Benchmark ID:** `SA2A-B9`

Measure the incremental cost of independent process evidence:

```text
OCEL events produced
OCEL objects produced
serialized size
observer CPU time
observer memory
serialization time
validation time
conformance-query time
```

The benchmark MUST NOT disable required evidence merely to improve throughput.

# 94. Benchmark B10 — Recovery and Reconciliation

**Benchmark ID:** `SA2A-B10`

For injected crashes/failures, report:

```text
failure point
prepared receipt state
external outcome knowledge
recovery time
reconciliation result
number of repeated external effects
```

The desired duplicate-effect count is zero unless the external domain makes exact idempotency impossible and the profile explicitly documents the limitation.

# 95. Stress Qualification

A Strict implementation SHOULD execute bounded stress tests across:

```text
candidate volume
semantic graph size
rule count
hook count
plan size
receipt-chain length
concurrent tasks
resource exhaustion
observer load
```

Stress testing MUST preserve all authority, receipt, and canonical-state invariants.

A stress result that drops evidence silently is a conformance failure, not a performance tradeoff.

# 96. Chaos Qualification

Chaos tests SHOULD inject failures into real boundaries, including:

```text
process termination
network partition
message duplication
message reordering
storage unavailability
partial writes
clock skew
validator crash
planner crash
authority broker crash
observer restart
actuator timeout
external ambiguous outcome
```

Each chaos fixture MUST define the invariant to preserve, not a golden internal execution trace.

# 97. Security Mutation Qualification

Security-sensitive boundaries SHOULD be mutation-tested.

Recommended mutations include:

```text
return true from authority check
ignore expiry
ignore revocation
remove receipt preparation
accept unsupported profile
trust sender standing
skip SHACL
skip graph-global falsifiers
allow caller-controlled consequence class
allow root-manifest component drift
allow replay to call actuator
```

A robust court SHOULD fail on each mutation.

# 98. Mandatory RFC-SA2A-001 Falsifier Corpus

A Strict deployment MUST test at least the following semantic counterexamples:

```text
consequence without authority requirement
DO without prepared-receipt requirement
unknown capability referenced by plan
unadmitted ontology term
unadmitted rule
unadmitted validator
plan exceeding fan-out bound
plan exceeding resource envelope
semantic artifact lacking provenance
semantic artifact lacking canonical identity
projection attempting to become canonical source
authority derived from agent identity alone
LLM output marked directly as ADMITTED
canonical mutation outside BRCE
```

Each corpus member MUST be an executable attempt, not a static checklist item.

# 99. Extended Adversarial Corpus

A mature Chicago court SHOULD additionally include:

```text
blank-node relabeling
malformed RDF that resembles empty graph
nested evidence laundering
alternate list/map/container encodings
forged standing seal
stale validator identity
expired authority grant
revoked authority grant
token subject/capability rebinding
broker unavailable
profile downgrade
host-identity normalization collision
vacuous declaration-count checks
zero-cost allocation at exhausted budget
receipt-chain deletion
receipt-chain reorder
receipt digest substitution
fresh-consumer hidden-cache dependency
same-runtime masquerading as heterogeneous runtime
non-UTF-8 / malformed host payload
resource-bound integer edge cases
```

New production defects SHOULD be converted into permanent corpus fixtures.

# 100. Positive Controls

Every major refusal family SHOULD have a positive control proving discrimination.

Examples:

```text
expired grant refused / future grant accepted
invalid SHACL refused / valid graph admitted
unknown capability refused / known capability admitted
tampered receipt refused / intact receipt verifies
unprepared DO blocked / prepared authorized DO executes
cycle beyond bound blocked / bounded acyclic reflex reaches quiescence
```

A verifier that always refuses is not conformant merely because it blocks attacks.

# 101. Negative Controls

Where a feature is declared unsupported, the court MUST distinguish:

```text
UNSUPPORTED
```

from:

```text
REFUSED
```

A system MUST NOT claim to have tested a feature it structurally does not implement.

# 102. Benchmark Environment Receipt

Every benchmark report MUST identify enough environment information to make the result interpretable, including where relevant:

```text
CPU model/count
memory
operating system / kernel
runtime versions
WASM engine version
BEAM/JVM/Python/Rust runtime versions
storage type
network topology
container/runtime limits
model/provider identity if UNKNOWN resolution is benchmarked
```

Benchmark numbers without environment identity MUST NOT be compared as if they measured the same subject.

# 103. Conformance Execution Order

The recommended qualification ladder is:

```text
1. exact identity / build
2. syntax / structural admission
3. semantic admission
4. logic closure
5. graph-global falsifiers
6. planning
7. authority
8. prepared receipt / BRCE
9. independent postcondition
10. replay
11. fresh consumer
12. blind OCEL process conformance
13. cross-runtime / transport qualification
14. chaos / stress
15. benchmarks
16. exact-subject standing receipt
```

The cheapest high-information falsifiers SHOULD run first.

# 104. Independent OCEL Validation Order

For each Chicago run producing OCEL evidence, the court SHOULD execute:

```text
run SUT
persist evidence
content-address evidence
validate OCEL 2.0 serialization
load evidence in independent consumer
run conformance predicates
cross-check receipts/post-state
issue standing verdict
```

The standing verdict MUST NOT be issued before the evidence artifact is durably available to the verifier.

# 105. OCEL Conformance Queries

This specification defines **questions**, not one required trace shape.

A court MUST be able to answer applicable questions such as:

```text
Was the violating action actually attempted?
Did an unadmitted object participate downstream?
Did a planner result acquire authority without a grant?
Did any consequence occur before durable preparation?
Did an actuator self-attest without independent observation?
Did a receipt identity change while preserving standing?
Did replay cause an external consequence?
Did a fresh consumer require hidden producer state?
Did a known-class reflex invoke exploratory intelligence?
Did a cascade exceed admitted bounds?
```

Implementations MAY answer these questions from different valid OCEL process structures.

# 106. OCEL Evidence Completeness

The court MUST reject an OCEL artifact that is syntactically valid but cannot support the predicates required for the claimed profile.

Evidence incompleteness is not equivalent to evidence of conformance.

Formally:

```math
Unknown(ValidExecution) \Rightarrow \neg Conformant
```

for a REQUIRED court predicate.

# 107. OCEL Object-Centricity Requirement

The observer SHOULD preserve the fact that one execution event may concern multiple semantic objects.

Flattening all activity into one case identifier SHOULD be avoided when it destroys relations needed to establish identity, authority, receipt, task, plan, or resource causality.

Qualified event-to-object and object-to-object relations SHOULD be used where they materially preserve process meaning.

# 108. Observer Non-Authority

The process observer records evidence.

It MUST NOT acquire consequence authority merely because it can see or classify the process.

```math
Observe \not\Rightarrow DO
```

An observer outage SHOULD affect evidence standing but MUST NOT silently create new execution authority.

# 109. Reference Process-Intelligence Court

An informative reference architecture is:

```text
autofde-lab
  → generates/selects falsifiers and experimental hypotheses

ash_a2a or another SA2A runtime
  → executes the real semantic/authority/consequence path

beam4pm or another process-intelligence system
  → independently observes the resulting execution and produces/queries OCEL 2.0
```

The roles are architectural, not product requirements.

A conforming implementation MAY use entirely different software while preserving the same separation.

# 110. Reference `beam4pm` Role

In the reference ecosystem, `beam4pm` is the natural location for the Chicago OCEL v2 process court because its role is process intelligence and object-centric conformance, not consequence execution.

A reference test SHOULD therefore drive real SA2A behavior, observe its emitted receipts/state/telemetry through `beam4pm`, validate the resulting OCEL independently, and determine whether the invariant was preserved.

`beam4pm` SHOULD NOT be handed a precomputed expected OCEL trace for the falsifier.

# 111. Reference `ash_a2a` Role

In the reference ecosystem, `ash_a2a` is a valid SUT for courts involving:

```text
A2A transport/lifecycle
Semantic Envelope admission
capability declarations
authority separation
CommandBus / consequence routing
receipt propagation
GraphLaw integration
Knowledge Hook boundary requests
```

Its own unit tests are useful but are not sufficient substitutes for an independent Chicago OCEL court.

# 112. Reference `autofde-lab` Role

In the reference ecosystem, `autofde-lab` owns EXPLORE and qualification science:

```text
falsifier generation
counterexample search
benchmark design
planner/policy experimentation
UNKNOWN resolution
machine-experience compilation
```

It SHOULD produce stronger falsifiers over time.

It MUST NOT convert the process observer into production authority.

# 113. Reference Manufacturing Boundary

Where qualified cognition is manufactured into deterministic software, the intended flow is:

```math
O^*
\rightarrow query
\rightarrow manufacturer
\rightarrow formal admission
\rightarrow runtime
\rightarrow BRCE
\rightarrow receipt
```

Generated artifacts remain projections.

A Chicago court SHOULD be generated or parameterized from canonical semantic requirements where practical rather than hand-maintained independently of them.

# 114. Required Conformance Artifacts

A complete conformance package SHOULD contain:

```text
exact-subject manifest
claimed SA2A profile
root-manifest identity
court version
falsifier inventory
commands and exit codes
raw test output
raw durable receipts
independent postcondition evidence
OCEL 2.0 artifact
OCEL validation receipt
conformance-query results
benchmark environment receipt
benchmark results
fresh-consumer result
replay result
final standing receipt
known exclusions / unsupported capabilities
```

# 115. Conformance Receipt

The final standing receipt MUST identify at least:

```text
subject
claimed profile
exact source/artifact identities
court revision
gates attempted
gates passed
gates failed
falsifiers killed
falsifiers survived
OCEL artifact digest
OCEL validation result
replay result
fresh-consumer result
independent postcondition result
benchmark artifact identities
excluded / unsupported features
standing
```

The receipt SHOULD be machine-readable.

# 116. Claim Language

A conforming report SHOULD use exact language such as:

```text
SA2A-CORE CONFORMANT for exact subject X under court revision Y
SA2A-DO NONCONFORMANT: CHI-BRCE-004 survived
SA2A-STRICT PARTIAL_ALIVE: local Chicago gates passed; cross-runtime court not observed
BLOCKED: required external provider unavailable
UNSUPPORTED: implementation does not implement SA2A-DO
```

It SHOULD NOT use phrases such as “RFC compliant” without naming the claimed profile and exact subject.

# 117. Failure Classification

Failures SHOULD be classified by failed transition rather than summarized as “tests failed.”

Recommended classes include:

```text
IDENTITY_FAILURE
ADMISSION_FAILURE
VALIDATOR_FAILURE
META_ADMISSION_FAILURE
PLANNING_FAILURE
BOUND_FAILURE
AUTHORITY_FAILURE
RECEIPT_FAILURE
ACTUATION_FAILURE
POSTCONDITION_FAILURE
REPLAY_FAILURE
FRESH_CONSUMER_FAILURE
OCEL_VALIDATION_FAILURE
OCEL_EVIDENCE_INCOMPLETE
CROSS_RUNTIME_DIVERGENCE
RESOURCE_BLOCKED
BUILD_BROKEN
UNSUPPORTED
```

# 118. Repair Discipline

After a falsifier survives:

1. preserve the minimal reproducer;
2. identify the failed transition;
3. form a new hypothesis;
4. make the smallest coherent repair;
5. add a permanent guard/test;
6. rerun the falsifier;
7. rerun the nearest court boundary;
8. expand verification only after the narrow repair passes.

An unchanged failure MUST NOT be repeatedly rerun without a new hypothesis.

# 119. Requalification

A prior Chicago Crown MAY be reused only if the identities relevant to the claim are unchanged.

At minimum, changes to any of the following SHOULD trigger requalification of dependent gates:

```text
source revision
validator/rule revision
root manifest
planner/domain
manufacturer
WASM artifact
runtime version
Authority Broker
BRCE
receipt schema
OCEL observer mapping
conformance-query set
```

# 120. Cross-Version Compatibility

CalVer ordering does not imply compatibility.

A newer Semantic A2A implementation MUST NOT inherit conformance merely because its version number is greater.

Compatibility and court applicability MUST be declared explicitly.

# 121. Minimum Continuous Qualification

A project claiming maintained Semantic A2A conformance SHOULD run, at minimum:

```text
narrow unit tests on each change
mandatory semantic falsifier corpus
Chicago gates affected by the diff
fresh-consumer/replay gates for receipt-path changes
cross-runtime court for semantic-engine changes
blind OCEL court for process/evidence changes
full profile court before final release tag
```

# 122. Benchmark Regression Policy

A performance regression alone does not automatically invalidate semantic conformance unless it violates an admitted bound or SLO that is part of the claimed profile.

A correctness regression always outranks a performance improvement.

The benchmark history SHOULD retain exact-subject identities so results remain comparable.

# 123. Security Disclosure and Falsifier Retention

A security defect discovered by the court SHOULD produce a retained regression falsifier after remediation.

Sensitive exploit details MAY be withheld from public artifacts when necessary, but the internal qualification package SHOULD retain enough exact evidence to re-run the boundary.

# 124. Privacy

OCEL process evidence SHOULD disclose only the identities necessary for qualification.

Implementations SHOULD prefer stable pseudonymous or content-addressed identities where human or confidential business data is not required by the court.

Redaction MUST NOT destroy the causal or identity relations needed for the claimed standing.

# 125. Determinism

Where a court claims deterministic semantics, identical admitted inputs, semantic machinery, and deterministic environment MUST reproduce equivalent semantic results.

Non-semantic metadata such as wall-clock timestamps, process IDs, or incidental scheduling MAY differ unless those fields participate in the claim.

The court SHOULD compare semantic identities rather than raw pretty-printed output.

# 126. Heterogeneous Runtime Requirement

A cross-runtime claim requires genuinely heterogeneous hosts or runtime implementations.

Changing only a whitespace-normalized host label is not evidence of heterogeneity.

The court SHOULD establish runtime identity from independently observable executable/runtime information rather than caller-controlled strings alone.

# 127. Bounded Concurrency

Concurrency tests MUST verify both the declared bound and the authority/resource envelope inherited by subtasks.

Delegation MUST NOT manufacture additional authority.

A child task whose parent has exhausted its resource envelope MUST NOT silently allocate a fresh unbounded envelope.

# 128. Evidence-Laundering Resistance

The court MUST consider semantically equivalent alternate encodings of prohibited evidence.

For example, if direct `llm_output` is prohibited from acquiring standing, the guard SHOULD be tested against nested structures, alternate collection representations, and equivalent field placements where the implementation accepts them.

A one-level key check is insufficient when semantically equivalent input can bypass it.

# 129. Vacuity Resistance

A declaration count is not an obligation count.

A court MUST NOT infer that a required semantic feature was exercised merely because configuration declares it.

Where a profile requires behavior, at least one test MUST force that behavior through the actual boundary.

# 130. Fail-Closed Requirement

If the court cannot determine whether a REQUIRED predicate holds, the standing result MUST NOT be conformant.

```math
Unknown(RequiredPredicate) \Rightarrow \neg CONFORMANT
```

An exception, timeout, malformed validator result, or unavailable broker MUST NOT be translated to success.

# 131. Refusal as Lawful Outcome

A refusal is often a successful conformance result.

The court MUST distinguish a lawful typed refusal from:

```text
crash
silent drop
unsupported feature
unknown outcome
successful admission
successful consequence
```

Refusal evidence SHOULD identify the stage and semantic subject.

# 132. No Blank Checks

The court MUST attempt at least one resource-extension request from a running worker or agent.

The invariant is:

```math
NeedMoreResources \not\Rightarrow GrantMoreResources
```

This applies to tokens, compute, money, calls, workers, tools, and authority.

# 133. Production Boundedness

A Strict production court MUST reject a known operation whose control contract is equivalent to:

```text
continue reasoning until you believe the task is complete
```

Known production work SHOULD reduce to finite admitted machinery or transition to `UNKNOWN` for bounded discovery.

# 134. Machine Experience Regression

A semantic class previously crowned as KNOWN SHOULD be re-tested periodically or after machinery changes to ensure it has not silently regressed to general inference.

The court SHOULD treat reintroduction of unnecessary LLM/planner calls as a machine-experience regression even if the functional output remains correct.

# 135. Conformance Benchmark Result Integrity

Benchmark output MUST NOT be edited manually after generation without invalidating its content digest.

Derived summaries MAY be produced, but the raw machine-readable benchmark result SHOULD remain available for replay and audit.

# 136. Court Versioning

The conformance court itself is semantic machinery.

Its version, validators, falsifier corpus, OCEL mappings, and conformance queries MUST be versioned.

A new court revision MAY discover defects in a subject that previously passed an older court. This does not make the new court incorrect; it means the earlier evidence boundary was narrower.

# 137. Court Meta-Admission

For Strict qualification, the court’s own normative machinery SHOULD itself be admitted or otherwise content-addressed and reviewable.

At minimum, the standing receipt MUST bind:

```text
court version
falsifier corpus digest
OCEL validator identity
conformance-query digest
standing-schema identity
```

# 138. Process Observer Qualification

The process observer SHOULD itself have tests for:

```text
dropped events
duplicated events
corrupted relationship identity
out-of-order ingestion
restart recovery
serialization corruption
unknown event type
unknown object type
```

An observer that silently loses required evidence cannot confer a Chicago Crown even if the SUT behaved correctly.

# 139. OCEL Observer Freshness

For high-consequence qualification, the court SHOULD demonstrate that the OCEL artifact can be read by a fresh process or independent OCEL tool after producer and observer processes terminate.

This establishes that the process evidence is an artifact, not merely a live dashboard.

# 140. Process Mining / Conformance Analysis

An implementation MAY use object-centric process mining, Petri-net conformance, POWL, declarative constraints, temporal queries, graph queries, or other deterministic methods to evaluate the OCEL.

This RFC does not mandate one conformance algorithm.

The algorithm MUST be capable of proving the predicates required by the claimed gates without relying on a predeclared golden trace.

# 141. Query Predicate Stability

Conformance predicates SHOULD be expressed at the semantic level.

For example:

```text
“No consequence before durable receipt preparation”
```

is preferable to:

```text
“event #7 must be named brce_prepare and event #8 must be named actuator_call.”
```

The former survives implementation refactoring while preserving the invariant.

# 142. Minimal Falsifier Quality Bar

A high-quality falsifier is:

```text
small
reproducible
boundary-specific
discriminating
capable of surviving if the guard is removed
independent of unrelated infrastructure where possible
permanently retainable as a regression guard
```

Large end-to-end scenarios are useful, but they do not replace small falsifiers that localize the violated transition.

# 143. Layered Verification Ladder

The recommended verification ladder is:

```text
narrow
→ unit
→ integration
→ Chicago exact-subject court
→ cross-runtime
→ end-to-end
→ chaos
→ stress
→ benchmark
→ machine report
```

The cheapest high-information test SHOULD run first.

# 144. Reuse of Prior Evidence

Evidence MAY be reused only when source, validator, toolchain, configuration, environment, and relevant subject identities match the earlier receipt.

Verifier standing and subject standing are distinct.

A previously qualified verifier does not automatically prove a newly changed SUT.

# 145. Compliance Matrix Requirement

A release claiming Semantic A2A conformance SHOULD publish a matrix mapping:

```text
RFC-SA2A-001 requirement
→ conformance test ID
→ evidence artifact
→ result
→ exact subject
```

A missing mapping for a REQUIRED requirement MUST be treated as an open evidence gap.

# 146. Definition of Done

For SA2A-STRICT, Chicago Done means:

> The exact admitted subject autonomously executes the real bounded path against load-bearing collaborators, crosses no unreceipted consequence boundary, independently verifies the resulting state, reproduces its evidence under replay and fresh-consumer conditions, emits independently validatable OCEL 2.0 process evidence, defeats the mandatory adversarial falsifiers, and routes a previously solved semantic class through admitted deterministic machinery without equivalent exploratory inference.

This is a standing claim about the exact exercised subject only.

# 147. Final Conformance Invariant

A Semantic A2A implementation SHALL be considered conformant to a claimed profile only when the court has positive evidence that every REQUIRED boundary for that profile was exercised and no prohibited transition acquired standing.

The final relation is:

```math
\boxed{
Conformant_P(S)
\Leftrightarrow
\bigwedge_{g\in Gates(P)}
\left(
AttemptObserved(g,S)
\land
PredicateSatisfied(g,S)
\right)
}
```

For consequence-bearing profiles:

```math
\boxed{
\neg Standing(x) \Rightarrow \neg Consequence(x)
}
```

must remain structurally true under adversarial execution.

For Strict known-class reflexes:

```math
\boxed{
KNOWN \rightarrow DeterministicMachine \rightarrow Receipt
}
```

must be observed without equivalent exploratory inference.

That is the Chicago conformance standard for Semantic A2A.

---

# Appendix A — Compact Algebra

```math
O^*=\alpha_B(O)
```

```math
A=\mu(O^*)
```

```math
Candidate\not\Rightarrow Standing
```

```math
Received\not\Rightarrow Admitted
```

```math
Hook\not\Rightarrow DO
```

```math
Intent\not\Rightarrow Authority
```

```math
Plan\not\Rightarrow Authority
```

```math
Proof\not\Rightarrow Authority
```

```math
Capability\not\Rightarrow Authority
```

```math
Authentication\not\Rightarrow Authority
```

```math
Executed(a)\Rightarrow Authorized(a)
```

```math
Attempted(a)\Rightarrow PreparedReceipt(a)
```

```math
Replay\not\Rightarrow ReActuate
```

```math
PASS_{negative}=AttemptObserved\land\neg ForbiddenOutcome
```

```math
KNOWN\Rightarrow Allocation_{LLM}=0
```

where deterministic admitted machinery is sufficient.

# Appendix B — Test ID Namespace

Recommended test ID families:

| Family | Subject |
|---|---|
| `CHI-ID-*` | Exact identity / tag / artifact binding |
| `CHI-ADM-*` | Admission / canonical standing |
| `CHI-REAL-*` | Real collaborators / zero mocks |
| `CHI-PLAN-AUTH-*` | Planner non-authority |
| `CHI-PREFLIGHT-*` | Whole-plan bound/preflight identity |
| `CHI-AUTO-*` | Bounded autonomous execution |
| `CHI-BRCE-*` | Sole DO boundary / prepared receipt |
| `CHI-POST-*` | Independent postcondition |
| `CHI-RECEIPT-*` | Receipt identity and tamper resistance |
| `CHI-REPLAY-*` | Replay / no re-actuation |
| `CHI-FRESH-*` | Fresh consumer |
| `CHI-KNOWN-*` | Zero runtime exploratory inference |
| `SA2A-CANON-*` | RDF canonical identity |
| `SA2A-SHEX-*` | Structural admission |
| `SA2A-SHACL-*` | Semantic constraints |
| `SA2A-LOGIC-*` | Datalog/N3 closure |
| `SA2A-SPARQL-*` | Global falsifiers / projections |
| `SA2A-HOOK-*` | Knowledge Hooks |
| `SA2A-AUTH-*` | Authority / grants / confused deputy |
| `SA2A-ENV-*` | Semantic Envelope |
| `SA2A-XRUNTIME-*` | Heterogeneous runtime portability |
| `SA2A-OCEL-*` | OCEL validity / evidence completeness |
| `SA2A-CHAOS-*` | Fault injection / reconciliation |
| `SA2A-B1..B10` | Benchmarks |

# Appendix C — Required Evidence Questions

A Strict court SHOULD be able to answer mechanically:

```text
What exact subject executed?
What candidate entered the boundary?
Was the candidate actually parsed and evaluated?
Why did it acquire or fail to acquire standing?
Which validator/rule/planner identities participated?
Was a plan merely selected or was it authorized?
Which grant authorized the consequence?
Was durable preparation complete before actuation?
Which external consequence was independently observed?
Which receipt binds the result?
Can the evidence be replayed without external DO?
Can a fresh consumer reconstruct the same standing?
What process did the independent OCEL observer actually see?
Did any mandatory falsifier survive?
Did a known-class run invoke exploratory intelligence?
```

# Appendix D — Chicago Standing Receipt Template

The following is an informative machine-readable template. It is **not** an OCEL template and MUST NOT be used as a golden process trace.

```json
{
  "specification": "RFC-SA2A-002-v26.9.16",
  "subject": {
    "identity": "...",
    "source_revision": "...",
    "artifact_digests": ["..."],
    "claimed_profile": "SA2A-STRICT"
  },
  "court": {
    "revision": "...",
    "falsifier_corpus_digest": "...",
    "query_set_digest": "..."
  },
  "results": {
    "gates_attempted": 12,
    "gates_passed": 12,
    "falsifiers_killed": 0,
    "falsifiers_survived": 0
  },
  "evidence": {
    "ocel_digest": "...",
    "ocel_valid": true,
    "replay": "PASS",
    "fresh_consumer": "PASS",
    "independent_postcondition": "PASS"
  },
  "standing": "CONFORMANT"
}
```

# Appendix E — Benchmark Result Template

An informative benchmark record SHOULD contain:

```text
benchmark ID
exact subject
profile
environment identity
fixture/corpus identity
iteration count
warmup policy
latency distribution
throughput
memory
artifact/evidence size
invariant failures
OCEL overhead
raw-result digest
```

Percentiles SHOULD be reported when latency distribution matters.

Means alone SHOULD NOT be used to hide long-tail behavior.

# Appendix F — Mapping to RFC-SA2A-001

| RFC-SA2A-001 area | Primary qualification in this RFC |
|---|---|
| Received is not Admitted | Gate 2; Admission Pipeline Court |
| Agent/Capability/Plan/Proof not Authority | Gates 4, 64–67 |
| SELECT ≠ CONSTRUCT ≠ DO | Gates 4, 7; Planner/BRCE courts |
| Zero Unreceipted Actuation | Gate 7; Prepared Receipt Court |
| Public Semantics / Identity | Gates 1–2; Namespace Court |
| Canonical Graph Identity | Canonical Graph Identity Court |
| ShEx / SHACL | Structural/Semantic falsifier courts |
| Safe Datalog / N3 | Logic courts |
| SPARQL falsifiers | SPARQL Court |
| Meta-admission | Meta-Admission / Root Manifest Courts |
| Planning / Plan Package | Gates 4–6; Plan Package Court |
| Authority | Authority / Confused Deputy / Grant Lifecycle Courts |
| BRCE | Gate 7; BRCE Court |
| Replay | Gate 10 |
| Attestation | Attestation Court |
| Bounded fan-out/resources | Gates 5–6; Resource Bounds Court |
| UNKNOWN / CMCA | UNKNOWN / Allocation Courts |
| Machine Experience | Gate 12; Machine Experience Qualification |
| LLM boundary | LLM Boundary Court |
| Transport independence | Transport / Cross-Runtime Courts |
| Evidence boundaries | Standing / Evidence Classes / Receipt |
| Strict final invariant | Full 12-gate Chicago Crown |

# Appendix G — OCEL 2.0 Prior-Art Basis

This specification uses OCEL 2.0 as a process-evidence exchange format because OCEL models typed events, typed objects, event-to-object relations, object-to-object relations, relationship qualifiers, and time-varying object attributes without forcing all behavior into one case identifier.

Normative OCEL syntax remains defined by the OCEL 2.0 specification and its standard serialization formats. This RFC adds Semantic A2A qualification semantics on top of OCEL; it does not redefine OCEL itself.

Reference: https://www.ocel-standard.org/2.0/ocel20_specification.pdf

# Appendix H — Reference Standards

This companion RFC relies on the same standards family referenced by RFC-SA2A-001, including:

```text
Agent2Agent (A2A) protocol
RDF / RDF Dataset Canonicalization (RDFC-1.0)
ShEx
SHACL
SPARQL
Notation3 (N3)
ODRL
formal planning representations such as FOND/HDDL
OCEL 2.0 for object-centric process evidence
```

Conformance to this document does not imply conformance to unrelated optional features of those standards.

# Appendix I — Non-Goals

This specification does not require:

- one programming language;
- one agent framework;
- one RDF library;
- one planner;
- one WASM engine;
- one process-mining algorithm;
- one OCEL serialization;
- one internal event naming scheme;
- one cloud provider;
- one authority policy language;
- one benchmark hardware configuration.

It requires that the claimed Semantic A2A invariants survive executable falsification and that the evidence supporting the claim is independently inspectable.

# Appendix J — Evolution Rule

When a new real defect is discovered in a conforming implementation:

```math
Defect
\rightarrow MinimalCounterexample
\rightarrow NewFalsifier
\rightarrow PermanentCorpus
\rightarrow CourtRevision
```

The desired trajectory is that every discovered failure boundary becomes machine knowledge and does not require rediscovery by future intelligence.

Thus the conformance court itself obeys the Semantic A2A machine-experience principle:

```math
\boxed{
\frac{\partial I_{required}}{\partial CourtExperience}<0
}
```

---

# References

1. **RFC-SA2A-001 v26.9.16**, *Semantic A2A: Admitted Semantic Interoperation for Machine-to-Machine Systems*.
2. **OCEL 2.0 Specification**, Object-Centric Event Log 2.0, https://www.ocel-standard.org/2.0/ocel20_specification.pdf.
3. **RDF Dataset Canonicalization (RDFC-1.0)**, W3C Recommendation.
4. **SHACL**, W3C Shapes Constraint Language.
5. **ShEx**, Shape Expressions.
6. **SPARQL**, W3C RDF query language.
7. **Notation3 (N3)**, RDF logic/rule language.
8. **ODRL Information Model 2.2**, W3C Recommendation.

---

# End of RFC-SA2A-002 v26.9.16
