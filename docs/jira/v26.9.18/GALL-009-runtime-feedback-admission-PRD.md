# GALL-009 — Runtime Feedback Admission

## Subject

A validated runtime/process/telemetry finding about one exact semantic subject.

## Required transition

```text
validated observation
→ exact subject + source receipt
→ explicit FeedbackRule
→ admitted belief update
→ downstream planning/repair candidate
```

The court does **not** turn feedback into normative law, standing, or authority.

## Acceptance

- subject and source receipt identities are exact SHA-256 digests;
- finding type and evidence class match an explicit rule;
- only rule-named facts may change;
- unknown remains explicit;
- standing/authority/DO facts are unrepresentable through this admission path;
- an admission receipt digest is deterministic;
- applying admitted feedback requires the expected predecessor provenance receipt.

## Falsifiers

- a Weaver/OCEL/model finding directly changes authority or standing;
- a finding updates a fact not named by the rule;
- a finding for another semantic subject is accepted;
- a different evidence class is silently substituted;
- feedback can actuate without GALL-003/BRCE.

## Evidence ceiling

Passing this court proves only deterministic feedback admission into an epistemic belief state. It does not prove the observation itself, authorize repair, execute a consequence, or confer ALIVE standing.
