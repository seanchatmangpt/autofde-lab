# RFC v26.9.26 — SBB qualification and architecture court seed

## Ownership
autofde-lab owns executable qualification/falsification experiments for ABB -> SBB resolution.

## Definition of done
1. Implement an ArchitectureQualificationCourt over exact ABB, ArchitectureContract and CandidateSBB subjects.
2. Evaluate semantic, functional, effect, failure, authority, resource, evidence and lifecycle compatibility independently.
3. Produce deterministic QUALIFIED or typed REFUSED evidence; UNKNOWN remains UNKNOWN.
4. Add adversarial worlds for vendor-as-ABB, Pack-as-EA, mutable subject, missing evidence, authority widening, stale contract and equivalence laundering.
5. Add DfCM frontier evaluation over >=2 candidate SBBs; qualification must not collapse selection.
6. Add prior-art reuse/compose/extend/invent decision receipt.
7. Emit qualification artifacts consumable by marketplace/ggen/xaas/affidavit.
8. Benchmark replay determinism and falsifier coverage.

No test result may confer BRCE authority.

## Executable status (repair pass on PR #203)
This is a seed, not a completion claim. Per DoD item:

- DoD 1-3, 5: `src/autofde_lab/enterprise_architecture.py`; positive court
  `tests/fortune5/test_architecture_qualification_court.py`.
- DoD 4, per named world:
  - vendor-as-ABB: `kind` in VENDOR/PRODUCT/ABB, or an exact subject equal to the ABB
    digest, is `VENDOR_AS_ABB`
    (`tests/fortune5/test_architecture_qualification_category.py`).
  - Pack-as-EA: `kind` in PACK/CONTRACT/EA, an exact subject equal to the contract
    digest, or a contract whose ABB and contract digests coincide, is `PACK_AS_EA`
    (same file). Any other kind than `SBB` is `UNKNOWN_KIND`.
  - mutable subject, missing evidence, authority widening, stale contract:
    `tests/fortune5/test_architecture_qualification_adversarial.py`.
  - equivalence laundering: a per-dimension `*_INCOMPATIBLE` refusal (court test) and
    one exact subject under two candidate ids, `SUBJECT_ALIASED` (category test).
    Semantic equivalence proof between distinct subjects is not modelled; it stays
    UNKNOWN, never QUALIFIED.
  - further fail-closed worlds: malformed digests, contract ceiling above CONSTRUCT,
    blank/duplicate/bare-string/unhashable evidence, non-mapping or undeclared
    dimensions, unhashable authority, receipt tamper, stale subject, replay mismatch,
    frontier reordering, duplicate delivery, conflicting candidate ids.
- DoD 6: `prior_art_disposition` receipt binds the findings and the route; non-bool
  findings route to `UNKNOWN`, never `INVENT`.
- DoD 8: `benchmarks/architecture_qualification.py` (replay determinism, falsifier
  coverage over 32 operators, timing) with regression bound
  `tests/fortune5/test_architecture_qualification_bench.py` and host receipt
  `receipts/v26.9.26/architecture-qualification-bench.json`.
- CI: the court step in `.github/workflows/pr-ci.yml` runs on its own `archq` route
  (court module, benchmark, bench receipt, tests, this charter, the workflow); the
  route is itself checked by `tests/fortune5/test_architecture_qualification_route.py`.
- `verify_receipt` is an unkeyed integrity check, not authenticity; authenticity is
  `replay_refusals` against exact inputs.
- Not started: DoD 7 (artifacts consumed by marketplace/ggen/xaas/affidavit);
  consuming chatman-ecosystem#296 semantics; reconciling this module with the existing
  `autofde_lab.fortune5.enterprise_architecture*` modules (open: one semantic owner).
