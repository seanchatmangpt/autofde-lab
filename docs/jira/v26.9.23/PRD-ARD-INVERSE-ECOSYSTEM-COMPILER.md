# PRD/ARD — v26.9.23 Inverse Ecosystem Compiler

**Status:** PROPOSED
**Release:** v26.9.23
**Host repository:** seanchatmangpt/autofde-lab
**Base subject:** master@ae255ad123dfdcef9b3de82395006834abb20a28
**Working name:** Inverse Ecosystem Compiler (IEC)
**Standing ceiling:** documentation and architecture only until executable courts run

> This document specifies a new capability. It does not establish that the
> capability exists. docs/ is explanatory and cannot create standing.
> Every implementation claim must later be supported by exact-subject execution.

## 1. Executive summary

The Chatman ecosystem already has strong forward manufacture:

~~~text
admitted semantic source
  -> query / planning / generation
  -> generated artifact
  -> admission / verification
  -> BRCE-bounded consequence
  -> receipt / replay / standing
~~~

It also already has a real reverse-compilation primitive in ggen-create:
working exemplars can be observed, parameterized, converted into a ggen package,
regenerated with real ggen, and compared against an independent reference rail.

v26.9.23 generalizes that proven primitive from:

~~~text
one exemplar -> one reusable generator
~~~

to:

~~~text
repository corpus
  -> recovered semantic facts
  -> cross-repository equivalence classes
  -> minimal admitted semantic kernel
  -> deterministic generators / compositions
  -> regenerated subjects
  -> per-subject translation validation
  -> retirement of repeated LLM reasoning
~~~

The product objective is not to summarize the ecosystem.

The objective is to recover the smallest bounded semantic program that can
regenerate the admitted behavior of the observed ecosystem while preserving
authority, compatibility, receipts, replay, and explicit irreducible residue.

The limiting trajectory is:

\[
SourceCode \rightarrow Cache
\]

\[
CanonicalGraph \rightarrow SourceOfTruth
\]

and:

\[
\frac{\partial Outcome}{\partial RepeatedLLMReasoning} \rightarrow 0
\]

for every reasoning class that becomes known and externalizable.

## 2. Why autofde-lab owns the v26.9.23 experiment

The host is autofde-lab, not a new repository.

Its current doctrine already assigns it:

- candidate hypotheses;
- discriminating experiments;
- planning routes;
- possibility graphs;
- integration control;
- GALL verification;
- process-intelligence experimentation.

It explicitly does not own ambient production actuation.

That is exactly the boundary required by IEC.

IEC begins as an inference and falsification problem:

\[
R \rightarrow Hypotheses(K,G,E)
\]

not as a production migration or deletion controller.

The neighboring ownership is preserved:

| Concern | Owner |
| --- | --- |
| ecosystem-scale archaeology and hypothesis search | autofde-lab |
| exemplar -> admitted ggen package | ggen-create |
| reusable semantic manufacturing capital | ggen-marketplace |
| ontology -> Elixir/Igniter projections | ggen_igniter |
| deterministic manufacture | ggen |
| shared protocol / engineering law | engineering-standards |
| ecosystem composition and release qualification | ggen-ecosystem |
| evidence sealing / certification profiles | affidavit |
| work-order control plane | xaas / sJira |
| external consequential DO | BRCE-authorized executor only |

IEC MAY propose changes for neighboring repositories.

IEC MUST NOT silently absorb their authority.

## 3. Observed starting subjects

The v26.9.23 design is grounded against these observed heads on
2026-09-23:

| Repository | Branch | Observed subject |
| --- | --- | --- |
| autofde-lab | master | ae255ad123dfdcef9b3de82395006834abb20a28 |
| ggen-create | main | eaa463af138d7aff88db813f0f65307bf5c9b5ba |
| ggen-marketplace | main | 420bc91e7c1e291be73ab749b7e443252bc7bab8 |
| ggen-ecosystem | main | ee528a1bbfd4263232cefe6903b0df4f8b618502 |
| ggen_igniter | main | d84da1419a6945c6a8a64b8f6cdca9d0b2c9e0f3 |
| affidavit | main | 68f4265c3a84dd2b673bd54daa4c339805f018ef |
| engineering-standards | main | 610944c48bce6377291c088a3e07775e9ef2908b |
| xaas | main | 2fb10156c00a821a6915f239ace517bd860c1479 |

These pins are observation inputs, not permanent dependency pins.

The first executable run MUST produce a fresh catalog and bind every subject
it actually analyzes.

## 4. Problem statement

The ecosystem contains valuable semantics in multiple representations:

- RDF/OWL ontologies;
- SHACL shapes;
- SPARQL queries;
- TLA+ and other formal specifications;
- Python, Rust, Elixir, JavaScript, shell, configuration, and workflows;
- generated source;
- handwritten source;
- tests and fixtures;
- receipts and ledgers;
- PRDs, ARDs, ADRs, RFCs, and operating doctrine;
- git history and prior migrations;
- repeated architectural patterns distributed across repositories.

These representations are not all independent truths.

Many are projections, historical residue, local restatements, or repeated
implementations of the same latent transform.

The current failure mode is:

\[
KnownPattern
\xrightarrow{again}
LLMReasoning
\xrightarrow{again}
HandwrittenArtifact
\]

when the desired steady state is:

\[
KnownPattern
\rightarrow
Ontology/Type/Rule/Generator/Verifier
\rightarrow
DeterministicReuse
\]

The ecosystem therefore pays repeatedly for intelligence it has already bought.

## 5. Product thesis

Given a bounded repository corpus:

\[
R = \{r_1,r_2,\dots,r_n\}
\]

recover:

- \(K\): a canonical semantic kernel;
- \(G\): deterministic generators and compositions;
- \(H\): handwritten irreducible residue;
- \(V\): admitted equivalence and conformance courts;
- \(P\): provenance mapping from source observations to kernel facts.

The desired relationship is:

\[
Generate(K,G,H) \equiv_V R
\]

where \(\equiv_V\) is deliberately bounded observational equivalence under the
declared verifier set \(V\).

IEC does not claim global semantic equivalence.

For a subject \(a\), candidate regeneration \(b\), and verifier set \(V\):

\[
a \equiv_V b
\iff
\forall v \in V,\; v(a)=v(b)
\]

The optimization objective is:

\[
J(K,G,H) =
L(K) + L(G) + \lambda L(H)
+ \mu Failure_V
+ \nu RepeatedReasoning
\]

subject to preservation of:

- admitted public behavior;
- authority boundaries;
- exact-subject identity;
- compatibility obligations;
- receipt/replay requirements;
- generator ownership;
- security and privacy fences.

This is a bounded optimization problem.

It is not a claim that a globally minimal equivalent program is computable.

## 6. Product outcomes

IEC MUST produce six primary outcomes.

### O1 — Repository Semantic Census

Every admitted repository receives a machine-readable observation record:

~~~text
RepositoryObservation
  repository
  exact_subject
  languages
  build_surfaces
  test_surfaces
  public_interfaces
  ontology_sources
  generated_surfaces
  authority_boundaries
  receipt_surfaces
  external_dependencies
  historical_sources
  unknowns
~~~

Catalog membership is observation only.

### O2 — Semantic Equivalence Graph

IEC discovers candidate equivalence classes such as:

~~~text
same protocol expressed in multiple languages
same receipt structure with local names
same transition law repeated across repos
same generator pattern manually reproduced
same ontology concept duplicated under aliases
same verification obligation implemented differently
same workflow encoded in CI, code, and documentation
~~~

Every equivalence edge carries:

~~~text
CandidateEquivalence
  left_subject
  right_subject
  relation
  evidence
  exclusions
  verifier_required
  confidence_class
  standing
~~~

Similarity is not equivalence.

Adjacency is not equivalence.

A candidate remains candidate until its court runs.

### O3 — Canonical Semantic Kernel

The system proposes the smallest admitted graph that explains the discovered
equivalence classes.

Candidate classes include:

~~~text
Capability
Protocol
State
Transition
Invariant
Authority
ReceiptProfile
EvidenceState
Planner
Policy
Projection
Generator
Verifier
Process
WorkOrder
Artifact
Dependency
CompatibilityContract
DispositionCandidate
~~~

The kernel is not accepted because an LLM generated it.

It is accepted only to the extent that admitted projections can be regenerated
and validated against observed subjects.

### O4 — Regeneration

For an admitted subject:

\[
R_{old}
\xrightarrow{extract}
K_R
\xrightarrow{manufacture}
R_{new}
\]

The generated subject MUST be produced by admitted machinery where available.

Priority:

\[
reuse \rightarrow compose \rightarrow extend \rightarrow invent
\]

Existing ggen-create, ggen, ggen-marketplace, and framework-native generators
MUST be examined before a new local generator is admitted.

### O5 — Translation Validation

Every regeneration is validated independently.

IEC follows translation-validation discipline:

\[
source
\xrightarrow{translator}
target
\xrightarrow{validator}
PASS|COUNTEREXAMPLE
\]

The translator does not certify itself.

A successful validator result applies only to that exact translation.

### O6 — Intelligence Retirement Ledger

Every recurring reasoning class receives a disposition:

~~~text
ReasoningClass
  identity
  observations
  recurrence_count
  current_executor
  deterministic_replacement
  admission_status
  last_llm_required_reason
  retirement_status
~~~

The target state is:

~~~text
UNKNOWN -> explored with intelligence
KNOWN -> encoded
REPEATED -> mechanized
MECHANIZED -> LLM retired from normal path
~~~

## 7. Primary users

### Ecosystem architect

Needs to identify duplicated concepts, obsolete boundaries, and the true
semantic source of behavior.

### Generator author

Needs to know which repeated structures can become reusable packs instead of
hand-maintained code.

### Repository maintainer

Needs a bounded answer to:

> Which parts of this repository are canonical, generated, derived, duplicated,
> historical, or irreducible?

### Verification engineer

Needs exact translation-validation obligations and counterexamples rather than
a prose assertion that two implementations are equivalent.

### Agent / LLM operator

Needs a frontier showing which tasks remain semantic UNKNOWNs and which tasks
must be routed to deterministic machinery.

## 8. Product requirements

### PR-001 — Exact repository census

IEC MUST freeze an exact corpus manifest before inference.

The manifest MUST include repository identity, default branch, exact commit,
visibility class, and inclusion/exclusion reason.

No repository may enter the run only because it was discovered later.

A later addition creates a new corpus revision.

### PR-002 — Multi-source observation

IEC MUST ingest at least:

- file/tree identity;
- language and parser outcomes;
- build manifests;
- dependency manifests;
- test surfaces;
- CI/workflow definitions;
- ontology/schema files;
- generator declarations;
- receipt/evidence formats;
- public interfaces;
- documentation assertions;
- git history where required to reconstruct origin/function.

Each observation MUST retain provenance.

### PR-003 — Observed/inferred separation

Every semantic fact MUST be typed as one of:

~~~text
OBSERVED
DERIVED_DETERMINISTIC
INFERRED_CANDIDATE
ADMITTED
CONTRADICTED
UNKNOWN
~~~

LLM output begins as INFERRED_CANDIDATE.

It never enters ADMITTED merely because multiple agents agree.

### PR-004 — Structural parsing before LLM interpretation

Where a mature parser exists, IEC MUST use it before asking an LLM to infer
syntax structure.

Tree-sitter or a language-native compiler/parser SHOULD supply concrete or
abstract syntax structure for supported languages.

Regex-only source understanding is insufficient for an admitted structural
equivalence claim.

### PR-005 — Reuse ggen-create

IEC MUST treat current ggen-create as the existing per-exemplar reverse
compiler primitive.

IEC MUST NOT create a second exemplar-to-ggen-package implementation unless an
exact capability falsifier demonstrates that ggen-create cannot represent the
required case.

New IEC work belongs above or beside that boundary:

~~~text
ggen-create:
  exemplar -> manufacturing package

IEC:
  corpus -> semantic kernel -> reusable manufacturing topology
~~~

### PR-006 — Multi-repository anti-unification

IEC MUST support generalization across multiple observed subjects.

The initial admitted search SHOULD include:

- lexical anti-unification;
- syntax-tree anti-unification;
- graph neighborhood generalization;
- schema/type correspondence;
- protocol/state-machine correspondence;
- generator-template correspondence.

A generalization MUST retain substitutions that reconstruct each admitted
member.

### PR-007 — Counterexample-guided refinement

Kernel and generator inference MUST be iterative:

~~~text
candidate hypothesis
  -> manufacture / project
  -> verifier
  -> PASS or counterexample
  -> refine hypothesis
~~~

A counterexample is a first-class artifact.

The system MUST NOT repeatedly run an unchanged failed hypothesis without a new
discriminating change.

### PR-008 — Explicit equivalence dimensions

IEC MUST NOT use one global boolean called equivalent.

Equivalence MUST be decomposable across dimensions such as:

~~~text
interface
syntax
build
tests
runtime behavior
protocol behavior
authority
receipt semantics
replay
performance envelope
compatibility
documentation contract
~~~

The equivalence court selects which dimensions are load-bearing for a subject.

### PR-009 — Generated versus handwritten classification

Every file or artifact in an analyzed subject SHOULD receive one of:

~~~text
CANONICAL_SOURCE
GENERATED_PROJECTION
DERIVED_CACHE
HANDWRITTEN_IRREDUCIBLE
HISTORICAL_RESIDUE
EXTERNAL_VENDORED
UNKNOWN
~~~

A generated artifact MUST identify its producer when known.

### PR-010 — Repository disposition candidates

IEC MAY propose:

~~~text
KEEP
GENERATE
COMPOSE
MERGE
ADAPTER
ARCHIVE
DELETE
~~~

These are DispositionCandidate values only.

No disposition has repository mutation authority.

Any candidate other than KEEP MUST include:

- replacement path;
- preservation fence;
- equivalence court;
- rollback/recovery path;
- exact subjects affected.

### PR-011 — No unreceipted actuation

IEC is SELECT/CONSTRUCT/VERIFY only inside autofde-lab.

It MUST NOT merge, delete, archive, publish, deploy, or mutate external
repositories through ambient authority.

Consequential work MUST cross a separately authorized BRCE boundary.

### PR-012 — Retirement ledger

A repeated reasoning class MUST become a mechanization candidate once recurrence
is observed.

A class is RETIRED_FROM_LLM only after the deterministic replacement has an
admitted verifier and replay evidence.

### PR-013 — Incremental re-analysis

A later repository commit SHOULD reuse prior observations when identities prove
they remain valid.

Changed surfaces MUST invalidate dependent observations transitively.

Unchanged evidence MUST not be re-purchased with LLM reasoning.

### PR-014 — Typed unknowns

IEC MUST preserve UNKNOWN.

Examples:

~~~text
UNKNOWN_ORIGIN
UNKNOWN_GENERATOR
UNKNOWN_EQUIVALENCE
UNKNOWN_AUTHORITY
UNKNOWN_RUNTIME_BEHAVIOR
UNKNOWN_HISTORY
~~~

Unknown does not imply unique, handwritten, required, or safe to delete.

### PR-015 — Evidence-bounded claims

Every result MUST expose the exact evidence ceiling.

Examples:

~~~text
STRUCTURAL_EQUIVALENCE_ONLY
BUILD_AND_TEST_EQUIVALENCE_ONLY
BOUNDED_RUNTIME_EQUIVALENCE_ONLY
AUTHORITY_MODEL_EQUIVALENCE_ONLY
TRANSLATION_VALIDATED_FOR_EXACT_SUBJECT
~~~

No bounded court may silently become a universal equivalence claim.

## 9. Explicit non-goals

v26.9.23 does not require:

- a proof of globally minimal source code;
- proof of arbitrary-program semantic equivalence;
- automatic repository deletion;
- automatic merging of projects;
- rewriting all repositories into one programming language;
- replacing framework-native generators;
- replacing ggen-create;
- treating documentation as runtime evidence;
- treating LLM consensus as admission;
- executing arbitrary repository code during discovery without a broker;
- production migration;
- customer-system actuation;
- replacing BRCE, GALL, or Affidavit.

## 10. Prior-art-first design

IEC should compose existing ideas rather than naming local reinventions.

### Software reflexion models

Use design/source drift as evidence.

IEC's Observed / Expected / Convergent / Divergent / Absent / UNKNOWN mapping
is a semantic extension of the reflexion-model idea: compare recovered
implementation structure with proposed high-level structure rather than assuming
one is correct.

### Anti-unification

Use least-general-generalization techniques where the representation supports
them.

Anti-unification provides the core shape:

\[
AntiUnify(x_1,\dots,x_n)
\rightarrow
(g,\sigma_1,\dots,\sigma_n)
\]

such that:

\[
g\sigma_i = x_i
\]

within the admitted representation.

### Syntax-guided synthesis and CEGIS

When IEC must synthesize a transform, the search space SHOULD be bounded by a
grammar or type system.

Counterexample-guided refinement is preferred to unrestricted generation.

### Translation validation

IEC validates each produced translation independently instead of assuming that
a complex reverse compiler is universally correct.

### Language parsers

Use Tree-sitter or native parsers to recover structural observations before LLM
semantic interpretation.

## 11. Architecture overview

~~~mermaid
flowchart TD
    C[Exact Repository Corpus]
    O[Observation Extractors]
    N[Normalized Semantic IR]
    E[Equivalence Candidate Graph]
    H[Hypothesis Frontier]
    K[Candidate Semantic Kernel]
    M[Manufacture Adapters]
    T[Translation Validators]
    X[Counterexamples]
    R[Retirement Ledger]
    P[Promotion Candidates]

    C --> O
    O --> N
    N --> E
    E --> H
    H --> K
    K --> M
    M --> T
    T -->|PASS| R
    T -->|FAIL| X
    X --> H
    R --> P
~~~

The architecture is deliberately a loop.

A one-shot "analyze everything and write an ontology" operation is not
admissible.

## 12. Canonical pipeline

\[
INGEST
\rightarrow PARSE
\rightarrow NORMALIZE
\rightarrow EXTRACT
\rightarrow RELATE
\rightarrow ANTIUNIFY
\rightarrow HYPOTHESIZE
\rightarrow FALSIFY
\rightarrow ADMIT
\rightarrow MANUFACTURE
\rightarrow TRANSLATIONVALIDATE
\rightarrow CLASSIFY
\rightarrow PROMOTE
\]

### 12.1 INGEST

Freeze corpus identity and collect immutable observations.

### 12.2 PARSE

Use deterministic parsers for known formats.

### 12.3 NORMALIZE

Map syntax-specific observations into a language-neutral intermediate graph
without discarding source identity.

### 12.4 EXTRACT

Recover candidate concepts, relations, transforms, invariants, and ownership.

### 12.5 RELATE

Build candidate correspondence edges within and across repositories.

### 12.6 ANTIUNIFY

Find common structure while preserving per-member substitutions.

### 12.7 HYPOTHESIZE

Construct candidate kernel/generator explanations.

This is the main permitted Claude/LLM frontier.

### 12.8 FALSIFY

Search for the cheapest observation or execution that distinguishes competing
hypotheses.

### 12.9 ADMIT

Promote only what the relevant deterministic/formal court supports.

### 12.10 MANUFACTURE

Generate replacement projections with existing admitted generator rails.

### 12.11 TRANSLATIONVALIDATE

Compare original and regenerated subjects under exact declared verifier sets.

### 12.12 CLASSIFY

Update artifact, repository, and reasoning-class dispositions.

### 12.13 PROMOTE

Emit candidate changes for owning repositories.

Promotion itself has no merge or deployment authority.

## 13. Architecture components

### A1 — Corpus Controller

Owns:

- exact repository manifest;
- corpus revision;
- include/exclude rules;
- per-repository observation state.

It MUST be deterministic.

### A2 — Observation Extractor Registry

Adapters SHOULD include:

~~~text
git
filesystem
Tree-sitter / native parser
package manifests
build systems
test discovery
CI/workflows
RDF/OWL
SHACL
SPARQL
TLA+
OpenAPI / JSON Schema
OCEL
receipt schemas
documentation metadata
~~~

Each extractor emits provenance-bearing observations.

### A3 — Semantic Intermediate Representation

IEC uses an RDF-compatible canonical graph.

The IR MUST preserve:

- source subject;
- source span/path;
- observation method;
- exact evidence identity;
- asserted relation;
- confidence/standing type;
- contradiction links;
- derivation lineage.

The IR is not allowed to erase the distinction between observation and
inference.

### A4 — Correspondence Engine

Produces candidate links such as:

~~~text
sameAsCandidate
implementsCandidate
generatesCandidate
refinesCandidate
projectsCandidate
duplicatesCandidate
supersedesCandidate
adapterForCandidate
verifiesCandidate
~~~

No edge name ending in Candidate grants canonical identity.

### A5 — Generalization Engine

The engine chooses the strongest known formal mechanism supported by the object:

- first-order anti-unification;
- syntax-tree generalization;
- graph matching;
- schema subsumption;
- rule induction;
- state-machine refinement;
- constraint solving.

LLM reasoning is a fallback for semantic UNKNOWNs.

### A6 — Hypothesis Frontier

The frontier stores competing explanations.

A hypothesis MUST contain:

~~~text
hypothesis_id
covered_observations
excluded_observations
kernel_delta
generator_delta
required_residue
predicted_consequences
falsifier
estimated_cost
authority_requirements
~~~

Hypotheses without falsifiers are not admission candidates.

### A7 — Manufacture Router

Routes admitted transforms to existing machinery:

~~~text
ggen-create
ggen
ggen-marketplace packs
ggen_igniter
framework-native generators
language-native generators
template/generator adapters
~~~

The router records UNSUPPORTED(generator-capability) before permitting
handwritten residue.

### A8 — Equivalence Court

The court accepts:

~~~text
OriginalSubject
GeneratedSubject
VerifierSet
ClaimCeiling
~~~

and emits:

~~~text
PASS
COUNTEREXAMPLE
BLOCKED
UNSUPPORTED
~~~

It MUST NOT emit generic success without the verifier-set identity.

### A9 — Retirement Controller

Maps repeated Claude/LLM transformations to durable machinery.

It does not retire a reasoning class until the replacement's exact execution is
verified.

### A10 — Promotion Router

Maps admitted findings to owning repositories.

Examples:

~~~text
protocol law -> engineering-standards
reusable pack -> ggen-marketplace
Elixir projection adapter -> ggen_igniter
reverse-compiler primitive -> ggen-create
ecosystem composition -> ggen-ecosystem
receipt profile -> affidavit
new planner / experiment -> autofde-lab
work graph -> xaas / sJira
~~~

## 14. Claude Cloud role

Claude is intentionally not the normal runtime.

Claude is used for the expensive UNKNOWN frontier.

### Claude MAY

- read broad repository context;
- propose semantic correspondences;
- identify hidden repeated transforms;
- propose kernel factorizations;
- produce falsifiers;
- propose missing ontology terms;
- explain contradictions;
- suggest prior art;
- synthesize bounded candidates.

### Claude MUST NOT

- declare its own hypothesis admitted;
- grant BRCE authority;
- treat generated prose as evidence;
- silently edit generated projections;
- delete repositories;
- promote similarity to equivalence;
- hide counterexamples;
- repeatedly solve a mechanizable class without recording retirement debt.

### Token-use objective

The $250 grant should maximize future avoided reasoning, not generated text.

A default allocation is:

~~~text
55%  broad archaeology and semantic correspondence discovery
20%  adversarial falsification and counterexample search
15%  kernel / generator candidate synthesis
10%  final compression, retirement ledger, and promotion plan
~~~

This allocation is a planning default, not a billing claim.

## 15. Explore / exploit separation

### Explore

Allowed:

- broad retrieval;
- hypothesis generation;
- weak candidate links;
- bounded failed probes;
- semantic experiments;
- alternative decompositions.

Optimization:

\[
InformationGain > ProbeCost
\]

### Exploit

Allowed only after admission:

- deterministic extraction;
- known parser operation;
- known generator execution;
- formal verification;
- replay;
- mechanical catalog updates.

A known failed edge becomes topology and a guard.

It MUST NOT be rediscovered repeatedly as though it were new uncertainty.

## 16. Semantic kernel ontology

The first ontology revision SHOULD define at least:

~~~text
Repository
Revision
Artifact
SourceArtifact
GeneratedArtifact
CanonicalSource
IrreducibleResidue

Capability
Protocol
State
Transition
Invariant
AuthorityBoundary
ReceiptProfile
EvidenceState

Generator
Projection
Template
Query
Parser
Verifier
EquivalenceCourt
Counterexample

Observation
Inference
Admission
Contradiction
Unknown

EquivalenceCandidate
EquivalenceDimension
Substitution
Generalization

ReasoningClass
RetirementCandidate
DispositionCandidate
PromotionCandidate
~~~

Relationships SHOULD include:

~~~text
observedAt
derivedFrom
generatedBy
verifiedBy
implements
projects
refines
supersedes
requiresAuthority
hasReceiptProfile
hasEquivalenceDimension
hasSubstitution
hasCounterexample
promotesToRepository
retiredBy
~~~

## 17. State model

An IEC semantic claim follows:

~~~text
OBSERVED
  -> CANDIDATE
  -> ADMITTED
  -> MANUFACTURED
  -> VERIFIED
  -> REPLAYABLE
  -> PROMOTABLE
~~~

Negative states remain typed:

~~~text
REFUSED
BLOCKED
UNSUPPORTED
BUILD_BROKEN
CONTRADICTED
UNKNOWN
~~~

No state transition grants external DO authority.

## 18. Authority model

| Component | Observe | Select | Construct | Verify | External DO |
| --- | ---: | ---: | ---: | ---: | ---: |
| corpus controller | yes | bounded | manifest | yes | no |
| parser/extractors | yes | no | IR | deterministic | no |
| Claude frontier | yes | candidate | hypothesis | no | no |
| generalization engine | yes | bounded | candidate kernel | bounded | no |
| manufacture router | admitted | bounded | artifacts | no | no |
| equivalence court | admitted | no | receipt/evidence | yes | no |
| promotion router | admitted | candidate | change intent | no | no |
| BRCE executor | admitted | policy | bounded | receipt | **exclusive** |

## 19. Semantic equivalence law

"Equivalent" is always parameterized.

For verifier set \(V\):

\[
Equivalent_V(a,b)
\]

MUST name \(V\).

Examples:

~~~text
Equivalent_{public_api}
Equivalent_{build+unit}
Equivalent_{protocol}
Equivalent_{receipt}
Equivalent_{bounded_runtime}
Equivalent_{all_admitted_for_subject}
~~~

The last form is still bounded by the admitted verifier set.

IEC MUST preserve negative evidence.

If:

\[
v(a) \neq v(b)
\]

the resulting counterexample is permanently associated with the failed
equivalence hypothesis.

## 20. Minimality law

IEC does not seek minimum line count.

It seeks minimum lawful semantic description under the selected language of
representation.

A candidate \(K_1\) dominates \(K_2\) only when:

1. both cover the same admitted observations;
2. both satisfy the same equivalence courts;
3. both preserve the same authority/compatibility boundaries;
4. \(Cost(K_1) < Cost(K_2)\) under the declared cost function.

The cost function MUST be versioned.

No result may be called "globally minimal."

## 21. Preservation fences

Before any MERGE, ARCHIVE, or DELETE disposition candidate, IEC MUST
reconstruct:

~~~text
system
boundary
origin
function
consumers
authority
compatibility
historical reason
replacement path
rollback path
~~~

A repository that appears redundant but has an unmodeled consumer remains
UNKNOWN_CONSUMER, not deletable.

## 22. Security model

IEC treats repository contents as untrusted input.

Required controls:

- no secret publication;
- no private-repository identity leakage into a public corpus;
- root-fenced path access;
- symlink and path-traversal refusal;
- binary/opaque classification;
- no arbitrary build/test execution during passive discovery;
- brokered execution for active probes;
- bounded network access;
- exact toolchain identity for executable courts;
- immutable counterexample preservation;
- no authority inference from credential possession.

## 23. Incremental computation

IEC SHOULD be content-addressed.

For observation \(o\):

\[
id(o)=H(subject,extractor,version,input)
\]

A previous observation MAY be reused only when all bound identities match.

If source, extractor, parser grammar, config, or dependency identity changes,
dependent observations become stale.

This converts repeated archaeology into incremental compilation.

## 24. CEGIS loop

The core learning loop is:

~~~text
observations
  -> candidate semantic kernel
  -> generate representative subject
  -> translation validation
  -> PASS or counterexample
  -> refine
~~~

Formally:

\[
K_{i+1} = Refine(K_i, Counterexample_i)
\]

An unchanged \(K_i\) MUST NOT be rerun against the same failed court without a
new hypothesis about why the result could differ.

## 25. First crown: one repository can be regenerated

The first v26.9.23 crown is intentionally narrower than "the whole ecosystem."

### Crown IEC-C1

Given one non-trivial admitted repository subject:

1. freeze exact subject;
2. produce repository observation graph;
3. classify canonical/generated/handwritten/unknown surfaces;
4. recover candidate semantic kernel;
5. reuse existing generators where possible;
6. generate a fresh subject in an isolated destination;
7. run the subject's admitted verifier set against original and regenerated
   forms;
8. preserve all mismatches as counterexamples;
9. iterate until the declared court passes or returns typed UNSUPPORTED;
10. emit translation-validation receipt and retirement ledger.

The first recommended target is ggen_igniter because it already exposes clear
ontology/query/template/generated boundaries while still containing substantial
handwritten coordination and verification code.

A pass does not imply that every behavior of ggen_igniter is equivalent.

The crown claim is only:

~~~text
IEC_TRANSLATION_VALIDATED_FOR_<exact-subject>_UNDER_<verifier-set>
~~~

## 26. Second crown: cross-repository semantic collapse

### Crown IEC-C2

Select at least three repositories with a repeated semantic family.

The court must prove that:

1. the common semantic kernel is smaller than independent representations under
   the declared cost function;
2. each original member is reconstructable from kernel + substitution + explicit
   residue;
3. each reconstructed member passes its own verifier set;
4. a held-out member or held-out revision is explained without manually adding a
   member-specific duplicate of the whole kernel.

This crown separates generalization from memorization.

## 27. Third crown: reasoning retirement

### Crown IEC-C3

Observe one reasoning class performed multiple times by Claude during IEC.

Externalize it into deterministic/formal machinery.

Re-run the workflow with Claude disabled for that class.

Required result:

\[
Outcome_{mechanized} \equiv_V Outcome_{Claude}
\]

under the admitted court, with lower required semantic intelligence at runtime.

## 28. Ecosystem-scale crown

### Crown IEC-C4

For the admitted public repository corpus:

- every repository has an observation record;
- every analyzed file has an artifact class or typed UNKNOWN;
- every proposed cross-repository equivalence has a court or explicit unresolved
  state;
- every reusable pattern has a destination owner;
- every disposition candidate has a preservation fence and replacement witness;
- no claimed deletion depends only on similarity or LLM judgment;
- repeated known reasoning is represented in the retirement ledger.

IEC-C4 is a coverage and bounded-equivalence crown.

It is not a proof that the corpus is globally minimal.

## 29. Repository disposition calculus

For repository \(r\):

\[
DispositionCandidate(r)
\in
\{
KEEP,
GENERATE,
COMPOSE,
MERGE,
ADAPTER,
ARCHIVE,
DELETE
\}
\]

Selection requires a receipt containing:

~~~text
subject
candidate
reason
replacement
preservation_fence
equivalence_courts
counterexamples
rollback
authority_required
claim_ceiling
~~~

No disposition is automatically executed.

## 30. Promotion rules

A finding graduates from autofde-lab when its class becomes known.

### Reusable generator

\[
autofde-lab \rightarrow ggen-marketplace
\]

after deterministic package qualification.

### Reverse-compilation primitive

\[
autofde-lab \rightarrow ggen-create
\]

when it is general exemplar/correspondence functionality.

### Shared protocol invariant

\[
autofde-lab \rightarrow engineering-standards
\]

after independent implementability is demonstrated.

### Evidence profile

\[
autofde-lab \rightarrow affidavit
\]

when it describes certification rather than planning.

### Composition/release policy

\[
autofde-lab \rightarrow ggen-ecosystem
\]

when it governs admitted ecosystem composition.

## 31. Work packages

### IEC-001 — Corpus freeze

Produce the exact v26.9.23 repository manifest and privacy fence.

### IEC-002 — Observation schema

Implement the provenance-bearing semantic observation model.

### IEC-003 — Structural extractor set

Integrate deterministic parsers for the initial language/format corpus.

### IEC-004 — ggen-create federation

Expose ggen-create observation/correspondence/package capabilities as an IEC
adapter rather than duplicating them.

### IEC-005 — Cross-repository correspondence graph

Produce candidate equivalence and provenance edges.

### IEC-006 — Generalization engine

Implement bounded anti-unification and graph generalization.

### IEC-007 — Equivalence court

Implement per-dimension, per-subject translation validation.

### IEC-008 — First regeneration crown

Close IEC-C1 against one exact ggen_igniter subject.

### IEC-009 — Cross-repo collapse crown

Close IEC-C2 against a three-repository family.

### IEC-010 — Intelligence retirement

Close IEC-C3 for one repeated semantic transform.

### IEC-011 — Ecosystem census

Run the full admitted public corpus and produce IEC-C4 coverage artifacts.

### IEC-012 — Promotion plan

Emit destination-specific work orders for durable extracted capabilities.

## 32. Proposed implementation topology

New code SHOULD live under an IEC-specific namespace rather than contaminating
the existing planner APIs before qualification.

Proposed shape:

~~~text
src/autofde_lab/iec/
  __init__.py
  model.py
  corpus.py
  observations.py
  provenance.py
  parsers.py
  correspondence.py
  anti_unification.py
  frontier.py
  cost.py
  manufacture.py
  equivalence.py
  counterexample.py
  retirement.py
  promotion.py

ontology/
  inverse-ecosystem-compiler.ttl
  shapes/
    inverse-ecosystem-compiler.shacl.ttl

tests/iec/
  test_corpus.py
  test_observations.py
  test_correspondence.py
  test_anti_unification.py
  test_equivalence.py
  test_counterexamples.py
  test_retirement.py
  test_ggen_igniter_crown.py
~~~

This is a proposed topology.

Existing repository structure outranks this design if implementation inspection
finds a more lawful native extension point.

## 33. Storage and artifact model

A run SHOULD emit a content-addressed directory:

~~~text
receipts/v26.9.23/iec/<run-id>/
  corpus.json
  observations.jsonl
  semantic-graph.ttl
  candidate-kernel.ttl
  equivalence-candidates.jsonl
  counterexamples.jsonl
  retirement-ledger.jsonl
  disposition-candidates.jsonl
  translation-validations/
  promotion-plan.json
  run-receipt.json
~~~

Generated files are evidence projections, not independent authority sources.

## 34. Verification ladder

Verification proceeds from cheapest to most discriminating:

1. schema and canonicalization;
2. parser/extractor unit tests;
3. deterministic replay;
4. SHACL/ontology admission;
5. ggen-create adapter parity;
6. generated artifact comparison;
7. build/unit tests;
8. integration/protocol tests;
9. bounded runtime/e2e;
10. cross-repository translation validation;
11. held-out generalization;
12. exact-head replay.

A higher rung is not run merely because it is expensive.

It is run because the preceding rung cannot discharge the required claim.

## 35. Metrics

### Coverage

\[
Coverage =
\frac{classified\ admitted\ artifacts}
     {admitted\ artifacts}
\]

### Mechanization ratio

\[
Mechanization =
\frac{known\ recurring\ transforms\ with\ deterministic\ replacements}
     {known\ recurring\ transforms}
\]

### Residue ratio

\[
Residue =
\frac{handwritten\ irreducible\ semantic\ units}
     {semantic\ units}
\]

### Compression

\[
Compression =
\frac{Cost(original\ repeated\ representations)}
     {Cost(kernel+generators+residue)}
\]

### Counterexample yield

\[
CEYield =
\frac{hypotheses\ falsified}
     {active\ hypotheses\ tested}
\]

### LLM retirement

\[
Retirement =
\frac{retired\ repeated\ reasoning\ classes}
     {repeated\ reasoning\ classes}
\]

Metrics do not grant standing.

## 36. Performance objectives

v26.9.23 MUST measure rather than assume performance.

Initial targets are operational envelopes, not standing claims:

- passive corpus observation is incrementally cacheable;
- unchanged subjects do not require full LLM re-analysis;
- deterministic extraction can run independently of Claude;
- the first crown fits within one bounded Claude Cloud grant;
- every expensive semantic call is attributable to one UNKNOWN frontier item;
- repeated semantic calls are visible as retirement debt.

No latency target is admitted until a baseline run exists.

## 37. Failure taxonomy

Typed failures include:

~~~text
BLOCKED_CORPUS_IDENTITY
BLOCKED_MISSING_PARSER
BLOCKED_EXECUTION_AUTHORITY
BLOCKED_VERIFIER_UNAVAILABLE

UNSUPPORTED_LANGUAGE
UNSUPPORTED_GENERATOR_CAPABILITY
UNSUPPORTED_EQUIVALENCE_DIMENSION
UNSUPPORTED_RUNTIME_PROBE

REFUSED_PRIVATE_IDENTITY_LEAK
REFUSED_PATH_ESCAPE
REFUSED_SYMLINK
REFUSED_AMBIGUOUS_AUTHORITY
REFUSED_UNBOUNDED_EQUIVALENCE
REFUSED_DISPOSITION_WITHOUT_REPLACEMENT

BUILD_BROKEN_GENERATED_SUBJECT
COUNTEREXAMPLE_EQUIVALENCE
CONTRADICTED_SEMANTIC_FACT
UNKNOWN_ORIGIN
UNKNOWN_GENERATOR
UNKNOWN_CONSUMER
UNKNOWN_RUNTIME_BEHAVIOR
~~~

One typed failure is one edge in the topology.

It is not evidence that the whole IEC experiment failed.

## 38. Definition of done — v26.9.23

The release is not complete because the PRD/ARD exists.

The v26.9.23 IEC slice is complete only when all of the following are observed:

1. **Corpus identity**
   - exact corpus manifest emitted;
   - no hidden repository movement;
   - public/private boundary verified.

2. **Observation**
   - deterministic repository observations execute;
   - provenance survives normalization;
   - UNKNOWN remains typed.

3. **Reuse**
   - IEC calls or composes current ggen-create for its admitted reverse-compiler
     capability;
   - no parallel exemplar compiler is introduced without a falsifier.

4. **Candidate kernel**
   - at least one cross-file and one cross-repository generalization exists;
   - every inferred fact has provenance and a falsifier.

5. **Manufacture**
   - one non-trivial target is regenerated in isolation;
   - generated versus irreducible residue is explicit.

6. **Translation validation**
   - original and regenerated subjects run through the declared verifier set;
   - all mismatches become preserved counterexamples;
   - the exact passing translation receives a receipt.

7. **Held-out check**
   - one held-out revision or member tests whether the kernel generalizes.

8. **Retirement**
   - one repeated Claude reasoning class is replaced by deterministic machinery;
   - the workflow succeeds without Claude for that class.

9. **Authority**
   - no external merge/delete/archive/deploy occurs from IEC without a separate
     BRCE-authorized path.

10. **Replay**
    - exact-subject replay reproduces the admitted result.

Only the exact satisfied crowns may move to ALIVE.

## 39. Primary falsifiers

The architecture is falsified if any of these are necessary:

- IEC must ignore current ggen-create and rebuild its admitted capability;
- semantic equivalence requires an unbounded "trust the LLM" decision;
- generated code becomes an independent source of truth;
- a repository is declared obsolete without a replacement/equivalence witness;
- UNKNOWN must be collapsed into a guessed semantic fact;
- translation validation cannot bind exact original/generated identities;
- replay necessarily reproduces an external consequence;
- a repeated reasoning class cannot be separated from Claude despite stable
  semantics and a deterministic verifier;
- the proposed kernel is larger or less reusable than the repeated structures
  it replaces under the same cost function;
- the first crown can pass only by weakening an existing repository verifier.

## 40. Claude execution contract for the moonshot run

The recommended Claude job is:

> Recover the smallest bounded semantic kernel that explains the admitted
> behavior of the selected Chatman ecosystem corpus. Treat repositories as
> archaeological evidence, not architecture truth. Reuse existing public
> standards, parsers, formal methods, ggen-create, ggen, ggen-marketplace, and
> framework-native generators before inventing machinery. Every inferred
> equivalence is a candidate until a deterministic/formal court admits it.
> Preserve UNKNOWN and contradictions. For every repeated reasoning operation,
> propose a deterministic replacement and add it to the retirement ledger.
> Do not mutate, merge, archive, delete, publish, deploy, or otherwise perform
> external consequence. Produce counterexamples aggressively. Optimize for the
> amount of future reasoning eliminated, not for lines of code generated.

Claude's output is candidate evidence.

The resulting deterministic artifacts and courts are the intended durable
product.

## 41. References and prior art

The implementation should consult at least:

- Murphy, Notkin, Sullivan, *Software Reflexion Models: Bridging the Gap between
  Design and Implementation*, IEEE TSE 27(4), 2001.
- Alur et al., *Syntax-Guided Synthesis*, FMCAD 2013.
- Pnueli, Siegel, Singerman, *Translation Validation*, TACAS 1998.
- Plotkin/Reynolds anti-unification / least-general-generalization literature.
- Tree-sitter parser and query model for language-aware structural extraction.
- Current ggen-create PRD/ARD and exact-head parity courts.
- Current BRCE RFC and adapter PRs before any consequential extension.

## 42. End-state equation

The desired steady state is:

\[
RepositoryCorpus
\rightarrow
ObservationGraph
\rightarrow
CanonicalKernel
\rightarrow
DeterministicManufacture
\rightarrow
TranslationValidation
\rightarrow
Receipts
\]

with:

\[
RepeatedLLMReasoning \rightarrow 0
\]

for every semantic class that IEC successfully converts from UNKNOWN to known,
admitted machinery.

The terminal success condition is not:

> Claude understands the ecosystem.

It is:

> The ecosystem can reconstruct and verify the understood class without Claude.
