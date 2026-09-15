# DSPy Tamper-Magnitude Calibration Sweep (Live Run)

## What this measures

Where does `groq/openai/gpt-oss-20b`'s suspicion-scoring of a claimed CMCA
allocation against the real, independently-computed reference allocation actually
stop noticing a tamper, as the tamper gets smaller? `DSPY_THIRD_PARTY_VALIDATION.md`
established one point on this curve (a large, obvious +0.3 tamper, scored 90/100).
This sweep asks the harder question: how small a tamper still gets caught.

**Scope, stated plainly up front:** one tamper index (index 0, matching the earlier
single-run baseline — this does not calibrate sensitivity across different indices),
one model, 3 real repeats per magnitude, one run of the sweep itself. This is a
calibration snapshot, not a permanent guarantee — a rerun of this exact sweep on a
different day could land somewhat differently, especially at magnitudes where the
detection rate below is not `0%` or `100%`.

## Method

`crates/bcinr-cmca/scripts/dspy_cmca_sweep.py` (built this session, imports
`CmcaAllocationVerifier`/`run_case` from `dspy_cmca_verifier.py` rather than
duplicating them) swept `delta_millionths` at index 0 across
`[300000, 100000, 30000, 10000, 3000, 1000, 300, 100, 30, 10]` — i.e. an absolute
share shift from +0.3 down to +0.00001 — with 3 independent live judge calls per
magnitude, plus 5 independent live judge calls on the untampered case as a
false-positive baseline. All 35 calls succeeded (0 errored/failed calls). Raw
per-call results: `crates/bcinr-cmca/scripts/sweep_results.json`.

## Real results

```
baseline (untampered, n=5/5): mean=0, median=0, false_positive_rate=0.00

 magnitude | mean score |  median score | detection rate | note
---------------------------------------------------------------
    300000 |       90.0 |          90.0 |           1.00 |
    100000 |      100.0 |         100.0 |           1.00 |
     30000 |       80.0 |          80.0 |           1.00 |
     10000 |       80.0 |          80.0 |           1.00 |
      3000 |       20.0 |          20.0 |           0.00 |
      1000 |        5.0 |           5.0 |           0.00 |
       300 |       70.0 |          70.0 |           1.00 |
       100 |       10.0 |          10.0 |           0.00 |
        30 |        0.0 |           0.0 |           0.00 |
        10 |        0.0 |           0.0 |           0.00 |

failed/errored calls: 0 / 35
```

Threshold for "detected" is the verifier's own default: `suspicion_score >= 50`
(`CmcaAllocationVerifier`'s `threshold=50`, same value used throughout this
session — not re-tuned for this sweep).

## The three numbers asked for, and an honest correction to how they're stated

- **False-positive rate (baseline, untampered):** `0.00` (0/5) — the judge never
  flagged a genuine allocation as suspicious across 5 real calls.
- **Magnitude where detection first drops below 100%:** `3000` (0.003 absolute
  share shift), reading the table top-down from the largest magnitude.
- **Magnitude where detection first drops to 0%:** also `3000` by that same
  top-down reading — but this framing implies a clean, monotonic falloff, and
  **the real data is not monotonic**: magnitude `300` scored `70.0` (detected,
  rate `1.00`), sandwiched between `1000` (`5.0`, not detected) and `100`
  (`10.0`, not detected). A single-point re-detection at `300` after two
  consecutive misses is not what a clean sensitivity curve looks like — with only
  3 repeats per magnitude, this is the kind of result that's genuinely ambiguous
  between "the model has some real but noisy signal down to very small
  magnitudes" and "the model is inconsistent/near-random once the tamper drops
  below roughly `10000`–`30000` (0.01–0.03 absolute share) and 300's detection is
  a false positive of the *tampered* case, not a real re-acquisition of signal."

## Consistency with the earlier single-point result

`DSPY_THIRD_PARTY_VALIDATION.md`'s single tampered case used `delta_millionths:
300000` and scored `90`. This sweep's `300000` row: mean `90.0`, median `90.0`,
detection rate `1.00` (both real calls scored 90; consistent, not a discrepancy).

## Honest interpretation

**What this establishes:** the judge reliably catches large tampers (roughly
`>= 10000`, i.e. an absolute share shift `>= 0.01`) and never false-positives on
genuine allocations across the calls made. That's a real, useful floor.

**What this does not establish:** a clean, trustworthy detection boundary below
that. The non-monotonic result at magnitude `300` means this sweep cannot honestly
claim "detection degrades gracefully below X" — the data instead suggests the
judge's behavior in the roughly `10`–`3000` magnitude range is closer to noisy than
to a smooth sensitivity falloff, on 3 repeats per point. Trusting this DSPy layer
to catch a subtle, small-magnitude tamper would be unfounded based on this run.
Whether that's a fundamental model limitation or an artifact of too few repeats per
magnitude is not resolved here — distinguishing those would need more repeats
per magnitude (10+, not 3) at the boundary region specifically, which was not run
in this session's scope.

**Practical takeaway:** this DSPy trusted-monitor pattern is a reasonable
plausibility check for gross tampering, not a substitute for CMCA's own
cryptographic receipt mechanism (`allocation_receipt.rs`'s BLAKE3-based
`seal_allocation_receipt`/`verify_allocation_receipt`), which is deterministic and
exact rather than probabilistic — that remains the load-bearing tamper-evidence
mechanism. This sweep is additional evidence for, not a replacement of, that
existing design choice.

## Reproduce

```bash
cargo build -p bcinr-cmca --features std --bin cmca_allocate_cli
CMCA_ALLOCATE_CLI_BIN=/Users/sac/bcinr/target/debug/cmca_allocate_cli \
  python3 crates/bcinr-cmca/scripts/dspy_cmca_sweep.py
```

Raw data: `crates/bcinr-cmca/scripts/sweep_results.json` (committed alongside this
doc for auditability — not regenerated/overwritten silently by a future run without
review, since it's the primary evidence this document interprets).
