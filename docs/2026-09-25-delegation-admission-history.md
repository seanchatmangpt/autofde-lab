# Delegation/admission history court

Admission is not permanent merely because a prior snapshot passed. Evidence may be
revoked, scopes may shrink, and delegation must contract accordingly.

The history court accepts a contiguous sequence of delegation/admission artifacts.
For every snapshot it runs the base court; for every adjacent pair it runs the
comparison court while conserving subject, boundary, and authority scope.

Additional temporal falsifiers:

- `SNAPSHOT_ADMISSION_FAILURE` — any snapshot has admission debt or missing evidence;
- `STANDING_SURVIVED_ADMISSION_FAILURE` — ALIVE/PARTIAL_ALIVE is retained on a
  snapshot that no longer passes;
- `CAPACITY_REVOKED_WITH_LIVE_DELEGATION` — evidence capacity falls below still-live
  delegated scope;
- existing positive-growth falsifiers are propagated from the comparison court.

Safe contraction is explicitly lawful. The growth inequality applies to positive
delegation growth; reducing delegation after evidence loss must not be rejected
merely because admission capacity fell by a larger absolute amount.

The receipt contains a content-addressed chain over snapshot and comparison receipt
identities plus peak delegation, minimum capacity, capacity-loss count, and
`admission_debt_area` across the history.
