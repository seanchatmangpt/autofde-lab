"""DGF-Bench deterministic substitution and retirement accounting.

The harness reuses DGF-Bench's executable evaluator.py as the policy kernel.
It performs no model calls and receipts both policy bytes and corpus bytes.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Sequence


@dataclass(frozen=True, slots=True)
class DGFCaseScore:
    case_id: str
    case_dir: str
    gate_total: int
    gate_matches: int
    route_match: bool
    output_digest: str = ""

    @property
    def gate_success_rate(self) -> float:
        return self.gate_matches / self.gate_total if self.gate_total else 0.0


@dataclass(frozen=True, slots=True)
class DGFSubstitutionSummary:
    cases: int
    routes_passed: int
    gates: int
    gates_passed: int
    kernel_digest: str = ""

    @property
    def route_success_rate(self) -> float:
        return self.routes_passed / self.cases if self.cases else 0.0

    @property
    def gate_success_rate(self) -> float:
        return self.gates_passed / self.gates if self.gates else 0.0

    def to_dict(self) -> dict[str, int | float | str]:
        return {
            **asdict(self),
            "route_success_rate": self.route_success_rate,
            "gate_success_rate": self.gate_success_rate,
        }


@dataclass(frozen=True, slots=True)
class DGFRunReceipt:
    kernel_digest: str
    dataset_digest: str
    case_count: int
    gate_count: int
    routes_passed: int
    gates_passed: int
    llm_calls: int = 0

    @property
    def standing(self) -> str:
        return (
            "ALIVE"
            if self.case_count > 0
            and self.gate_count > 0
            and self.routes_passed == self.case_count
            and self.gates_passed == self.gate_count
            else "PARTIAL_ALIVE"
        )

    def to_dict(self) -> dict[str, str | int]:
        return {**asdict(self), "standing": self.standing}


@dataclass(frozen=True, slots=True)
class ResidualWorkInputs:
    exception_share: float
    exception_effort_multiplier: float
    ordinary_review_multiplier: float
    rework: float
    automation_support: float
    baseline_overhead: float = 0.0


def residual_work_ratio(inputs: ResidualWorkInputs) -> float:
    values = asdict(inputs)
    if not 0.0 <= inputs.exception_share <= 1.0:
        raise ValueError("exception_share must be in [0, 1]")
    if any(not math.isfinite(value) for value in values.values()):
        raise ValueError("residual-work inputs must be finite")
    for name, value in values.items():
        if name != "exception_share" and value < 0:
            raise ValueError(f"{name} must be non-negative")

    numerator = (
        inputs.exception_share * inputs.exception_effort_multiplier
        + (1.0 - inputs.exception_share) * inputs.ordinary_review_multiplier
        + inputs.rework
        + inputs.automation_support
    )
    return numerator / (1.0 + inputs.baseline_overhead)


class DGFAdmissionError(ValueError):
    """Typed refusal raised when a DGF run cannot be admitted as evidence."""

    def __init__(self, refusal_code: str, detail: str) -> None:
        self.refusal_code = refusal_code
        super().__init__(f"{refusal_code}: {detail}")


@dataclass(frozen=True, slots=True)
class DGFKernel:
    """The executable DGF policy, bound to the exact bytes that were executed."""

    evaluator_path: str
    digest: str
    module: ModuleType


def _evaluator_path(dgf_root: Path) -> Path:
    evaluator_path = dgf_root / "evaluator.py"
    if not evaluator_path.is_file():
        raise FileNotFoundError(f"DGF evaluator not found: {evaluator_path}")
    return evaluator_path


def _digest_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def dgf_evaluator_digest(dgf_root: Path) -> str:
    """Bind a run to the exact executable policy bytes used for evaluation."""
    return _digest_bytes(_evaluator_path(dgf_root).read_bytes())


def load_dgf_kernel(dgf_root: Path, *, expected_digest: str | None = None) -> DGFKernel:
    """Read evaluator.py once, hash those bytes, and execute those same bytes.

    Hashing and executing one byte string closes the window in which the file
    could change between the digest and the import (stale-subject receipt).
    """
    evaluator_path = _evaluator_path(dgf_root)
    payload = evaluator_path.read_bytes()
    digest = _digest_bytes(payload)
    if expected_digest is not None and digest != expected_digest:
        raise DGFAdmissionError(
            "KERNEL_DIGEST_MISMATCH",
            f"expected {expected_digest}, evaluator.py is {digest}",
        )

    module = ModuleType("autofde_lab_dgf_reference_evaluator")
    module.__file__ = str(evaluator_path)
    exec(compile(payload, str(evaluator_path), "exec"), module.__dict__)  # noqa: S102
    if not callable(getattr(module, "evaluate_route", None)):
        raise AttributeError(
            "DGF evaluator.py must expose evaluate_route(case, occurrences)"
        )
    return DGFKernel(evaluator_path=str(evaluator_path), digest=digest, module=module)


def assert_evaluator_digest(dgf_root: Path, expected: str) -> str:
    actual = dgf_evaluator_digest(dgf_root)
    if actual != expected:
        raise DGFAdmissionError(
            "KERNEL_DIGEST_MISMATCH",
            f"DGF_EVALUATOR_DIGEST_MISMATCH:expected={expected}:actual={actual}",
        )
    return actual


def _load_evaluator(dgf_root: Path) -> ModuleType:
    return load_dgf_kernel(dgf_root).module


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DGFAdmissionError("DGF_MALFORMED", f"{path}: {exc}") from exc


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _require(mapping: Any, key: str, path: Path) -> Any:
    if not isinstance(mapping, dict) or key not in mapping:
        raise DGFAdmissionError("DGF_MALFORMED", f"{path}: missing {key!r}")
    return mapping[key]


def run_dgf_case(
    case_dir: Path,
    *,
    dgf_root: Path,
    kernel: DGFKernel | None = None,
) -> DGFCaseScore:
    """Re-run one DGF case through its executable deterministic policy."""
    hidden_path = case_dir / "99_hidden_ground_truth.json"
    manifest_path = case_dir / "01_route_manifest.json"
    hidden = _read_json(hidden_path)
    manifest = _read_json(manifest_path)

    canonical_truth = _require(hidden, "canonical_truth", hidden_path)
    expected = _require(hidden, "reference_decisions", hidden_path)
    occurrences = _require(manifest, "occurrences", manifest_path)
    if not isinstance(expected, list):
        raise DGFAdmissionError(
            "DGF_MALFORMED", f"{hidden_path}: reference_decisions must be a list"
        )
    if not isinstance(occurrences, list):
        raise DGFAdmissionError(
            "DGF_MALFORMED", f"{manifest_path}: occurrences must be a list"
        )
    # Anti-vacuity: a case with no gates or no reference decisions cannot
    # witness substitution, and a count mismatch is a broken contract.
    if not occurrences:
        raise DGFAdmissionError(
            "DGF_CASE_HAS_NO_GATE_OCCURRENCES", str(case_dir)
        )
    if not expected:
        raise DGFAdmissionError(
            "DGF_CASE_HAS_NO_REFERENCE_DECISIONS", str(case_dir)
        )
    if len(occurrences) != len(expected):
        raise DGFAdmissionError(
            "DGF_CASE_CONTRACT_COUNT_MISMATCH",
            f"{case_dir}: occurrences={len(occurrences)}:"
            f"reference={len(expected)}",
        )

    active = kernel if kernel is not None else load_dgf_kernel(dgf_root)
    actual = active.module.evaluate_route(canonical_truth, occurrences)
    if not isinstance(actual, (list, tuple)):
        raise DGFAdmissionError(
            "DGF_MALFORMED",
            f"evaluate_route returned {type(actual).__name__}, not a route list",
        )
    actual = list(actual)

    gate_total = max(len(actual), len(expected))
    gate_matches = sum(
        1
        for got, want in zip(actual, expected, strict=False)
        if _canonical(got) == _canonical(want)
    )
    route_match = len(actual) == len(expected) and gate_matches == gate_total

    return DGFCaseScore(
        case_id=str(hidden.get("case_id", case_dir.name)),
        case_dir=str(case_dir),
        gate_total=gate_total,
        gate_matches=gate_matches,
        route_match=route_match,
        output_digest=_digest_bytes(_canonical(actual).encode("utf-8")),
    )


def discover_dgf_cases(dataset_root: Path) -> tuple[Path, ...]:
    cases = {
        path.parent
        for path in dataset_root.rglob("99_hidden_ground_truth.json")
        if (path.parent / "01_route_manifest.json").is_file()
    }
    return tuple(sorted(cases))


def dgf_dataset_digest(
    case_dirs: Sequence[Path],
    *,
    dataset_root: Path | None = None,
) -> str:
    if not case_dirs:
        raise ValueError("DGF_EMPTY_DATASET")

    root = dataset_root.resolve() if dataset_root is not None else None
    digest = hashlib.sha256()
    for case_dir in sorted((path.resolve() for path in case_dirs), key=str):
        label = (
            case_dir.relative_to(root).as_posix()
            if root is not None and case_dir.is_relative_to(root)
            else case_dir.name
        )
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        for filename in ("01_route_manifest.json", "99_hidden_ground_truth.json"):
            path = case_dir / filename
            if not path.is_file():
                raise FileNotFoundError(path)
            digest.update(filename.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def summarize_dgf_scores(
    scores: Iterable[DGFCaseScore], *, kernel_digest: str = ""
) -> DGFSubstitutionSummary:
    rows = tuple(scores)
    return DGFSubstitutionSummary(
        kernel_digest=kernel_digest,
        cases=len(rows),
        routes_passed=sum(int(row.route_match) for row in rows),
        gates=sum(row.gate_total for row in rows),
        gates_passed=sum(row.gate_matches for row in rows),
    )


def run_dgf_dataset(
    dataset_root: Path,
    *,
    dgf_root: Path,
    case_dirs: Sequence[Path] | None = None,
    expected_kernel_digest: str | None = None,
) -> tuple[tuple[DGFCaseScore, ...], DGFSubstitutionSummary]:
    """Run every discovered case through the deterministic reference kernel.

    The kernel is loaded once; the summary carries the digest of the exact
    bytes executed. Duplicate case identities are refused rather than double
    counted.
    """
    cases = (
        tuple(case_dirs) if case_dirs is not None else discover_dgf_cases(dataset_root)
    )
    if not cases:
        raise DGFAdmissionError("DGF_EMPTY_DATASET", str(dataset_root))
    kernel = load_dgf_kernel(dgf_root, expected_digest=expected_kernel_digest)
    scores = tuple(
        run_dgf_case(case_dir, dgf_root=dgf_root, kernel=kernel) for case_dir in cases
    )
    seen: dict[str, str] = {}
    for score in scores:
        if score.case_id in seen:
            raise DGFAdmissionError(
                "DUPLICATE_CASE_ID",
                f"{score.case_id} in {seen[score.case_id]} and {score.case_dir}",
            )
        seen[score.case_id] = score.case_dir
    return scores, summarize_dgf_scores(scores, kernel_digest=kernel.digest)


def run_receipted_dgf_dataset(
    dataset_root: Path,
    *,
    dgf_root: Path,
    case_dirs: Sequence[Path] | None = None,
    expected_kernel_digest: str | None = None,
    expected_evaluator_digest: str | None = None,
) -> tuple[tuple[DGFCaseScore, ...], DGFSubstitutionSummary, DGFRunReceipt]:
    """Run the dataset and receipt the exact kernel bytes and corpus bytes.

    ``expected_evaluator_digest`` is an alias of ``expected_kernel_digest``.
    The receipt's kernel digest is the digest of the bytes actually executed
    (never a second, separately-read hash).
    """
    if (
        expected_kernel_digest is not None
        and expected_evaluator_digest is not None
        and expected_kernel_digest != expected_evaluator_digest
    ):
        raise DGFAdmissionError(
            "KERNEL_DIGEST_PIN_CONFLICT",
            f"{expected_kernel_digest} != {expected_evaluator_digest}",
        )
    pin = expected_kernel_digest or expected_evaluator_digest
    cases = (
        tuple(case_dirs) if case_dirs is not None else discover_dgf_cases(dataset_root)
    )
    scores, summary = run_dgf_dataset(
        dataset_root,
        dgf_root=dgf_root,
        case_dirs=cases,
        expected_kernel_digest=pin,
    )
    receipt = DGFRunReceipt(
        kernel_digest=summary.kernel_digest,
        dataset_digest=dgf_dataset_digest(cases, dataset_root=dataset_root),
        case_count=summary.cases,
        gate_count=summary.gates,
        routes_passed=summary.routes_passed,
        gates_passed=summary.gates_passed,
    )
    return scores, summary, receipt
