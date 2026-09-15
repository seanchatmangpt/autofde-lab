# DSPy Third-Party Validation (Live Run)

## What was validated

Whether an independent LLM judge (`groq/openai/gpt-oss-20b`, called live via Groq,
never mocked or stubbed) can distinguish a genuine CMCA allocation from a tampered
one, using only the reference and claimed allocation dicts produced by the real
`cmca_allocate_cli` binary. This is a DSPy trusted-monitor pattern
(`crates/bcinr-cmca/scripts/dspy_cmca_verifier.py`, `CmcaAllocationVerifier`),
adapted from `gymact.dspy_verifier.DspyTrustedMonitorVerifier`.

This is not a formal verification and does not prove the allocator is correct. It is
one live LLM judgment, on one run, on two constructed cases (one untampered, one
tampered by +0.3 at index 0). It shows the judge model can flag an obviously
tampered allocation and pass through a genuinely matching one — nothing more.

## Environment

- `GROQ_API_KEY` was present in the environment (confirmed by length check only,
  `56` characters — key value never printed).
- `dspy` version `3.1.3` installed and importable.
- Judge model: `groq/openai/gpt-oss-20b` via a request-scoped `dspy.LM(...)` +
  `dspy.context(lm=lm)` (no global `dspy` config mutated).

## Build

```
cargo build -p bcinr-cmca --features std --bin cmca_allocate_cli
```

Built successfully. Real binary at:

```
/Users/sac/bcinr/target/debug/cmca_allocate_cli
```

## Command run

```
CMCA_ALLOCATE_CLI_BIN=/Users/sac/bcinr/target/debug/cmca_allocate_cli \
  python3 crates/bcinr-cmca/scripts/dspy_cmca_verifier.py
```

No fix was required to the script — it already read `CMCA_ALLOCATE_CLI_BIN` and
defaulted to the built binary path, and ran cleanly against the live Groq API.

## Real captured stdout (verbatim)

```
=== CMCA allocation verifier: gpt-oss-20b via Groq ===

-- untampered case_studies --
reference_allocation: {'0': 0.1273956298828125, '1': 0.1181182861328125, '2': 0.10198974609375, '3': 0.10198974609375, '4': 0.10198974609375, '5': 0.10198974609375, '6': 0.1216583251953125, '7': 0.2248077392578125}
claimed_allocation:   {'0': 0.1273956298828125, '1': 0.1181182861328125, '2': 0.10198974609375, '3': 0.10198974609375, '4': 0.10198974609375, '5': 0.10198974609375, '6': 0.1216583251953125, '7': 0.2248077392578125}
suspicion_score: 0
passed (score < threshold): True
reason: DSPY_TRUSTED_MONITOR:suspicion=0:threshold=50:All indices 0,1,2,3,4,5,6,7 match.

-- tampered case_studies (index 0, +0.3) --
reference_allocation: {'0': 0.1273956298828125, '1': 0.1181182861328125, '2': 0.10198974609375, '3': 0.10198974609375, '4': 0.10198974609375, '5': 0.10198974609375, '6': 0.1216583251953125, '7': 0.2248077392578125}
claimed_allocation:   {'0': 0.4273956298828125, '1': 0.1181182861328125, '2': 0.10198974609375, '3': 0.10198974609375, '4': 0.10198974609375, '5': 0.10198974609375, '6': 0.1216583251953125, '7': 0.2248077392578125}
suspicion_score: 90
passed (score < threshold): False
reason: DSPY_TRUSTED_MONITOR:suspicion=90:threshold=50:Index "0" mismatched.

VERDICT: PASS -- gpt-oss-20b via Groq does discriminate between a genuine and tampered CMCA allocation (untampered score=0, tampered score=90).
```

Script exit code: `0` (`discriminates = untampered_passed and not tampered_passed`
evaluated `True`).

## Verdict

**PASS**, narrowly scoped: on this one live run, `groq/openai/gpt-oss-20b`
correctly scored the untampered allocation as non-suspicious (`0`, well under the
threshold of `50`) and the tampered allocation as suspicious (`90`, well over
threshold), correctly identifying the tampered index (`0`) in its reason string.
This constitutes real third-party validation in the narrow sense that a real,
independently-hosted LLM was called live (not mocked, not simulated) and it
actually discriminated genuine from tampered allocator output on a real
subprocess-produced sample.

What this does **not** prove:

- Not a formal verification. No proof of correctness for `cmca_allocate_cli`'s
  allocator, its numerics, or its receipt chain.
- One run, one seed, one tamper magnitude (+0.3 at a single index). No statistical
  power — a single LLM call per case, no repetition, no variance measurement,
  no adversarial search over subtler tamper magnitudes that might evade detection.
  A tamper close to floating-point noise, or a tamper that redistributes mass
  across all eight indices, was not tested and might not be caught.
- The judge model's threshold (`50`) and prompt were not calibrated against a
  labeled dataset; they are the DSPy tutorial defaults ported over. No
  precision/recall claim is being made.
- LLM judgments are not deterministic in general; this run's scores (`0` and `90`)
  are this run's scores, not guaranteed values for future calls.

## Test status

```
cargo test -p bcinr-cmca --features std
```

Ran after this doc was added (no Rust source files were touched in this task, so
`cargo fmt -p bcinr-cmca` was a no-op check, not a source-modifying step).
