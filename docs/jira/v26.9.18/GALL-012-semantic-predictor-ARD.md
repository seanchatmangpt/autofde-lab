# ARD v26.9.18 — GALL-012: Semantic Predictor

**Status:** DRAFT ARCHITECTURE SPEC
**Release:** v26.9.18
**Repository:** `seanchatmangpt/autofde-lab`
**Owner:** autofde-lab
**Dependencies:** GALL-009 admitted graph, GALL-011 falsifier corpus
**Authority ceiling:** CANDIDATE generation only

## Architecture objective
RDF/graph features can train/evaluate candidate predictors, export deterministic model artifacts through ONNX, and feed Nx/Axon/Ortex or other runtimes while every prediction remains explicitly candidate-only.

## Components
- semantic dataset manufacturer
- baseline model suite
- GNN/GraphSAGE trainer
- model qualification report
- ONNX exporter/parity checker
- candidate inference adapter for Python/Elixir runtimes

## Data/control flow
`Admitted graph/evidence -> features + split -> baseline/GNN training -> qualification/falsifiers -> ONNX artifact -> runtime inference -> CANDIDATE only`

## Invariants
1. Create reproducible graph feature/label extraction from admitted public semantic data and qualified evidence.
2. Establish non-neural baselines using appropriate scikit-learn models before/alongside GraphSAGE/GNN.
3. Split training/validation/test subjects to prevent semantic leakage.
4. Version data schema, feature transform, model, hyperparameters and random seeds.
5. Export qualified supported models to ONNX and verify inference parity within declared tolerance.
6. Allow Elixir Nx/Axon/Ortex consumption where model operators are supported.
7. Prediction output contains score/model identity/evidence class and can only enter candidate selection.
8. GALL-011 mutation/falsifier corpus participates in evaluation.

## Failure/refusal boundaries
- Data leakage => FAIL
- Model/runtime parity outside tolerance => REFUSED
- Unsupported operator => UNSUPPORTED
- Prediction used as admitted fact/authority => architecture failure

## Qualification court
- dataset determinism test
- baseline/GNN held-out evaluation
- leakage mutation test
- ONNX parity test
- candidate-standing enforcement test

## Standing law
[
Observed \neq Admitted,\quad Prediction \neq Fact,\quad Candidate \neq Authority,\quad SELECT \neq DO
]

PASS requires exact-subject positive execution plus the required negative witnesses. No missing layer may be synthesized in this repository merely to satisfy the crown.
