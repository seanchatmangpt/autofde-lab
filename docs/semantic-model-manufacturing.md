# Semantic model manufacturing (Semantic ML)

AutoFDE Lab treats machine learning and language models as **semantic codecs and proposal engines, not authorities**.

The governing equation is:

```text
A = mu(O*)
```

`O` is unstructured observation. `Candidate(O*)` is an untrusted graph delta manufactured by a
model. `O*` is admitted semantic state. Artifacts, including trained models, are projections of
`O*` and have no independent standing.

## Semantic ML

In AutoFDE, **Semantic ML** is defined as:

$$\boxed{\text{Semantic ML} = \text{Machine learning whose inputs, outputs, features, training evidence, and qualification are bounded by } \mathcal{O}^*}$$

Unlike traditional ML ($X \rightarrow f_\theta(X) \rightarrow Y$), Semantic ML enforces:

$$\boxed{\pi(\mathcal{O}^*) \rightarrow f_\theta \rightarrow Candidate(\Delta \mathcal{O}^*) \rightarrow \text{Court} \rightarrow \mathcal{O}^{*'}}$$

### The Four Invariants of Semantic ML
1. **Ontology-derived feature space**: $X = \pi(\mathcal{O}^*)$ — Features are projections of admitted semantics, never arbitrary columns invented by AutoML.
2. **Semantic output space**: $Y \subseteq \text{Language}(\mathcal{O}^*)$ — Outputs resolve back to canonical ontology identities rather than free-form text or ungrounded labels.
3. **Standing is external to ML**: $\text{Prediction} \neq \text{Truth}$ — Every model output remains a candidate until the admission court admits it with a cryptographic receipt.
4. **Models are disposable manufacture**: $M = \mu(\mathcal{O}^*, D, \text{Objective})$ — DSPy programs, GLM teachers, TPOT pipelines, scikit-learn models, and AtomVM Erlang projections can all be replaced without mutating the underlying semantic contract.

### Limiting Trajectory (v26.9.14)
```text
lim_{t -> inf} LLMRuntimeDependency(t) = 0
lim_{t -> inf} GPURequirement(t) = 0
```

Where admitted semantics make natural language unnecessary, the steady-state path becomes:
$$\mathcal{O}^* \rightarrow \text{Tiny Semantic Operator} \rightarrow \mathcal{O}^{*'}$$

## Pipeline & Architecture

```text
MANUFACTURE TIME (Bootstrap Only)
---------------------------------
O -> DSPy (GLM-5.3-Flash teacher) -> Candidate(O*) -> Court -> O*
     -> Manufactured Experience Dataset
     -> Bounded TPOT / Sklearn / PEFT search
     -> OptimizationReceipt

RUNTIME (Zero LLM, Zero GPU, Zero Network)
------------------------------------------
pi(O*) -> SemanticFeatureSchema
       -> TinySemanticOperator (Fixed-Point / AtomVM Erlang)
       -> Candidate(Delta O*)
       -> SemanticAdmissionCourt
       -> AdmissionReceipt
```

## Components

- `feature_schema.py`: deterministic `SemanticFeatureSchema` mapping admitted ontology IRIs to integer vectors $\mathbb{Z}^n$.
- `tiny_operator.py`: standalone `TinySemanticOperator`, `TinyOperatorManifest`, and `TinyOperatorReceipt` requiring zero ML dependencies.
- `portable_compiler.py`: pure-Python fixed-point quantization and tabular compilation for linear models and decision trees.
- `atomvm_codegen.py`: compiles learned models into standalone AtomVM BEAM Erlang modules (`semantic_operator_v26_9_14.erl`).
- `parity_court.py`: cross-runtime parity court asserting $Standing_1 = Standing_2 = Standing_3$ across CPU, portable, and AtomVM.
- `contracts.py`: strict candidate, triple, example, and cryptographic receipts (`AdmissionReceipt`, `OptimizationReceipt`, `ModelQualificationRecord`).
- `constrained.py`: JSON Schema for constrained vLLM/OpenAI-compatible generation and fail-closed parsing.
- `admission.py`: known-predicate, provenance, and optional SHACL court; deterministic N-Triples and receipt hashes.
- `evaluation.py`: graph exactness, precision/recall/F1, provenance coverage, unsupported-predicate rate, and Chapman objective.
- `dspy_program.py`: typed DSPy extraction module plus MIPROv2, BootstrapFewShot, and GEPA compilation hooks.
- `sklearn_search.py`: micro-exportable bounded search (`Ω_TPOT_MICRO`) and deterministic baseline ranking.
- `dataset.py`: partitions experience into positive `gold_examples` and negative `contrastive_examples`.
- `distillation.py`: PEFT/TRL LoRA student manufacture and comparative court qualification.
- `loop.py`: orchestrates the closed manufacturing cycle with exact-head replay verification.

The design vocabulary is in `ontology/semantic-model-manufacturing.ttl`; structural shapes live in
`ontology/shapes/semantic-model-manufacturing.shacl.ttl`.

## Installation

The repository's existing `dspy` and `ofmf` extras already provide DSPy and RDF/SHACL machinery.
For the full experimental stack, including current TPOT (the continuation of TPOT2) and LoRA
manufacture:

```bash
uv pip install -e .
uv pip install -r requirements-semantic-models.txt
```

The heavy training dependencies are imported lazily and do not affect ordinary AutoFDE imports.

## DfCM boundaries

1. Public domain ontologies and formal standards are selected before any model search begins.
2. TPOT searches an explicitly bounded light pipeline space; it never creates predicates, classes,
   or authority rules.
3. DSPy optimizes proposal behavior against graph metrics; a high metric score grants no standing.
4. A student model is disposable `A`, regenerated from admitted examples. It is never `O*`.
5. Unknown predicates fail closed. Ontology extension is a separate explicit design/admission act.
6. Refused candidates are prohibited from entering the training corpus.
7. Receipts bind candidate revision to deterministic admitted graph hash for replay.

## Verification

Cheap repository-native verification:

```bash
uv run pytest tests/semantic_models/ -q
```

Optional integration verification after installing the full dependency manifest should additionally
instantiate `build_tpot_classifier()` and a configured DSPy LM; those operations are intentionally
not part of deterministic unit tests because TPOT evolution and model calls are expensive.

No unit test or optimizer result establishes publication, production execution, or ALIVE standing.
