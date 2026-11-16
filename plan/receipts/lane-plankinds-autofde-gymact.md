# Lane receipt: plankinds K14 autofde-lab, K15 gymact, K16 LLM
Standing: PARTIAL

Subject: /Users/sac/plan (no git state read). Repos invoked read-only via uv:
/Users/sac/autofde-lab (`uv sync` ok, 5m30s), /Users/sac/gymact (`uv sync` ok; K15 runs
with `--extra bpmn` because spiffworkflow is an optional extra; default sync lacks it).

## Command and output

    cd /Users/sac/plan && PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest \
      --with playwright pytest -q -p no:cacheprovider \
      pipeline/tests/test_plankinds_autofde_gymact.py
    4 passed in 13.14s

The exact command given in the contract (without `--with playwright`) fails at conftest
import: `ModuleNotFoundError: No module named 'playwright'` (pre-existing, conftest.py:11
imports ui_driver).

## Rows (real subprocess results; expect == status for all runnable)

    K14 pddl-blocks-3            PLAN       rc=0 plan found, 4 steps cost 4
    K14 pddl-unsolvable          NO_PLAN    rc=1 (see caveat)
    K14 pddl-missing-domain      REFUSED    rc=2 open() failed
    K14 fond-strong-cyclic-valid PLAN       valid=true
    K14 fond-strong-invalid      INFEASIBLE valid=false
    K14 fond-empty-policy        INFEASIBLE missing=[s0]
    K15 bpmn-simple-sequential   PLAN       Task_A,Task_B,EndEvent_1 completed
    K15 bpmn-unknown-process     REFUSED    BPMN_PARSE_OR_SPEC_LOOKUP_FAILED
    K15 powl-conformant-trace    PLAN       conforms=True
    K15 powl-nonconformant-trace INFEASIBLE div=b enabled=('a',)
    K15 explore-cli-fixture      PLAN       rc=0 evaluations=5
    K15 explore-cli-bad-request  REFUSED    rc=1 pydantic extra_forbidden
    K16 -                        SKIP       AZURE_OPENAI_API_KEY set but
        AZURE_OPENAI_ENDPOINT/AZURE_OPENAI_DEPLOYMENT absent

## Caveats

- pddl-unsolvable: the engine exits rc=1 via an uncaught AttributeError
  ('ImplicitSpace' object has no attribute 'sample') on a cyclic-goal problem, not a clean
  "no plan" path. Mapped via the documented rc=1 contract; an autofde-lab engine defect.
- A malformed problem file (truncated PDDL) also yields rc=1, not rc=2 (parser accepted it).
- K16: run() implemented (anthropic/openai/azure chat call, plan parse) but never executed
  here; no usable endpoint. Install hint: export AZURE_OPENAI_ENDPOINT and
  AZURE_OPENAI_DEPLOYMENT (or ANTHROPIC_API_KEY).
- Not wired (inventory paths differed from the contract: fabric/, sota_factory/ live under
  src/autofde_lab/): RCPSP, MDP, POWL benchmarks, HDDL, pairwise_covering, replan episode.
- UNSUPPORTED_KINDS exported by k14/k15: SAT/SMT, behavior trees, executable state machine,
  replanning, preference planning, fast-downward, VAL; the test asserts the lists.
  Note plan_matrix.py only emits UNSUPPORTED rows from run_kind results; these lists are
  exported, not yet emitted as rows.

## Files

pipeline/tests/plankinds/k14_autofde.py, k15_gymact.py, k16_llm.py,
pipeline/tests/test_plankinds_autofde_gymact.py, this receipt.
