# PRD v26.9.18 — GALL-012: Semantic Predictor

**Status:** DRAFT IMPLEMENTATION SPEC
**Release:** v26.9.18
**Repository:** `seanchatmangpt/autofde-lab`
**Owner:** autofde-lab
**Dependencies:** GALL-009 admitted graph, GALL-011 falsifier corpus
**Authority ceiling:** CANDIDATE generation only

## Product outcome
RDF/graph features can train/evaluate candidate predictors, export deterministic model artifacts through ONNX, and feed Nx/Axon/Ortex or other runtimes while every prediction remains explicitly candidate-only.

## Problem
Graph/ML models can reduce planning/search cost, but a prediction must never become semantic truth, authority or standing merely because its score is high.

## Functional requirements
1. Create reproducible graph feature/label extraction from admitted public semantic data and qualified evidence.
2. Establish non-neural baselines using appropriate scikit-learn models before/alongside GraphSAGE/GNN.
3. Split training/validation/test subjects to prevent semantic leakage.
4. Version data schema, feature transform, model, hyperparameters and random seeds.
5. Export qualified supported models to ONNX and verify inference parity within declared tolerance.
6. Allow Elixir Nx/Axon/Ortex consumption where model operators are supported.
7. Prediction output contains score/model identity/evidence class and can only enter candidate selection.
8. GALL-011 mutation/falsifier corpus participates in evaluation.

## Acceptance criteria
1. Baseline and GraphSAGE/GNN metrics are computed on held-out semantic subjects.
2. Training-data permutation/leakage falsifier is detected.
3. ONNX output matches source runtime within declared tolerance on qualification corpus.
4. Unsupported ONNX operator/runtime path returns UNSUPPORTED rather than alternate semantics.
5. Prediction never directly updates O* or authority.
6. Candidate quality improvement is measurable without weakening falsifier recall.

## Evidence product
Emit a content-addressed checkpoint artifact/receipt binding exact repository SHA, predecessor identities, inputs, courts/falsifiers, outputs, standing and evidence ceiling.

## Release rules
Source presence, configuration, hosted workflow definitions and model scores are not runtime standing. UNKNOWN, PARTIAL, REFUSED, BLOCKED and UNSUPPORTED remain typed. Changed identities are changed subjects.

## Definition of done
RDF/graph features can train/evaluate candidate predictors, export deterministic model artifacts through ONNX, and feed Nx/Axon/Ortex or other runtimes while every prediction remains explicitly candidate-only.
