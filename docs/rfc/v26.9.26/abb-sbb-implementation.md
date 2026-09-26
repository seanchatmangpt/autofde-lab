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
