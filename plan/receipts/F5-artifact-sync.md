# F5-artifact-sync
Standing: PASS

Base state (no git): drift found by sha1 -- executor/fixtures/servengine_ideal_domain.pddl
(cbf456f3) lagged spec/ (9bdb2a63: wo-no-part-replacement, run-ai-vision-closeout-gate-no-part,
SLA condition); MiniZinc had 3 variants: spec/ + courts/mzn/alignment_dispatch.mzn (76b2e58f,
old unrepaired), alignment/ + courts/mzn/alignment_repaired.mzn (f62a173b), pipeline/ (5ffdf752).

Canonical: PDDL = spec/ (authored, newest). MiniZinc = alignment/alignment_dispatch.mzn
(only copy proven by alignment/run_tests.sh vs expected.json; cpsat diff court reads it).
courts/mzn/alignment_dispatch.mzn left as deliberate unrepaired court input.

Actions: copied spec PDDL -> executor/fixtures; alignment mzn -> spec/ and
pipeline/enterprise_pipeline/. Added pipeline/tests/test_artifact_sync.py (5 sha256 pairs).
No PDDL edited, so ontology/servengine.ttl not regenerated.

Commands: pytest test_artifact_sync.py -> 5 passed; bash alignment/run_tests.sh -> ran=42 failed=0.
