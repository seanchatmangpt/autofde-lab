# Runbook

## Setup

`just bootstrap` verifies minizinc, uv, python3, just and ortools; exits 1 if any is missing.

## Common commands

- `just ontology`: regenerate and validate `ontology/servengine.ttl` (rdflib + pyshacl via uv).
- `just receipts-lint`: enforce the Standing-line law over `receipts/*.md`.
- `just check`: run every lane gate (`gate-*` or `*-gate` recipes), print a table of exit codes,
  fail on absent modules, missing receipts, or unsupported standing values.

## Failure handling

A red lane in `just check` prints its output tail. Fix the owning lane; do not edit generated
files (`ontology/servengine.ttl`).

## See Also

ARCHITECTURE.md
