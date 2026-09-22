# Semantic A2A graph-learning candidate projection

## Subject

This surface adds graph neural network inference to Semantic A2A as an
**exploration-only candidate manufacturer**.

The authority boundary is:

```text
canonical RDF / public ontology
  -> semantic feature projection
  -> GraphSAGE link scoring
  -> Standing.CANDIDATE edge
  -> SA2A AdmissionPipeline
  -> SELECT / CONSTRUCT / authority
  -> BRCE
  -> DO
  -> receipt / replay
```

There is deliberately no path from a learned score directly to ADMITTED,
AUTHORIZED, PREPARED, EXECUTED, RECEIPTED, or ATTESTED standing.

## Prior art

The design is grounded in Färber, Lamprecht, and Susanti,
*Bridging RDF Knowledge Graphs with Graph Neural Networks for Semantically-Rich
Recommender Systems* (arXiv:2506.08743). The paper's useful architectural result
for SA2A is the separation and combination of:

- RDF object-property topology;
- RDF datatype/content features;
- heterogeneous graph structure;
- GNN link prediction.

This repository does **not** create a private RDF vocabulary to reproduce that
pipeline. The canonical RDF/public ontology remains outside the learned
projection. A caller supplies:

- source_graph_identity: identity of the canonical semantic graph;
- feature_projection_identity: identity of the transform from semantic graph to
  numeric node features;
- node_ids / edges / feature vectors.

That allows an AutoRDF2GML-compatible or other standards-grounded feature
pipeline to be added later without changing the SA2A authority law.

## Objects

### SemanticFeatureGraph

A model-ready projection containing node identity, numeric feature vectors, edge
indices, source graph identity, and feature-projection identity. It is a
projection, not semantic truth.

### GraphSAGECandidateScorer

A real torch-geometric two-layer GraphSAGE encoder with dot-product link
scoring. Initial weights can be deterministically seeded for bounded exploration;
externally trained weights can be loaded with load_state_dict(). Current
parameter tensors are content-addressed into model_identity.

torch and torch-geometric already exist in the repository's solvers dependency
surface; this PR does not create a second dependency declaration.

### CandidateEdge / CandidateBatch

Every learned proposal is hard-fenced to:

```text
standing = CANDIDATE
authorizes_actuation = false
```

Those fields are not caller-settable constructor arguments. Model score,
graph identity, feature projection identity, and model identity remain attached
to each hypothesis.

CandidateEdge.as_rdflib_graph() creates a real RDF triple only so the existing
AdmissionPipeline can evaluate the hypothesis. Creating the RDF graph does not
change the candidate's standing.

## Deterministic replay

Candidate ranking is independent of caller order:

1. observed edges are excluded by default;
2. duplicate candidate pairs collapse to their maximum score;
3. score must be a finite probability in [0, 1];
4. ranking is by descending score, then semantic node identity;
5. top-k is applied only after canonical ranking.

GraphSAGE construction uses a scoped torch RNG context so creating an
exploratory scorer does not mutate the caller's ambient RNG state. The exact
model architecture and current weights are content-addressed into
model_identity.

## Falsifiers

The implementation is wrong if any of these observations occur:

- a GNN result can self-assert standing beyond CANDIDATE;
- a GNN result can set authorizes_actuation=true;
- the same model weights, graph projection, and candidate set replay to a
  different ranked result in the same deterministic runtime;
- an already-observed edge is emitted when exclude_observed=true;
- an unknown node can enter a candidate pair without refusal;
- feature vectors with inconsistent dimensions or non-finite values are
  accepted;
- a model score outside [0, 1] is accepted;
- converting a learned candidate to RDF mutates its standing to ADMITTED;
- learned inference bypasses AdmissionPipeline or BRCE.

## Narrow court

```bash
PYTHONPATH=src python -m pytest -vv tests/sa2a/test_graph_learning.py
```

The test uses the real AdmissionPipeline. When torch and torch-geometric are
available it also executes the real GraphSAGE modules; no mocks, patching, or
monkeypatching are used.

## Evidence ceiling

This change can establish repository-local standing for deterministic
GraphSAGE-to-CANDIDATE projection and the candidate/admission authority fence
once the exact-head court executes successfully.

It does not establish model quality on an enterprise dataset, trained-weight
qualification, cross-repository SA2A standing, production deployment, merge,
publication, or real-world actuation.
