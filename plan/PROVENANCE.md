# PROVENANCE

Copied from /Users/sac/plan on 2026-11-11 (working tree, not a clean checkout).

- ~/plan HEAD: 9a2f021bc67a432e8fcb1baa65c6d61369e54273
- Excluded: .git, .venv, caches, .results, store/, *.sqlite, node_modules, pm/out,
  executor/receipts.jsonl, planner/plan_solution.soln
- ~/plan git status at copy time (first 20 lines, uncommitted state included in the copy):

```
 M .gitignore
 M Justfile
 M console.py
 M executor/fixtures/servengine_ideal_domain.pddl
 M justfile.d/01-l1.just
 M justfile.d/07-executor.just
 M justfile.d/20-alignment.just
 M justfile.d/30-l3-cpsat.just
 M justfile.d/40-pipeline.just
 M justfile.d/45-ui.just
 M justfile.d/46-plankinds.just
 M justfile.d/47-rules.just
 M justfile.d/50-pm.just
 M justfile.d/90-ledger.just
 M ledger/core.py
 M ledger/tests/test_ledger.py
 M ontology/servengine.ttl
 M pipeline/enterprise_pipeline/align.py
 M pipeline/enterprise_pipeline/alignment_dispatch.mzn
 M pipeline/enterprise_pipeline/pddl.py
```

Renamed 2026-11-13: source checkout ~/plan is now ~/fnox (GitHub seanchatmangpt/plan -> seanchatmangpt/fnox, fnox HEAD b143fed00cc6d78927cb3250dd3b07e10ca5e0af); ~/plan remains as a symlink. The history above cites the old path and is not rewritten.
