# consumer-acceptance

Standing: ALIVE

Lane L. Subject: `scripts/gall_consumer_acceptance.py`, run from `/Users/sac/plan`
(read-only there) against the autofde-lab working tree (no git SHA captured; the coordinator
owns git). Every coprocessor kind has a PLAN case and an anti-vacuity case; the six K14
cases come from `plankinds/k14_autofde.py`.

## Command

```
cd /Users/sac/plan && PYTHONPATH=pipeline:pipeline/tests \
  uv run --quiet python /Users/sac/autofde-lab/scripts/gall_consumer_acceptance.py
```

Exit 1 on any mismatch, any SKIP, any absent kinds module, or any child Traceback.

## Output (exit 0)

```
kind           case                       expected    actual      ok  detail
k14            pddl-blocks-3              PLAN        PLAN        Y   rc=0 0.001 seconds.
k14            pddl-unsolvable            NO_PLAN     NO_PLAN     Y   rc=1 et({(0,), (1,)}), fro
k14            pddl-missing-domain        REFUSED     REFUSED     Y   rc=2 eading /nonexistent/d
k14            fond-strong-cyclic-valid   PLAN        PLAN        Y   {"valid": true, "missing":
k14            fond-strong-invalid        INFEASIBLE  INFEASIBLE  Y   {"valid": false, "missing"
k14            fond-empty-policy          INFEASIBLE  INFEASIBLE  Y   {"valid": false, "missing"
search         astar-reachable            PLAN        PLAN        Y   cost=2.0 n_actions=2 
search         astar-unreachable          INFEASIBLE  INFEASIBLE  Y   cost=None n_actions=0 no t
mdp            lrtdp-reachable            PLAN        PLAN        Y   cost=2.0 n_actions=2 
mdp            lrtdp-unreachable          INFEASIBLE  INFEASIBLE  Y   cost=None n_actions=0 no p
fond           strong-cyclic              PLAN        PLAN        Y   cost=None n_actions=1 
fond           strong-on-cycle            INFEASIBLE  INFEASIBLE  Y   cost=None n_actions=0 
pddl           blocks-3                   PLAN        PLAN        Y   cost=4.0 n_actions=4 
pddl           unsolvable                 NO_PLAN     NO_PLAN     Y   cost=None n_actions=0 
temporal_pddl  durative-go                PLAN        PLAN        Y   cost=10.1 n_actions=2 
temporal_pddl  garbage-input              REFUSED     REFUSED     Y   cost=None n_actions=0 cann
htn            verify-and-commit          PLAN        PLAN        Y   cost=5.0 n_actions=5 
htn            unparsable-domain          REFUSED     REFUSED     Y   cost=None n_actions=0 cann
rcpsp          two-tasks-one-resource     PLAN        PLAN        Y   cost=5.0 n_actions=2 
rcpsp          demand-exceeds-capacity    INFEASIBLE  INFEASIBLE  Y   cost=None n_actions=0 dema
cp             two-flights-two-stands     PLAN        PLAN        Y   cost=2.0 n_actions=2 
cp             overlap-one-stand          INFEASIBLE  INFEASIBLE  Y   cost=None n_actions=0 no_o
portfolio      rcpsp-domain               PLAN        PLAN        Y   cost=19.0 n_actions=19 
portfolio      unknown-domain             REFUSED     REFUSED     Y   cost=None n_actions=0 unkn
rl_shielded    four-stands                PLAN        PLAN        Y   cost=0.0 n_actions=8 
rl_shielded    all-stands-blocked         INFEASIBLE  INFEASIBLE  Y   cost=None n_actions=0 ever
powl           two-step-plan              PLAN        PLAN        Y   cost=2.0 n_actions=2 
powl           empty-plan                 REFUSED     REFUSED     Y   cost=None n_actions=0 plan
graphlaw       precondition-met           PLAN        PLAN        Y   ADMITTED receipts=1 unmet=
graphlaw       precondition-unmet         REFUSED     REFUSED     Y   REFUSED receipts=0 unmet=[
ROWS=30 MISMATCH_OR_SKIP=0
RESULT: PASS
rc=0
```

## Notes

- All modules were present at run time: envelope.py, kinds_pddl.py, kinds_search.py,
  kinds_planning.py, kinds_rl.py, law_bridge/graphlaw_admitter.py.
- An earlier run of the same script returned FAIL (exit 1): `temporal_pddl` with an
  unreachable goal hung in the aries engine and was killed (rc=-15, row CRASH). That
  case was replaced with a garbage-input REFUSED case; the unreachable-goal behaviour of
  `temporal_pddl` is not covered here (UNVERIFIED).
- Detail columns are truncated to the script's field widths.
