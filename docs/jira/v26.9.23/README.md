# v26.9.23 — Inverse Ecosystem Compiler

The v26.9.23 architecture authority is
[PRD/ARD — Inverse Ecosystem Compiler](./PRD-ARD-INVERSE-ECOSYSTEM-COMPILER.md).

This directory is planning material only. It creates no implementation standing.

Implementation work orders should be projected into the ecosystem's sJira/XaaS
work graph with repository=seanchatmangpt/autofde-lab, while reusable
capabilities graduate to their owning repositories after qualification.

## Where execution standing lives

Standing is recorded in the ledgers and receipts, never in this directory:

- in-repo: [`docs/STATUS.md`](../../STATUS.md), pass 46;
- cross-repo: [`docs/ecosystem-standing.md`](../../ecosystem-standing.md), pass 6;
- evidence: `receipts/v26.9.23/iec/c1/` (IEC-C1) and `receipts/v26.9.23/iec/c3/`
  (IEC-C3), replayed byte for byte by `tests/iec/test_iec_real_subjects_chicago.py`;
- code: `src/autofde_lab/iec/crowns/` (doctrine in its `CLAUDE.md`).

| Work package | First-execution state (2026-09-23) |
| --- | --- |
| IEC-001 corpus freeze | implemented (`corpus.py`) |
| IEC-002 observation schema | implemented (`model.py`, `census.py`) |
| IEC-003 structural extractors | git objects, EEx, Tera, `ggen.toml`, rdflib; no Tree-sitter |
| IEC-004 ggen-create federation | implemented (`federation.py`); one sibling defect found |
| IEC-005 cross-repo correspondence | `DeclaredOutput` over three syntaxes only |
| IEC-006 generalization engine | n-ary anti-unification with hedge holes (`antiunify.py`) |
| IEC-007 equivalence court | implemented (`court.py`) |
| IEC-008 first regeneration crown | C1 static courts pass on 4 ggen_igniter subjects |
| IEC-009 cross-repo collapse crown | not started |
| IEC-010 intelligence retirement | C3 held-out court passes for one class |
| IEC-011 ecosystem census | not started |
| IEC-012 promotion plan | `receipts/v26.9.23/iec/c1/promotion-plan.json` (4 candidates) |
