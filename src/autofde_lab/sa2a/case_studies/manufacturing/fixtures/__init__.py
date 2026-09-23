"""fixtures -- compact evidence artifacts for the sa2a manufacturing baseline (MFG-01A).

round14.mmd / round14_e2o.mmd: Mermaid renderings of round 14 of a seed=1 run.
round14_ocel_slice.json: the OCEL 2.0 JSON slice those diagrams were rendered
from -- every object/event whose timestamp_ns falls in round 14 (14_000_000
<= timestamp_ns < 15_000_000), sliced from a fresh runtime.run(seed=1) at
migration time. Committed because it is small (a few KB); the full
200-round per-seed logs are not committed -- see MIGRATION_PLAN.md Section 3.
"""
