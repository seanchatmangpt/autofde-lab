# Signature-driven SREGym SOTA rail

This rail treats signatures as falsifiable cognition contracts.

```text
signature revision
  -> exact SREGym revision
  -> disposable kind cluster
  -> public MCP observations
  -> deterministic fact compiler
  -> hypothesis portfolio
  -> mechanically computed epistemic standing
  -> POWL discrimination process
  -> causal closure
  -> diagnosis
  -> POWL mitigation + verification process
  -> SREGym grader
  -> receipt
```

## Invariants

- No GEPA.
- No prompt compilation.
- No benchmark fault taxonomy in cognition.
- The LM proposes evidence relationships; it never owns epistemic standing.
- Multiple `SUPPORTED` hypotheses are **not terminal**.
- `DIAGNOSIS_READY` iff exactly one hypothesis is supported and none is unknown.
- Observation and mitigation structures are represented as POWL v2.
- MCP capabilities are discovered at runtime.
- Consequential activity requires an explicit DO step and a reversible process with verification.
- SREGym owns injection, hidden grading, stage transition, and reset.

## Cost boundary

The deterministic `sregym-signature-court.yml` runs on PRs and makes no model calls.
The kind/Groq benchmark rail is `workflow_dispatch` only in its durable form.

## Exact upstream subject

The initial court pins `SREGym/SREGym@ba07faf1a322f9b6d4a279643bb796aa2f36f64b`.
Changing this revision changes the benchmark subject and requires a new receipt.
