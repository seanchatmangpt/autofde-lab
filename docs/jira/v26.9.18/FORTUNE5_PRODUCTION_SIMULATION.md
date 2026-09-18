# v26.9.18 Fortune-5 Semantic A2A production-system simulation

## Scope

This implementation is a deterministic **simulation and evidence court** for a
Fortune-5-class full-stack estate. It is not connected to real production
infrastructure and carries no organizational or enterprise adoption standing.

The simulation composes:

`G(seed, theta) -> World -> semantic A2A message -> admission -> route/planner
-> authority -> prepared receipt -> actuation -> final receipt -> verification
-> telemetry spans -> OCEL 2.0 -> readiness witness -> replay`.

The Fortune-5 profile generates six multi-cloud regions and 24 service roles
per region (144 service instances) across edge, identity, application, event,
worker, data, cache, search, stream, ML, AI, agent, control, observability,
governance, security, and resilience layers.

## Production surfaces

- deterministic multi-cloud world generator with bounded fault schedules;
- SLO, cost, energy and carbon envelopes;
- semantic A2A messages with ontology/world identity binding;
- UNKNOWN -> frontier candidate -> qualified KnownRoute -> deterministic reuse;
- explicit authority grants and per-round change budgets;
- prepared receipts committed before simulated DO;
- final receipts with pre/post state digests and independent postcondition state;
- idempotency cache preventing duplicate effect;
- HDDL, POWL and FOND projections from the same world identity;
- OTel-shaped span tree for each semantic transition;
- OCEL 2.0 projection and independent authority/receipt/idempotency court;
- atomic artifact bundle with per-file and bundle digests;
- existing TTF5-AR readiness witness;
- zero-dependency HTTP API and HTML operations dashboard.

## Commands

Run the Fortune-5 profile:

```bash
PYTHONPATH=src python -m autofde_lab.fortune5.production run \
  --seed 7 --rounds 40 --scale fortune5 --artifacts artifacts/fortune5-sa2a
```

Run the dashboard/API:

```bash
PYTHONPATH=src python -m autofde_lab.fortune5.production serve \
  --host 127.0.0.1 --port 8080
```

Chicago court:

```bash
PYTHONPATH=src python -m pytest -vv \
  tests/fortune5/test_production_system_chicago.py
```

## Standing boundary

The code is designed so the release court can establish repository-local
simulation standing. It does **not** claim real cloud actuation, customer
acceptance, enterprise deployment, or cross-repository publication. The
GitHub workflow is the exact-head court; only a successful run at an exact
commit should advance this subject beyond candidate/local evidence.
