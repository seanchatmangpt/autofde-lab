# Formal delegation/admission transition law

The JSON court checks one evidence snapshot. The formal model checks which snapshots
are reachable when evidence and delegation grow over time.

The bounded model has four capacity counters (Explain, Verify, Modify, Account),
delegated scope, independent-verifier observation, changed-requirement observation,
and standing.

The reference transition system permits `DelegateOne` only when every evidence
capacity already covers the next delegated unit.

TLC checks seven invariants:

- delegation never exceeds Explain capacity;
- delegation never exceeds Verify capacity;
- delegation never exceeds Modify capacity;
- delegation never exceeds Account capacity;
- positive Verify capacity requires an independent verifier observation;
- positive Modify capacity requires a changed-requirement observation;
- standing requires current delegation to remain inside every capacity.

Four one-edge mutants calibrate the court:

- unbounded delegation;
- self-verification;
- Modify evidence without a changed requirement;
- standing without sufficient admission capacity.

The TLA+ text is generated from the repository's canonical `TransitionSystem` IR
and executed by the existing pinned real TLC court. The bound is capacity 3. A green
court is therefore bounded explicit-state evidence, not a mathematical proof and not
production standing.
