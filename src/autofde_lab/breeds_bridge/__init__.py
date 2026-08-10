"""Bridge to real wasm4pm-cognition "breeds" (reasoning strategies).

Standing: technicalStanding only (per .claude/rules/standing-law.md). This
package calls a real, locally-built Rust binary — it does not manufacture
any semantics, it observes real process output.

Mechanism (approach 1 of the task's ordering): the `wasm4pm-cognition` crate
at ~/wasm4pm exposes no `[[bin]]` target, but it does expose `[[example]]`
targets (see crates/wasm4pm-cognition/Cargo.toml) — e.g.
`examples/abductive_ibe.rs`, which builds to a real native binary via
`cargo build --release --example abductive_ibe`. That binary runs a real
breed (`AbductiveIbe`, dispatched through `breeds::dispatch::run_breed`) on
a fixed, hardcoded scenario (a differential-diagnosis IBE problem) and
prints its real result to stdout. This module invokes that binary via
`subprocess.run` and parses its real stdout — it does not call into any
WASM runtime and does not modify any file under ~/wasm4pm.

The example's input scenario is fixed at compile time in the Rust source
(it is not a general JSON-in/JSON-out CLI) — this bridge therefore exposes
a single, fixed call: "run the abductive_ibe breed on its built-in IBE
diagnosis scenario," not an arbitrary-input breed invocation. That is the
real, minimal, currently-buildable call path; a JSON-parameterized CLI
would require adding a `[[bin]]` to the wasm4pm crate, which is explicitly
out of scope (no edits to wasm4pm source are permitted for this task).
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

WASM4PM_ROOT = Path.home() / "wasm4pm"
ABDUCTIVE_IBE_BINARY = WASM4PM_ROOT / "target" / "release" / "examples" / "abductive_ibe"

_HEADER_RE = re.compile(
    r"^abductive_ibe ok — selected=(?P<selected>\S+)\s+hash=(?P<hash>[0-9a-f]+)$"
)
_CANDIDATE_RE = re.compile(r"^\s+(?P<id>\S+)\s+score=(?P<score>-?\d+\.\d+)$")


class BreedBridgeError(RuntimeError):
    """Raised when the real breed binary is missing or exits non-zero."""


@dataclass(frozen=True)
class Candidate:
    id: str
    score: float


@dataclass(frozen=True)
class AbductiveIbeResult:
    """Real, observed output of one `abductive_ibe` breed invocation."""

    selected: str | None
    output_hash_prefix: str
    explanation: str
    candidates: list[Candidate] = field(default_factory=list)
    raw_stdout: str = ""


def binary_available() -> bool:
    """Whether the real, locally-built abductive_ibe example binary exists on disk."""
    return ABDUCTIVE_IBE_BINARY.is_file()


def run_abductive_ibe(binary_path: Path = ABDUCTIVE_IBE_BINARY) -> AbductiveIbeResult:
    """Invoke the real wasm4pm-cognition `abductive_ibe` breed example.

    This is a real subprocess call to a real, compiled Rust binary — no
    mock, no fake, no fabricated JSON. The binary's scenario is fixed at
    compile time (see module docstring); this function parses the binary's
    real stdout into a typed result.

    Raises BreedBridgeError if the binary is absent (not built) or exits
    non-zero.
    """
    if not binary_path.is_file():
        raise BreedBridgeError(
            f"abductive_ibe example binary not found at {binary_path}. "
            "Build it in the wasm4pm checkout with: "
            "cd ~/wasm4pm && cargo build --release --example abductive_ibe -p wasm4pm-cognition"
        )

    proc = subprocess.run(
        [str(binary_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise BreedBridgeError(
            f"abductive_ibe exited {proc.returncode}: stderr={proc.stderr!r}"
        )

    stdout = proc.stdout
    lines = stdout.splitlines()
    if not lines:
        raise BreedBridgeError(f"abductive_ibe produced no stdout: {proc!r}")

    header_match = _HEADER_RE.match(lines[0])
    if header_match is None:
        raise BreedBridgeError(f"unrecognized abductive_ibe header line: {lines[0]!r}")

    selected_raw = header_match.group("selected")
    selected = None if selected_raw == "None" else selected_raw
    output_hash_prefix = header_match.group("hash")

    explanation = ""
    candidates: list[Candidate] = []
    for line in lines[1:]:
        cand_match = _CANDIDATE_RE.match(line)
        if cand_match is not None:
            candidates.append(
                Candidate(id=cand_match.group("id"), score=float(cand_match.group("score")))
            )
        elif line.strip() and not line.strip().startswith("ranked candidates"):
            # First non-candidate, non-empty line after the header is the
            # explanation text emitted by the breed itself.
            if not explanation:
                explanation = line.strip()

    return AbductiveIbeResult(
        selected=selected,
        output_hash_prefix=output_hash_prefix,
        explanation=explanation,
        candidates=candidates,
        raw_stdout=stdout,
    )
