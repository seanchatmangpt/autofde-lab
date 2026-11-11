# STUB-REGISTER

Written by `scripts/stub_register.py`; do not hand-edit. Every count below is
produced by the script from `src/autofde_lab` and
`docs/jira/v26.11.11/stub-dispositions.toml`.

Regenerate: `.venv/bin/python scripts/stub_register.py --write`

Gate: `.venv/bin/python scripts/stub_register.py --check` (exit 1 if any OPEN site,
BLOCKED row without evidence, or CLOSED row whose test file is missing).

## Totals

| status | count |
|---|---|
| OPEN | 0 |
| BLOCKED | 0 |
| CLOSED | 1 |
| ABSTRACT_BY_DESIGN | 83 |
| TOTAL | 84 |

## By category

| kind | OPEN | BLOCKED | CLOSED | ABSTRACT_BY_DESIGN |
|---|---|---|---|---|
| EMPTY_BODY | 0 | 0 | 0 | 65 |
| NIE_BARE | 0 | 0 | 0 | 12 |
| NIE_CALL | 0 | 0 | 1 | 6 |

## By directory (first level under src/autofde_lab)

| directory | OPEN | BLOCKED | CLOSED | ABSTRACT_BY_DESIGN |
|---|---|---|---|---|
| (root) | 0 | 0 | 0 | 6 |
| _cache | 0 | 0 | 0 | 14 |
| adapters | 0 | 0 | 0 | 1 |
| agent | 0 | 0 | 0 | 3 |
| autofde | 0 | 0 | 0 | 1 |
| builders | 0 | 0 | 0 | 6 |
| case_library | 0 | 0 | 0 | 1 |
| companion | 0 | 0 | 0 | 1 |
| fabric | 0 | 0 | 0 | 7 |
| hub | 0 | 0 | 1 | 24 |
| iec | 0 | 0 | 0 | 1 |
| powl | 0 | 0 | 0 | 2 |
| reasoning | 0 | 0 | 0 | 3 |
| receipts | 0 | 0 | 0 | 4 |
| sa2a | 0 | 0 | 0 | 4 |
| sota_factory | 0 | 0 | 0 | 2 |
| wasm | 0 | 0 | 0 | 3 |

## Non-trivial rows (every site not ABSTRACT_BY_DESIGN)

- CLOSED NIE_CALL line 131
  `autofde_lab/hub/solver/dspy_policy/dspy_policy.py::_describe_gym_dict_of_discrete_schema::NIE_CALL` evidence: tests/solvers/python/test_rl_misc_stub_closure_l8_chicago.py
