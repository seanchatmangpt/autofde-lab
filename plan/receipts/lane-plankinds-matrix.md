# lane-plankinds-matrix
Standing: PARTIAL
Subject: /Users/sac/plan (no git; SHA n/a). K10, K17, matrix machinery ALIVE this session;
full K1..K17 matrix UNVERIFIED (other lanes' solver kinds still running, K11-K16 modules absent).

## Files
pipeline/tests/plankinds/k10_pm4pytest.py, k17_stateful.py, pipeline/tests/plan_matrix.py,
pipeline/tests/test_plankinds_matrix.py, justfile.d/46-plankinds.just, docs/PLAN-KINDS.md.
Root justfile line needed (coordinator): `import? 'justfile.d/46-plankinds.just'`.

## Commands and output
`pytest -q -k "not full_matrix" pipeline/tests/test_plankinds_matrix.py` (with playwright etc.,
conftest imports ui_driver): `5 passed, 1 deselected in 1.96s`.

K10: fsm_conformant PLAN; fsm_reordered REFUSED (fitness 0.5); fsm_truncated REFUSED (0.6667);
ocpq_rules_hold PLAN; ocpq_activity_missing REFUSED; sla_within_bound PLAN;
sla_over_bound REFUSED (120s > 60s). 7/7 ok.
K17: runs10 PLAN (25 accepted appends), runs25 PLAN (85 accepted appends). 2/2 ok.

Matrix with registry {K10,K17} only: table rows K10 7/7, K17 2/2; check() raised
`plan matrix not green` listing K1-K9, K11-K16 `MISSING: no plankinds module`.

Full `test_full_matrix` run was stopped after ~8 min: other lanes' ff / up_aries solver
processes were still running; result UNVERIFIED.
