# WS3 CapabilityResolver falsifiers

Each `f0N_*.py` imports the real `../resolve.py` (no mocks) and asserts the
correct behaviour; exit 1 with `WRONG:` means the counterexample reproduces
against the current target. `./run_all.sh` runs them all.

| file | severity | claim attacked |
|---|---|---|
| f01 | BREAKS_CLAIM | composition covers need, non-covering local action selected |
| f02 | BREAKS_CLAIM | prose keyword false positive outranks exact ontology individual |
| f03 | BREAKS_CLAIM | min_keyword_score not enforced after name/description averaging |
| f04 | WEAKENS_CLAIM | chain cost absent from Pareto; cheapest alternative dominated |
| f05 | WEAKENS_CLAIM | Turtle multi-type / rdf:type forms and duplicate-IRI individuals ignored |
| f06 | BREAKS_CLAIM | non-applicable local action beats full-cover marketplace pack |

Not reproduced: no input routed to code generation (`route_to_codegen` is
constant False and no generation kind exists) — that invariant survives.
