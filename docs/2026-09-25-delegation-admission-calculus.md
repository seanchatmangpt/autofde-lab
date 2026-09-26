# Delegation / Admission Calculus — arXiv:2609.29473

## Compression

The paper's judgment obligations are treated as an executable admission boundary rather
than an education-only rubric:

```text
Explain -> provenance + ontology + rationale
Verify  -> independent verifier set + receipt
Modify  -> changed-requirement probe + result + replay
Account -> authority + consequence + receipt + replay + standing
```

Each obligation is exact-subject bound and carries `scope_units`: the amount of delegated
work for which that evidence is valid.

The court defines:

```text
AdmissionCapacity = min(
  Explain.scope_units,
  Verify.scope_units,
  Modify.scope_units,
  Account.scope_units
)

AdmissionDebt = max(0, DelegationUnits - AdmissionCapacity)
```

A PASS requires every obligation to pass, verification to be independent, every required
evidence identifier to exist, and `AdmissionDebt = 0`.

## Growth law

When comparing a reference and candidate for the same exact subject, boundary, and authority
scope:

```text
delta(Delegation) <= delta(AdmissionCapacity)
```

Violation yields `DELEGATION_GROWTH_OUTRUNS_ADMISSION_GROWTH`.

This turns “delegation must not outrun verification” into the stronger cross-cutting law that
delegation may not outrun the weakest admission obligation. Verification cannot compensate for
missing provenance, changed-condition evidence, authority, receipt, replay, or standing.

## Why minimum, not average

The obligations are conjunctive. A verifier covering 1,000 delegated units does not authorize
1,000 units if the changed-requirement probe covers 3 or the receipt boundary covers 2.
Averages would manufacture authority from unrelated strength.

## CLI

```bash
PYTHONPATH=src python -m autofde_lab.iec.crowns.delegation_admission \
  candidate.json receipt.json --gate

PYTHONPATH=src python -m autofde_lab.iec.crowns.delegation_admission \
  candidate.json comparison.json --reference reference.json --gate
```

Exit codes:

- `0`: court executed; with `--gate`, gate PASS.
- `3`: well-formed evidence produced a COUNTEREXAMPLE under `--gate`.
- `2`: malformed input or typed refusal (subject/boundary/authority drift).

## Falsifiers

The implementation is falsified if any of these can receive PASS:

1. verification marked non-independent;
2. a missing Explain / Verify / Modify / Account evidence edge;
3. delegation units greater than the minimum evidenced scope;
4. candidate delegation grows faster than admission capacity;
5. comparison changes the exact subject, boundary, or authority scope without refusal.

## Standing ceiling

This court produces technical admission evidence only. It does not grant BRCE DO authority,
production standing, organizational approval, or legal standing. It is suitable as an input to
those boundaries, not a replacement for them.
