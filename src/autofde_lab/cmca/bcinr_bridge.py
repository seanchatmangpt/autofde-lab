"""Bridge to the real ``cmca_rank_cli`` binary from the vendored bcinr crate.

The canonical CMCA (Chatman Multifractal **Consequence** Allocation)
implementation in this ecosystem is the Rust crate ``bcinr-cmca``
(vendored verbatim under ``vendor/bcinr`` at the commit recorded in
``VENDORED_BCINR_COMMIT`` below -- see ``vendor/bcinr/VENDORING.md`` for
provenance and refresh procedure). Its allocator is branchless ($CC=1$),
allocation-free, and computes over Q16.16 fixed point with the compiled
lens policy (``LENS_REGISTRY``/``LAMBDA``/``ETA``) -- the mathematics
this repo's CMCA contract delegates to. The former local float-softmax
stand-in (``reference-softmax``) has been deleted outright: every
allocation measure flows through this bridge.

This module never reimplements any of that mathematics: it converts
:class:`~autofde_lab.cmca.contracts.CandidateBranch` features into the
CLI's four caller-defined quality axes, invokes the binary, and parses the
ranking back. The four axes are, in order:

1. ``option_entropy`` (clamped to >= 0),
2. inverse estimated cost (``1 / max(estimated_cost, 1e-6)``),
3. ``historical_yield`` (clamped to >= 0),
4. salience ``S = option_entropy * historical_yield / cost`` (the same
   expression the reference engine soft-maxes).

Wire contract (stdin/stdout JSON, mirroring ``cmca_allocate_cli``'s
conventions upstream): request
``{"candidates": [{"name": ..., "measures": [m0, m1, m2, m3]}]}``;
response ``{"ranking": [{"name": ..., "share": ...}]}``; any refusal is an
``{"error": ...}`` envelope on **stderr** with exit code 1 (stdout
empty). The CLI pads
sub-8 candidate sets with all-zero *phantom* candidates that absorb a
real but negligible share, so this bridge renormalizes real-candidate
shares back to sum 1.0 before handing fractions to the allocator. More
than 8 real candidates is refused by the CLI (``allocate()`` is compiled
for exactly ``N = 8``, upstream CMCA-108) and surfaced here as a typed
:class:`BcinrCardinalityRefusal` rather than truncated -- there is no
correct way to silently drop a caller's candidate.

Unlike :mod:`autofde_lab.ocel.wasm4pm_bridge` (async, via
``run_subprocess_bounded``, because its callers are coroutines), every
caller of this bridge is synchronous, so the CLI transport uses a plain
timeout-bounded ``subprocess.run`` -- the coroutine-unsafety called out in
that module's docstring does not apply to a sync-only path.

## Transports

Two transports reach the same vendored allocator, tried in a fixed order:

1. **wasm** (default first): :mod:`autofde_lab.cmca.bcinr_wasm` loads the
   prebuilt ``wasm/artifacts/bcinr_cmca_wasm.wasm`` cdylib (built from the
   same ``VENDORED_BCINR_COMMIT`` snapshot) into ``wasmtime`` in-process --
   no Rust toolchain, no subprocess, usable from any WASM-capable host.
2. **cli**: a built ``cmca_rank_cli`` binary discovered via the
   ``BCINR_CMCA_CLI`` environment variable, the repo-vendored build
   (``cargo build --release -p bcinr-cmca`` inside ``vendor/bcinr``), an
   upstream checkout at ``~/bcinr``, or ``PATH``.

``$BCINR_CMCA_TRANSPORT`` forces one: ``wasm`` or ``cli`` (a forced-but-
absent transport is a typed refusal, never a silent switch to the other;
an unrecognized value refuses too). In the default order only
*unavailability* (missing runtime package or artifact) falls through to
the CLI -- a wasm protocol fault raises, since masking it would hide a
real defect. If neither transport resolves, callers get
:class:`BcinrCliUnavailable` -- this repo's ``UNSUPPORTED``-style typed
refusal for an absent optional external tool, not a crash.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from . import bcinr_wasm
from .contracts import CandidateBranch

#: Upstream commit of the vendored ``vendor/bcinr`` snapshot this bridge is
#: built against. Must match the pin recorded in ``vendor/bcinr/VENDORING.md``
#: (a Chicago test asserts that correspondence).
VENDORED_BCINR_COMMIT = "2ae60cf0"

#: Hard limit from the CLI itself (``allocate()`` is compiled for exactly
#: ``N = 8`` objects, upstream CMCA-108). Not a policy choice made here.
MAX_BCINR_CANDIDATES = 8

#: Cost floor, identical to the reference engine's, so inverse-cost axes of
#: zero-cost candidates saturate instead of dividing by zero.
_COST_FLOOR = 1e-6

_CLI_BASENAME = "cmca_rank_cli"


class BcinrCliUnavailable(RuntimeError):
    """No built ``cmca_rank_cli`` binary found (typed UNSUPPORTED refusal)."""


class BcinrCardinalityRefusal(RuntimeError):
    """More real candidates than the compiled ``N = 8`` allocator admits."""


class BcinrFeatureRefusal(RuntimeError):
    """A candidate carries non-finite features (NaN/Inf) -- refused, clamping
    would silently fabricate a different candidate."""


class BcinrProtocolError(RuntimeError):
    """The CLI answered with an error envelope or an unusable response."""


def find_bcinr_cli() -> str | None:
    """Locate the built ``cmca_rank_cli`` binary, or ``None``.

    Checks ``$BCINR_CMCA_CLI`` first, then this repo's vendored build at
    ``vendor/bcinr/target/release/``, then an upstream checkout at
    ``~/bcinr/target/release/``, then ``PATH`` -- mirroring
    :func:`autofde_lab.ocel.wasm4pm_bridge.resolve_wpm_binary`'s layered
    discovery without hardcoding one machine's layout.
    """
    env_path = os.environ.get("BCINR_CMCA_CLI")
    if env_path and Path(env_path).is_file():
        return env_path

    vendored = (
        Path(__file__).resolve().parents[3]
        / "vendor"
        / "bcinr"
        / "target"
        / "release"
        / _CLI_BASENAME
    )
    if vendored.is_file():
        return str(vendored)

    upstream = Path.home() / "bcinr" / "target" / "release" / _CLI_BASENAME
    if upstream.is_file():
        return str(upstream)

    return shutil.which(_CLI_BASENAME)


def resolve_bcinr_cli() -> str:
    """Locate the built ``cmca_rank_cli`` binary, or raise typed refusal."""
    found = find_bcinr_cli()
    if found:
        return found
    raise BcinrCliUnavailable(
        "no built 'cmca_rank_cli' binary found (checked $BCINR_CMCA_CLI, "
        "vendor/bcinr/target/release/cmca_rank_cli, "
        "~/bcinr/target/release/cmca_rank_cli, and PATH) -- build it with "
        "'cargo build --release -p bcinr-cmca' inside vendor/bcinr "
        f"(vendored upstream commit {VENDORED_BCINR_COMMIT})"
    )


def candidate_measures(branch: CandidateBranch) -> list[float]:
    """Four non-negative quality axes for one candidate, or typed refusal.

    Axis order is fixed (see module docstring); NaN or +-Inf in any input
    feature refuses rather than clamps -- a fabricated feature vector is a
    fabricated candidate. Finiteness is checked on the *raw* features
    before any clamping, so a ``-inf`` entropy cannot silently become a
    lawful ``0.0``.
    """
    for label, raw in (
        ("option_entropy", float(branch.option_entropy)),
        ("historical_yield", float(branch.historical_yield)),
        ("estimated_cost", float(branch.estimated_cost)),
    ):
        if not math.isfinite(raw):
            raise BcinrFeatureRefusal(
                f"candidate {branch.branch_id!r} has non-finite {label}; refusing"
            )
    entropy = max(float(branch.option_entropy), 0.0)
    yield_ = max(float(branch.historical_yield), 0.0)
    cost = max(float(branch.estimated_cost), _COST_FLOOR)
    salience = entropy * yield_ / cost
    measures = [entropy, 1.0 / cost, yield_, salience]
    if not all(math.isfinite(m) for m in measures):
        raise BcinrFeatureRefusal(
            f"candidate {branch.branch_id!r} produced non-finite measures; refusing"
        )
    return measures


def _call_cli(request: dict, binary: str, timeout_s: float) -> dict:
    """One ``cmca_rank_cli`` subprocess round-trip: request dict in, parsed
    response envelope out (typed refusal on unparseable output, nonzero
    exit, or an ``{"error": ...}`` envelope)."""
    proc = subprocess.run(
        [binary],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        # The CLI's error envelope is written to stderr (exit 1, stdout
        # empty) -- surface it as a typed refusal, not "unparseable output".
        if proc.returncode != 0 and proc.stderr.strip():
            try:
                err_payload = json.loads(proc.stderr)
                message = err_payload.get("error", proc.stderr[:200])
            except json.JSONDecodeError:
                message = proc.stderr[:200]
            raise BcinrProtocolError(f"cmca_rank_cli refused: {message}")
        raise BcinrProtocolError(
            f"cmca_rank_cli produced unparseable output (exit={proc.returncode}): "
            f"{proc.stdout[:200]!r} stderr={proc.stderr[:200]!r}"
        )

    if proc.returncode != 0 or "error" in payload:
        message = payload.get("error", proc.stdout[:200])
        raise BcinrProtocolError(f"cmca_rank_cli refused: {message}")
    return payload


def _dispatch_rank_request(
    request: dict,
    *,
    cli: str | None = None,
    timeout_s: float = 15.0,
) -> dict:
    """Pick a transport (see the module docstring's Transports section).

    ``$BCINR_CMCA_TRANSPORT`` forces ``wasm`` or ``cli``; a forced-but-absent
    transport refuses rather than silently switching, and an unrecognized
    value refuses too. Default order: wasm first, falling through to the
    CLI only on wasm *unavailability* -- a wasm protocol fault raises,
    since masking it would hide a real defect behind a different engine.
    """
    forced = os.environ.get("BCINR_CMCA_TRANSPORT", "").strip().lower()
    if forced == "cli":
        return _call_cli(request, cli or resolve_bcinr_cli(), timeout_s)
    if forced == "wasm":
        return bcinr_wasm.call_rank(request)
    if forced not in ("", "auto"):
        raise BcinrProtocolError(
            f"unknown BCINR_CMCA_TRANSPORT {forced!r}; expected 'wasm', 'cli', or unset"
        )
    try:
        return bcinr_wasm.call_rank(request)
    except bcinr_wasm.BcinrWasmUnavailable:
        # No wasm artifact discoverable at all -> try the CLI transport.
        return _call_cli(request, cli or resolve_bcinr_cli(), timeout_s)
    # BcinrWasmModuleMissing is deliberately NOT caught: $BCINR_CMCA_WASM
    # explicitly names a missing file, and bcinr_wasm documents that as a
    # mandatory refusal -- falling through to the CLI here would silently
    # mask the operator's misconfiguration.


def rank_candidates(
    candidates: Sequence[CandidateBranch],
    *,
    cli: str | None = None,
    timeout_s: float = 15.0,
) -> dict[str, float]:
    """Rank candidates through the real bcinr allocator (wasm-then-cli).

    Returns ``{branch_id: share}`` with shares renormalized to sum 1.0 over
    the real candidates (phantom padding absorbs a negligible share
    upstream). Deterministic for identical inputs: candidates are sent in
    canonical ``candidate_hash`` order and the allocator itself is
    deterministic fixed-point -- identically so through both transports,
    which are built from the same vendored commit.
    """
    if len(candidates) > MAX_BCINR_CANDIDATES:
        raise BcinrCardinalityRefusal(
            f"{len(candidates)} candidates exceeds the compiled N=8 allocator "
            f"shape (upstream CMCA-108); refusing rather than truncating"
        )

    canonical = sorted(candidates, key=lambda c: c.candidate_hash)
    request = {
        "candidates": [
            {"name": c.branch_id, "measures": candidate_measures(c)} for c in canonical
        ]
    }

    payload = _dispatch_rank_request(request, cli=cli, timeout_s=timeout_s)

    if "error" in payload:
        raise BcinrProtocolError(
            f"bcinr-cmca wasm transport refused: {payload['error']}"
        )

    ranking = payload.get("ranking")
    if not isinstance(ranking, list):
        raise BcinrProtocolError(
            f"cmca_rank_cli response missing 'ranking': {payload!r}"
        )

    shares: dict[str, float] = {}
    for entry in ranking:
        name = entry.get("name")
        share = entry.get("share")
        if not isinstance(name, str) or not isinstance(share, (int, float)):
            raise BcinrProtocolError(f"malformed ranking entry: {entry!r}")
        if name in shares:
            raise BcinrProtocolError(f"duplicate candidate name in ranking: {name!r}")
        if not math.isfinite(float(share)) or float(share) < 0.0:
            raise BcinrProtocolError(f"non-finite or negative share for {name!r}")
        shares[name] = float(share)

    expected = {c.branch_id for c in canonical}
    if set(shares) != expected:
        raise BcinrProtocolError(
            f"ranking names {sorted(set(shares) ^ expected)} mismatch the request"
        )

    total = sum(shares.values())
    if total <= 0.0:
        raise BcinrProtocolError("cmca_rank_cli returned zero total share mass")
    return {name: share / total for name, share in shares.items()}
