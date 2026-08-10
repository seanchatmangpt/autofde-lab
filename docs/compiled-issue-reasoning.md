# Compiled Issue Reasoning

AutoFDE Lab can route recurring troubleshooting through a finite diagnostic graph before spending open-ended cognition.

## Calculus

```text
OBSERVE
  -> NORMALIZE
  -> ROUTE
  -> HYPOTHESIZE
  -> ELIMINATE
  -> CONSTRUCT CANDIDATE REPAIR INTENT
  -> VERIFY EVIDENCE CONTRACT
  -> MATCHED | REFUSED_EVIDENCE | FALLBACK_NOVELTY
```

This package does not admit or actuate the repair intent. `mfw`/BRCE remains the authority boundary.

## Compilation criterion

A troubleshooting family belongs on the compiled path when it has all four properties:

1. structured observable evidence;
2. a finite causal/diagnostic graph;
3. bounded repair candidates;
4. a deterministic verifier.

Unknown or metastable causal topology is not forced through the graph. It returns `FALLBACK_NOVELTY`, so cognition can discover a new pattern. Once independently validated, that pattern can be added as another deterministic archetype.

```text
novel issue -> cognition -> validation -> admitted knowledge -> compiled recurrence
```

## MCP tools

`issue_reasoning_catalog` returns the finite archetype inventory and evidence contracts.

`issue_reason` accepts either a list of active evidence symbols or a mapping whose truthy values indicate observed evidence.

Example input:

```json
{"no_endpoints": true}
```

Example candidate result shape:

```json
{
  "route": "MATCHED",
  "archetype": "service_routing",
  "domain": "networking",
  "matched_evidence": ["no_endpoints"],
  "missing_evidence": [],
  "contradictory_evidence": [],
  "hypotheses_considered": [
    "selector_mismatch",
    "target_port_mismatch",
    "backend_unready",
    "endpoint_stale"
  ],
  "hypotheses_eliminated": 3,
  "repair_intent": "construct a service-routing repair candidate",
  "evidence_identity_sha256": "...",
  "candidate_identity_sha256": "...",
  "actuation": "REFUSED"
}
```

The SHA-256 fields are deterministic content identities for evidence and candidate replay. They are **not admission receipts**.

## Current generalized inventory

The initial compiler spans scheduling/capacity, probes/restart loops, service routing, DNS, authorization, resource exhaustion, storage, configuration drift, dependency failure, data/schema validation, software/version compatibility, queue/backpressure, build/toolchain failure, governance/policy, business-process stuck state, and explicit novel causal topology.

The inventory is intentionally extensible: the value proposition is not the first 16 patterns, but the ratchet that continually moves validated recurrence from expensive cognition into deterministic process reasoning.
