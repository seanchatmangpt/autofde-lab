# Region-Granular Intelligence (RGI) benchmark — v26.9.25

KREX (arXiv:2609.30057) moves GPU isolation from session/command scope to the smallest timing-critical region, then measures both throughput and whether candidate ordering survives. RGI applies the same measurement law to general LLM use.

## Objective

Measure movement from general-LLM execution to admitted machine execution without confusing absence of an LLM call with semantic equivalence or retirement.

The benchmark modes are:

- LLM_NATIVE — baseline execution where a general LLM may own broad regions.
- MACHINE_SERIAL — specialized machinery with no LLM, without concurrency/throughput optimizations.
- REGION_HYBRID — a general LLM is legal only on UNKNOWN semantic regions and only in OBSERVE / SELECT / CONSTRUCT.
- ZERO_LLM — the general LLM is unavailable.

A comparison holds subject, workload_id, and the declared run-scoped edge_universe fixed. Drift is refused rather than normalized.

## Dynamic denominator after IEC-011

IEC-011 in crowns/residue.py provides the static residue inventory: where LLM programs and clients are constructed at an exact commit. It correctly leaves LLMDependencyRatio unrepresentable because static code does not identify reachable execution edges.

RGI adds the missing run-scoped reachability observation. A trace declares an edge_universe and records every executed semantic edge. Coverage is PASS only when every declared edge is observed and no observed edge falls outside the declaration.

Only then does the run receive a numeric:

LLMDependencyRatio(run) = unique GENERAL_LLM edges / declared reachable edges

Standing is OBSERVED_RUN_SCOPE. It is not a production-global reachability claim.

When an LLM event corresponds to an IEC-011 residue edge, instrumentation should use the residue edge id as edge_id. A mechanized replacement keeps the same semantic edge id while changing executor to MACHINE. This joins static residue to dynamic retirement without matching by name.

## Metrics

benchmark_trace() emits:

- edge executions and unique reachable edges,
- machine-closed fraction,
- observed LLM execution fraction,
- run-scoped LLM dependency ratio,
- LLM wall fraction and token count,
- throughput in edges/second,
- LLM leakage,
- LLM-in-DO,
- unreceipted DO,
- reasoning classes still observed on LLM execution.

LLM leakage means GENERAL_LLM ran outside UNKNOWN, or ran in VERIFY / DO.

A ZERO_LLM observation does not write RETIRED_FROM_LLM. IEC-C3 and the retirement ledger remain the only retirement authority.

## Fidelity and ranking preservation

compare_runs() requires a typed external fidelity court receipt before its gate can pass. No receipt means SEMANTIC_FIDELITY_NOT_PASS even when the candidate has zero LLM calls.

When both traces carry rankings, RGI additionally emits pairwise flip rate and Kendall tau, mirroring KREX's use of ordering preservation. Those are observation metrics, not universal fidelity criteria. The typed verifier set remains authoritative for the subject's semantics: SPARQL equality, SHACL conformance, plan validity, SAT/SMT result, TLA+ properties, Lean proof checking, OR feasibility/objective, OCEL conformance, or another bounded verifier.

## Falsifiers

The comparison gate returns COUNTEREXAMPLE when any of these occur:

- candidate edge universe is incomplete,
- typed semantic fidelity is not PASS,
- general LLM executes outside UNKNOWN,
- general LLM appears in DO,
- any DO lacks a receipt,
- MACHINE_SERIAL or ZERO_LLM contains an LLM execution.

Exact-subject, workload, or edge-universe drift is a typed refusal rather than a candidate failure.

## CLI

    PYTHONPATH=src python -m autofde_lab.iec.crowns.rgi       reference.rgi-trace.json       candidate.rgi-trace.json       receipt.rgi-benchmark.json       --fidelity-receipt typed-fidelity-court.json       --gate

Exit 0 means the RGI benchmark gate passed for that exact run-scoped subject and workload. It does not imply production standing or global LLM retirement.
