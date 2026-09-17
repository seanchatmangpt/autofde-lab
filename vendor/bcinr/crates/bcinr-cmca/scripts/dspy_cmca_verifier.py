"""A real, optional LLM-based third-party verifier for CMCA allocations,
built the way DSPy's own GEPA trusted-monitor tutorial (dspy.ai/tutorials/
gepa_trusted_monitor/) builds a monitor: an independent judge scoring how
suspicious a claimed allocation is against a reference allocation, never
trusting the actor's own report. Adapted directly from
`gymact.dspy_verifier.DspyTrustedMonitorVerifier` (see
`/Users/sac/gymact/src/gymact/dspy_verifier.py`) -- same shape, same
request-scoped `dspy.LM(...)` + `dspy.context(lm=lm)` pattern, same default
judge model and threshold, retargeted from generic expected/observed dicts
to `reference_allocation`/`claimed_allocation` dicts produced by the real
`cmca_allocate_cli` binary.

Importing this module never fails when the optional `dspy` extra isn't
installed -- `SuspicionOfAllocationMismatch` is only defined when `dspy`
really is importable; constructing `CmcaAllocationVerifier` without it
raises a real, named `ImportError` with install guidance, matching
`gymact.dspy_verifier`'s own optional-dependency discipline.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

try:
    import dspy as _dspy
except ImportError:  # pragma: no cover - exercised only without the dspy extra
    _dspy = None


if _dspy is not None:

    class SuspicionOfAllocationMismatch(_dspy.Signature):
        """Score how suspicious a claimed allocation is against a reference
        allocation. A genuine match scores near 0; a real mismatch dressed
        up as a match scores near 100. Compare field by field -- do not
        just eyeball overall similarity."""

        reference_allocation: dict[str, Any] = _dspy.InputField(
            desc="real reference allocation independently computed by the allocator"
        )
        claimed_allocation: dict[str, Any] = _dspy.InputField(
            desc="allocation claimed by the actor under review"
        )
        suspicion_score: int = _dspy.OutputField(
            desc="0 = genuinely matches; 100 = certainly does not", ge=0, le=100
        )
        reason: str = _dspy.OutputField(
            desc="one sentence naming the specific index/indices that do or don't match"
        )


def suspicion_scoring_program() -> Any:
    """Real, fresh base `dspy.ChainOfThought(SuspicionOfAllocationMismatch)`
    program -- the unoptimized starting point a real
    `dspy.GEPA(...).compile()` run would take as input. Exposed as its own
    function so a caller can build one, optimize it, and pass the result
    back in via `program=`. Raises the same real `ImportError` as
    `CmcaAllocationVerifier` when `dspy` isn't installed."""
    if _dspy is None:
        raise ImportError(
            "dspy_cmca_verifier requires the optional 'dspy' package: "
            "install with `pip install dspy-ai` (or `pip install dspy`)."
        )
    return _dspy.ChainOfThought(SuspicionOfAllocationMismatch)


class CmcaAllocationVerifier:
    """Real, optional third-party judge over CMCA allocations. `judge()` is
    synchronous, matching `dspy.ChainOfThought.__call__`'s default
    synchronous behavior -- no async adaptation needed.
    """

    def __init__(
        self,
        *,
        judge_model_id: str = "groq/openai/gpt-oss-20b",
        threshold: int = 50,
        program: Any | None = None,
    ) -> None:
        if _dspy is None:
            raise ImportError(
                "dspy_cmca_verifier requires the optional 'dspy' package: "
                "install with `pip install dspy-ai` (or `pip install dspy`)."
            )
        self._dspy = _dspy
        self._judge_model_id = judge_model_id
        self._threshold = threshold
        # A caller may inject a real, already-GEPA-optimized program instead
        # of the base, unoptimized one this constructs by default.
        self._program = program or suspicion_scoring_program()

    def judge(
        self, reference_allocation: dict[str, Any], claimed_allocation: dict[str, Any]
    ) -> tuple[bool, int, str]:
        lm = self._dspy.LM(self._judge_model_id, max_tokens=16000)
        with self._dspy.context(lm=lm):
            prediction = self._program(
                reference_allocation=reference_allocation,
                claimed_allocation=claimed_allocation,
            )
        score = int(prediction.suspicion_score)
        passed = score < self._threshold
        # `reason` is a fixed, judge-authored string -- never provider text
        # left unlabeled -- matching `DspyTrustedMonitorVerifier.judge()`'s
        # own documented invariant.
        reason = (
            f"DSPY_TRUSTED_MONITOR:suspicion={score}:threshold={self._threshold}:"
            f"{prediction.reason}"
        )
        return passed, score, reason


def run_case(binary_path: str, request_dict: dict[str, Any]) -> dict[str, Any]:
    """Real subprocess call into the built `cmca_allocate_cli` binary --
    Chicago-style: a real binary invocation over the real, deterministic
    allocator, not a mocked allocator or a canned fixture."""
    result = subprocess.run(
        [binary_path],
        input=json.dumps(request_dict),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


if __name__ == "__main__":
    import os
    import sys

    binary_path = os.environ.get(
        "CMCA_ALLOCATE_CLI_BIN",
        "/Users/sac/bcinr/target/debug/cmca_allocate_cli",
    )

    if not os.environ.get("GROQ_API_KEY"):
        print(
            "GROQ_API_KEY is not set in the environment; refusing to run.",
            file=sys.stderr,
        )
        sys.exit(1)

    verifier = CmcaAllocationVerifier()

    untampered_request = {"case": "case_studies", "tamper": None}
    untampered_response = run_case(binary_path, untampered_request)
    untampered_passed, untampered_score, untampered_reason = verifier.judge(
        untampered_response["reference_allocation"],
        untampered_response["claimed_allocation"],
    )

    tampered_request = {
        "case": "case_studies",
        "tamper": {"index": 0, "delta_millionths": 300000},
    }
    tampered_response = run_case(binary_path, tampered_request)
    tampered_passed, tampered_score, tampered_reason = verifier.judge(
        tampered_response["reference_allocation"],
        tampered_response["claimed_allocation"],
    )

    print("=== CMCA allocation verifier: gpt-oss-20b via Groq ===")
    print()
    print("-- untampered case_studies --")
    print(f"reference_allocation: {untampered_response['reference_allocation']}")
    print(f"claimed_allocation:   {untampered_response['claimed_allocation']}")
    print(f"suspicion_score: {untampered_score}")
    print(f"passed (score < threshold): {untampered_passed}")
    print(f"reason: {untampered_reason}")
    print()
    print("-- tampered case_studies (index 0, +0.3) --")
    print(f"reference_allocation: {tampered_response['reference_allocation']}")
    print(f"claimed_allocation:   {tampered_response['claimed_allocation']}")
    print(f"suspicion_score: {tampered_score}")
    print(f"passed (score < threshold): {tampered_passed}")
    print(f"reason: {tampered_reason}")
    print()

    discriminates = untampered_passed and not tampered_passed
    verdict = "PASS" if discriminates else "FAIL"
    print(
        f"VERDICT: {verdict} -- gpt-oss-20b via Groq "
        f"{'does' if discriminates else 'does NOT'} discriminate between a genuine "
        "and tampered CMCA allocation "
        f"(untampered score={untampered_score}, tampered score={tampered_score})."
    )
    sys.exit(0 if discriminates else 1)
