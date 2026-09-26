# SWE-Prometheus → Verified Governance Gain (VGG) court — v26.9.25

Source: **SWE-Prometheus: Measuring Engineering Governance Improvements in Real-World Repositories**, arXiv:2609.29465.

## Reused benchmark semantics

SWE-Prometheus fixes a repository snapshot, asks for open-ended engineering-governance improvement, reconstructs base and treated states independently, and scores six governance dimensions:

1. Tests & CI
2. Code Quality Gates
3. Documentation & Collaboration
4. Structure & Maintainability
5. Reproducible Environment
6. Dependency & Security Health

Scores are in `[1,5]`. For each scorable dimension with base score below 5, this court reproduces the paper's headroom-normalized term:

```text
(treated - base) / (5 - base)
```

and reports their mean as `paper.ngi`. A base score of 5 receives no improvement reward but remains in the regression court.

The paper's behavior statuses are retained as `preserved | broken | invalid | unavailable`, and characterization-gate strength is retained as `detected | blind | vacuous | none`.

## Stronger claim boundary

The paper intentionally reports gate strength alongside behavior outcomes. This court turns that distinction into an evidence ceiling:

```text
behavior=broken                    -> BUILD_BROKEN
behavior!=preserved                -> UNKNOWN
clean-environment != PASS          -> PARTIAL_ALIVE
replay != PASS                     -> PARTIAL_ALIVE
any scorable governance regression -> PARTIAL_ALIVE
gate=detected                      -> ALIVE ceiling
gate=blind|vacuous                 -> PARTIAL_ALIVE ceiling
gate=none                          -> UNKNOWN ceiling
```

A `detected` gate must name a mutation-testing receipt. Configuration or a passing check alone cannot manufacture that claim.

`paper.ngi` remains reportable for weak-gate runs. The stronger `vgg.value` is numeric only when all of these hold for the exact base and patch:

- behavior is preserved;
- clean-environment reconstruction is PASS;
- replay is PASS;
- the behavior gate is mutation-detected;
- NGI is positive;
- no scorable dimension regresses.

Otherwise VGG is `UNREPRESENTABLE:EVIDENCE_CEILING`.

This is deliberately not a replacement leaderboard. It separates **paper-compatible measured improvement** from **admitted execution-backed governance gain**.

## Input contract

```json
{
  "schema": "autofde-lab.swe-prometheus-case/1",
  "repository": "owner/repo",
  "base_commit": "<exact immutable base>",
  "patch_digest": "sha256:<patch>",
  "behavior": "preserved",
  "gate_strength": "detected",
  "mutation_receipt_id": "sha256:<mutation-court>",
  "clean_environment": {
    "verdict": "PASS",
    "receipt_id": "sha256:<clean-reconstruction>"
  },
  "replay": {
    "verdict": "PASS",
    "receipt_id": "sha256:<replay>"
  },
  "dimensions": {
    "tests_ci": {"base": 2, "treated": 4, "evidence_status": "pass"},
    "quality_gates": {"base": 2, "treated": 4, "evidence_status": "pass"},
    "docs_collaboration": {"base": 2, "treated": 4, "evidence_status": "pass"},
    "structure_maintainability": {"base": 2, "treated": 4, "evidence_status": "pass"},
    "reproducible_environment": {"base": 2, "treated": 4, "evidence_status": "pass"},
    "dependency_security": {"base": 2, "treated": 4, "evidence_status": "pass"}
  }
}
```

Unavailable, failed, timed-out, or non-applicable evidence is explicit rather than converted into a score.

## CLI

```bash
PYTHONPATH=src python -m autofde_lab.iec.crowns.prometheus \
  case.json \
  receipt.swe-prometheus-vgg.json \
  --gate
```

Exit `0` under `--gate` means the exact submitted case reached the VGG admission threshold. It does **not** imply production standing beyond the recorded base, patch, verifier set, or replay boundary.

## Falsifiers

The VGG gate returns `COUNTEREXAMPLE` when any of the following are observed:

- `BEHAVIOR_BROKEN`
- `BEHAVIOR_NOT_PRESERVED`
- `GOVERNANCE_REGRESSION`
- `CLEAN_ENVIRONMENT_NOT_PASS`
- `REPLAY_NOT_PASS`
- `NON_DISCRIMINATIVE_BEHAVIOR_GATE`
- `NO_NGI_DENOMINATOR`
- `NO_POSITIVE_GOVERNANCE_GAIN`

A claimed `detected` gate without a mutation receipt is a typed refusal: `REFUSED_UNBOUNDED_EQUIVALENCE`.

## Adjacent machinery

This court composes with the existing IEC/RGI machinery rather than introducing another state vocabulary:

- exact subject identity: `git:<repo>@<base_commit>`;
- deterministic content IDs and receipts;
- typed `PASS / COUNTEREXAMPLE / BLOCKED / UNSUPPORTED` verifier results;
- evidence ceilings distinct from raw benchmark scores;
- deterministic CLI serialization.

The next reusable edge is an executor that manufactures the paired clean-environment probe records. That belongs in a generator/pack only after the probe ontology is fixed; the court itself stays independent of any particular CI provider, package manager, or LLM.
