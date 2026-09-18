# GymAct

GymAct is AutoFDE Lab's bounded benchmark-world transition substrate.

```text
admitted intent -> authority check -> bounded transition -> observation -> verification -> score -> receipt
```

A transition request may be refused. Refusal is a typed outcome and remains distinct from unsupported behavior or transport failure.

## Authority law

GymAct uses only the authority carried by the admitted episode. Benchmark authorization is scoped to the benchmark subject and must not be generalized to production systems.

## Evidence stages

1. **Acknowledgement** — the transition surface accepted a request.
2. **Observed transition** — a world-state change was observed.
3. **Verification** — the required postcondition was tested.
4. **Score** — the episode objective evaluated the result.
5. **Receipt** — identity, authority, consequence, verifier, and replay material were bound.
6. **Standing** — the receipt supports a scoped claim.

Acknowledgement is not an observed transition; an observed transition is not verification; a score is not standing.

## Generated surfaces

Where GymAct uses RDF, queries, and ggen templates, those sources own generated projections. Regenerate projections from their canonical source rather than editing derived output.
