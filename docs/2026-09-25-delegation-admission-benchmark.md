# Delegation/admission mutation and stress court

The snapshot court answers whether one candidate has enough evidence to support its
delegated scope. The benchmark tests the *admission machinery itself*.

## Mutation court

Starting from one PASS witness, eight single-edge mutations are applied:

1. delete Explain provenance;
2. make Verify self-grading;
3. delete the Verify receipt;
4. delete the Modify change identity;
5. change Modify to COUNTEREXAMPLE;
6. delete Account authority;
7. delete Account replay;
8. drift the Verify subject.

Every mutation has one required typed falsifier. The mutation court passes only at
kill rate 1.0.

## Capacity sweep

For every pair in the bounded grid:

```text
delegation_units in [0, N]
scope_units      in [0, N]
```

all four evidence scopes are set to `scope_units`. The observed court verdict must
exactly equal:

```text
PASS <=> delegation_units <= scope_units
```

The default N=32 executes 1,089 exact court evaluations. This catches off-by-one,
inverted-comparator, and accidental-average implementations of the minimum-capacity
law.

## CLI

```bash
PYTHONPATH=src python -m autofde_lab.iec.crowns.delegation_admission_benchmark \
  candidate.json benchmark-receipt.json --max-units 32 --gate
```

The receipt is deterministic and content-addressed. PASS proves only the bounded
court properties above; it does not establish production standing.
