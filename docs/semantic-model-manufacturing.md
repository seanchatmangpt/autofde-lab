# Semantic model manufacturing

AutoFDE Lab treats business language models as semantic codecs, not authorities.

The governing equation is:

```text
A = mu(O*)
```

`O` is unstructured observation. `Candidate(O*)` is an untrusted graph delta manufactured by a
model. `O*` is admitted semantic state. Artifacts, including trained models, are projections of
`O*` and have no independent standing.

## Pipeline

```text
O
  -> DSPy semantic extractor / distilled student
  -> strict CandidateGraphDelta JSON
  -> optional sklearn/TPOT2 advisory ranking
  -> known-predicate + provenance + SHACL admission
  -> ADMITTED | REFUSED receipt
  -> O*
  -> admitted SemanticExample corpus
  -> DSPy optimization and/or TRL+PEFT LoRA manufacture
  -> next candidate
```

The loop is deliberately asymmetric: optimization may manufacture candidates, but only the
admission court may change `O*`.

## Components

- `contracts.py`: strict candidate, triple, example, and receipt contracts with canonical hashes.
- `constrained.py`: JSON Schema for constrained vLLM/OpenAI-compatible generation and fail-closed parsing.
- `admission.py`: known-predicate, provenance, and optional SHACL court; deterministic N-Triples and receipt hashes.
- `evaluation.py`: graph exactness, precision/recall/F1, provenance coverage, unsupported-predicate rate, and the semantic optimization objective.
- `dspy_program.py`: typed DSPy extraction module plus MIPROv2, BootstrapFewShot, and GEPA compilation hooks.
- `sklearn_search.py`: deterministic sklearn baseline and bounded TPOT2/current-TPOT light search. Predictions are advisory only.
- `dataset.py`: only `ADMITTED` receipts can manufacture DSPy/distillation examples.
- `distillation.py`: TRL + PEFT LoRA student manufacture from admitted examples.
- `pipeline.py`: provider-neutral orchestration from observation to receipt.

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
