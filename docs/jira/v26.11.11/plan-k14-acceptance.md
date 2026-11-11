# plan-k14-acceptance

Standing: ALIVE

Subject: ~/plan K14 (autofde-lab) accepted against /Users/sac/autofde-lab on 2026-11-11.
Standing is limited to K14. K16 is BLOCKED/SKIP, and K10/K17/full matrix are not ALIVE here.

## Command

```
cd /Users/sac/plan && PYTHONPATH=pipeline:pipeline/tests uv run --quiet python \
  /Users/sac/autofde-lab/scripts/plan_k14_acceptance.py
```

Exit code: 0 (script exits 1 on mismatch, SKIP, or Traceback).

## K14 results (k14_autofde.py:43-56)

| case | expect | got | detail |
|---|---|---|---|
| pddl-blocks-3 | PLAN | PLAN | rc=0, 4 steps, cost 4 |
| pddl-unsolvable | NO_PLAN | NO_PLAN | rc=1, "no plan exists (search exhausted)" |
| pddl-missing-domain | REFUSED | REFUSED | rc=2, filesystem error |
| fond-strong-cyclic-valid | PLAN | PLAN | valid=true |
| fond-strong-invalid | INFEASIBLE | INFEASIBLE | valid=false |
| fond-empty-policy | INFEASIBLE | INFEASIBLE | missing=[s0] |

Unsolvable case: rc=1, Traceback=False, "no plan exists"=True (stderr empty).

## ~/plan pytest (PLAN_RESULTS_DIR=$(mktemp -d))

`pytest pipeline/tests/test_plankinds_autofde_gymact.py -v`: 4 passed in 9.58s.

Per-kind rows (run_kind):
- K14: 6/6 ok.
- K15: 6/6 ok (bpmn x2, powl x2, explore-cli x2). `~/gymact/.venv` present.
- K16: SKIP, "AZURE_OPENAI_API_KEY set but AZURE_OPENAI_ENDPOINT/AZURE_OPENAI_DEPLOYMENT
  absent" (k16_llm.py:34-40). Satisfiable by exporting those two vars, or by
  ANTHROPIC_API_KEY/OPENAI_API_KEY. It makes a real network call, so it was not forced.

`pytest pipeline/tests/test_plankinds_matrix.py -k "not full_matrix"`: 3 passed, 2 failed.
- K10 fails: probe import failed, no module `pm4pytest` (hint: uv run --with
  /Users/sac/pm4pytest). Not autofde-related.
- K17 fails: no module `hypothesis` (hint: uv run --with hypothesis). Declared dep, installable.
- K1 (k01_aries.py:26 via jtbd_factories.py:17): ModuleNotFoundError `factory`.
- `test_full_matrix` (K1..K17 in one run) was not completed. A combined run of both files
  hung past 600s and was killed (exit 144). Cause not diagnosed. Per-kind statuses for
  K1-K13 are UNVERIFIED.

## Missing from autofde-lab

None found. All paths ~/plan uses exist: `autofde_lab.fabric.pddl_engine` CLI
(k14_autofde.py:73), `autofde_lab.planning.fond_policy` (k14_autofde.py:24), and the blocks
fixtures `tests/domains/python/pddl_domains/blocks/{domain,probBLOCKS-3-0}.pddl`
(k14_autofde.py:15, k16_llm.py:14).
