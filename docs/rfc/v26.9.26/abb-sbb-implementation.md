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

## Executable status (harden pass on PR #203)
- DoD 1-3, 5-6: `src/autofde_lab/enterprise_architecture.py`; positive court
  `tests/fortune5/test_architecture_qualification_court.py`.
- DoD 4 adversarial worlds, fail-closed: malformed/wrong digests, DO under any ceiling,
  contract ceiling above CONSTRUCT, blank/duplicate evidence, non-bool mutability,
  undeclared/malformed dimensions, receipt tamper, stale subject, replay mismatch,
  frontier reordering, duplicate delivery and conflicting candidate ids:
  `tests/fortune5/test_architecture_qualification_adversarial.py`.
- DoD 8: `benchmarks/architecture_qualification.py` (replay determinism, falsifier
  coverage, timing) with regression bound
  `tests/fortune5/test_architecture_qualification_bench.py` and host receipt
  `receipts/v26.9.26/architecture-qualification-bench.json`.
- DoD 7 (artifacts consumed by marketplace/ggen/xaas/affidavit): not started.
