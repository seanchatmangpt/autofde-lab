# OCEL 2.0 projection for admission histories

The history receipt is projected into the repository's native OCEL model.

Objects:

- `DelegationSubject` — exact subject + history receipt identity;
- `AdmissionSnapshot` — one observed admission state;
- `AdmissionTransition` — one adjacent comparison receipt.

Events:

- `AdmissionSnapshotObserved`;
- `AdmissionTransition`;
- `AdmissionFailed` when a snapshot carries admission debt or another
  counterexample.

The projection is deterministic and validated with strict qualifiers. It introduces
no new standing; it exists so OCEL/conformance/process-science machinery can consume
the same receipt chain without reinterpreting the source JSON.
