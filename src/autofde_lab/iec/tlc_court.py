"""TLC court: execute SANY and TLC on IEC TLA+ projections and receipt the result.

This is the execution half that :mod:`autofde_lab.iec.tla_projection`
deliberately omits. It runs the pinned ``tla2tools.jar`` (v1.7.4) as a real
subprocess, parses TLC's ``-tool`` transcript with an explicit state machine,
and emits a receipt whose verdicts are derived only from observed tool output.

Evidence ceiling: a TLC verdict is a *bounded model-check* of the projected
model. It is never a proof (TLAPS is not in the toolchain, so
``FORMAL_PROOF_ALIVE`` is always ``UNSUPPORTED``), never evidence about a
production BRCE implementation, and never carries external authority.

Calibration (tla2tools v1.7.4, TLC2 2.19 rev 5a47802, SANY2 2.1), observed
against the real jar and pinned by ``tests/iec/test_tlc_transcript.py`` over
``tests/iec/fixtures/tlc/v1.7.4``:

* SANY exits 255 on a parse error but **exits 0 on a semantic error**; the
  semantic-error marker (``*** Errors:``) must be read from stdout.
* TLC message codes: 2262 version, 2187 mode, 2220/2219 SANY start/end,
  2185 start, 2189/2190 init, 2200 progress, 2192/2267 temporal check,
  2193 success, 2110 invariant violated, 2116 temporal violated,
  2114 deadlock, 2121/2264 trace header, 2217 trace state, 2218 stuttering,
  2199 final stats, 2194 depth, 2268 outdegree, 2186 finished,
  2229 (sev 1) config error.
* TLC exit codes: 0 success, 11 deadlock, 12 safety violation, 13 liveness
  violation, 151 configuration error.
* ``-deadlock`` *disables* deadlock checking.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .formal import (
    FormalCounterexampleTrace,
    FormalResult,
    FormalVerificationEvidence,
    FormalVerificationIntent,
)
from .model import canonical_json, digest
from .protocol_ir import TransitionSystem
from .tla_projection import TlaProjection, render_cfg, render_tla

TLA2TOOLS_VERSION = "1.7.4"
#: Pinned digest; ``tools/tla/tla2tools-1.7.4.sha256`` is the committed twin
#: and a test asserts the two agree.
TLA2TOOLS_SHA256 = "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"
TLA2TOOLS_SIZE = 2274532
TLA2TOOLS_URL = (
    "https://github.com/tlaplus/tlaplus/releases/download/v1.7.4/tla2tools.jar"
)
DEFAULT_CACHE_JAR = (
    Path.home()
    / ".cache"
    / "autofde-lab"
    / "tla2tools"
    / TLA2TOOLS_VERSION
    / "tla2tools.jar"
)
RECEIPT_SCHEMA = "autofde-lab/tlc-court-receipt/v1"
EVIDENCE_CEILING = (
    "Bounded explicit-state model check of the projected TLA+ model by TLC; "
    "not a proof, not evidence about any production implementation, and no "
    "external authority."
)
FORMAL_PROOF_UNSUPPORTED = "UNSUPPORTED(formal-proof-runtime:tlaps-not-installed)"
DEADLOCK_EXEMPTION_REASON = "terminal STANDING is intended quiescence"


class TlcVerdict(str, Enum):
    MODEL_PARSE_ALIVE = "MODEL_PARSE_ALIVE"
    MODEL_PARSE_REFUSED = "MODEL_PARSE_REFUSED"
    MODEL_CHECK_ALIVE = "MODEL_CHECK_ALIVE"
    PROPERTY_HOLDS_IN_BOUND = "PROPERTY_HOLDS_IN_BOUND"
    COUNTEREXAMPLE_FOUND = "COUNTEREXAMPLE_FOUND"
    TOOL_ERROR = "TOOL_ERROR"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _text_digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── toolchain ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ToolchainUnavailable:
    """Why the court cannot run. ``code`` is a typed refusal/absence."""

    code: str  # TLC_TOOLCHAIN_ABSENT | JAVA_ABSENT | JAR_DIGEST_MISMATCH
    reason: str

    @property
    def refused(self) -> bool:
        return self.code == "JAR_DIGEST_MISMATCH"


@dataclass(frozen=True, slots=True)
class TlaToolchain:
    jar_path: Path
    jar_sha256: str
    java_executable: str
    java_version: str

    @classmethod
    def discover(
        cls,
        jar_path: str | os.PathLike[str] | None = None,
        *,
        expected_sha256: str = TLA2TOOLS_SHA256,
    ) -> "TlaToolchain | ToolchainUnavailable":
        """Locate java and the pinned jar; refuse a jar whose digest differs.

        Resolution order for the jar: explicit argument, then
        ``AUTOFDE_TLA2TOOLS_JAR``, then the fetch-script cache.
        """

        candidate = (
            Path(jar_path)
            if jar_path is not None
            else Path(os.environ.get("AUTOFDE_TLA2TOOLS_JAR", str(DEFAULT_CACHE_JAR)))
        ).expanduser()
        if not candidate.is_file():
            return ToolchainUnavailable(
                "TLC_TOOLCHAIN_ABSENT",
                f"tla2tools.jar not found at {candidate}; run scripts/fetch_tla2tools.sh",
            )
        observed = sha256_file(candidate)
        if observed != expected_sha256:
            return ToolchainUnavailable(
                "JAR_DIGEST_MISMATCH",
                f"jar {candidate} sha256 {observed} != pinned {expected_sha256}",
            )
        java = _java_executable()
        if java is None:
            return ToolchainUnavailable(
                "JAVA_ABSENT", "no java executable on JAVA_HOME or PATH"
            )
        version = _java_version(java)
        if version is None:
            return ToolchainUnavailable(
                "JAVA_ABSENT", f"{java} -version produced no version"
            )
        return cls(candidate, observed, java, version)


def _java_executable() -> str | None:
    home = os.environ.get("JAVA_HOME")
    if home:
        exe = Path(home) / "bin" / "java"
        if exe.is_file():
            return str(exe)
    return shutil.which("java")


_JAVA_VERSION = re.compile(r'version "([^"]+)"')


def _java_version(java: str) -> str | None:
    try:
        completed = subprocess.run(
            [java, "-version"], capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = _JAVA_VERSION.search(completed.stderr + completed.stdout)
    return match.group(1) if match else None


# ── SANY ───────────────────────────────────────────────────────────────────

_SANY_ERROR_MARKERS = (
    "***Parse Error***",
    "Fatal errors while parsing",
    "Semantic errors:",
    "*** Errors:",
    "Could not parse module",
)


@dataclass(frozen=True, slots=True)
class SanyResult:
    verdict: TlcVerdict
    exit_code: int
    argv: tuple[str, ...]
    stdout: str
    stderr: str
    errors: tuple[str, ...]


def classify_sany(exit_code: int, stdout: str) -> tuple[TlcVerdict, tuple[str, ...]]:
    """Pure SANY classification: exit code alone is insufficient (calibrated:
    semantic errors exit 0)."""

    errors = tuple(marker for marker in _SANY_ERROR_MARKERS if marker in stdout)
    if exit_code == 0 and not errors and "Semantic processing of module" in stdout:
        return TlcVerdict.MODEL_PARSE_ALIVE, ()
    if errors or exit_code != 0:
        return TlcVerdict.MODEL_PARSE_REFUSED, errors or (f"exit {exit_code}",)
    return TlcVerdict.UNKNOWN, ("no semantic-processing marker",)


def sany_parse(tc: TlaToolchain, workdir: Path, proj: TlaProjection) -> SanyResult:
    workdir = Path(workdir)
    (workdir / f"{proj.module_name}.tla").write_text(proj.tla)
    argv = (
        tc.java_executable,
        "-cp",
        str(tc.jar_path),
        "tla2sany.SANY",
        f"{proj.module_name}.tla",
    )
    completed = subprocess.run(
        argv, cwd=workdir, capture_output=True, text=True, timeout=120, check=False
    )
    verdict, errors = classify_sany(completed.returncode, completed.stdout)
    return SanyResult(
        verdict, completed.returncode, argv, completed.stdout, completed.stderr, errors
    )


# ── TLC transcript state machine ───────────────────────────────────────────

_FRAME_START = re.compile(r"^@!@!@STARTMSG (\d+):(\d+) @!@!@$")
_FRAME_END = re.compile(r"^@!@!@ENDMSG (\d+) @!@!@$")
_STATS = re.compile(
    r"([\d,]+) states generated, ([\d,]+) distinct states found, ([\d,]+) states left on queue"
)
_DEPTH = re.compile(r"depth of the complete state graph search is (\d+)")
_STATE_HEAD = re.compile(r"^(\d+): <(.*)>\s*$")
_BACK_TO = re.compile(r"^(\d+): Back to state(?::)?\s*<?(.*?)>?\s*$")
_INVARIANT = re.compile(r"Invariant (\w+) is violated")
_VERSION = re.compile(r"TLC2 Version (\S+ of .+?\(rev: \w+\))")

# Phases of the transcript state machine.
PREAMBLE = "PREAMBLE"
INIT = "INIT"
EXPLORING = "EXPLORING"
VIOLATION = "VIOLATION"
TRACE = "TRACE"
LASSO = "LASSO"
STUTTER = "STUTTER"
STATS = "STATS"
FINISHED = "FINISHED"

_ALLOWED: dict[str, frozenset[str]] = {
    PREAMBLE: frozenset({PREAMBLE, INIT, FINISHED, VIOLATION}),
    INIT: frozenset({INIT, EXPLORING, VIOLATION, STATS, FINISHED}),
    EXPLORING: frozenset({EXPLORING, VIOLATION, STATS, FINISHED}),
    VIOLATION: frozenset({TRACE, STATS, FINISHED}),
    TRACE: frozenset({TRACE, LASSO, STUTTER, EXPLORING, STATS, FINISHED}),
    LASSO: frozenset({EXPLORING, STATS, FINISHED}),
    STUTTER: frozenset({EXPLORING, STATS, FINISHED}),
    STATS: frozenset({STATS, EXPLORING, FINISHED}),
    FINISHED: frozenset(),
}

_CODE_PHASE: dict[int, str] = {
    2262: PREAMBLE,
    2187: PREAMBLE,
    2220: PREAMBLE,
    2219: PREAMBLE,
    2185: INIT,
    2189: INIT,
    2190: INIT,
    2212: INIT,
    2200: EXPLORING,
    2192: EXPLORING,
    2267: EXPLORING,
    2110: VIOLATION,
    2107: VIOLATION,
    2116: VIOLATION,
    2114: VIOLATION,
    2121: TRACE,
    2264: TRACE,
    2217: TRACE,
    2218: STUTTER,
    2122: LASSO,
    2193: STATS,
    2199: STATS,
    2194: STATS,
    2268: STATS,
    2186: FINISHED,
}


@dataclass(frozen=True, slots=True)
class TlcMessage:
    code: int
    severity: int
    body: str


@dataclass(frozen=True, slots=True)
class TlcTraceState:
    index: int
    action: str
    values: tuple[tuple[str, str], ...]

    @property
    def state_digest(self) -> str:
        return digest({"values": self.values})


@dataclass(frozen=True, slots=True)
class TlcTranscript:
    messages: tuple[TlcMessage, ...]
    phases: tuple[str, ...]
    final_phase: str
    tool_version: str | None
    outcome: str  # SUCCESS | INVARIANT_VIOLATED | TEMPORAL_VIOLATED | DEADLOCK | TOOL_ERROR | INCOMPLETE
    violated_invariant: str | None
    trace: tuple[TlcTraceState, ...]
    loop: str | None  # STUTTERING | LASSO:<index> | None
    states_generated: int | None
    distinct_states: int | None
    left_on_queue: int | None
    depth: int | None
    errors: tuple[str, ...]

    @property
    def has_stats(self) -> bool:
        return self.distinct_states is not None

    @property
    def trace_digest(self) -> str:
        return digest(
            {
                "trace": [(s.index, s.action, s.values) for s in self.trace],
                "loop": self.loop,
            }
        )


def _frames(stdout: str) -> tuple[list[TlcMessage], list[str]]:
    messages: list[TlcMessage] = []
    stray: list[str] = []
    current: tuple[int, int, list[str]] | None = None
    for raw in stdout.splitlines():
        line = raw.rstrip("\r")
        start = _FRAME_START.match(line)
        if start:
            if current is not None:
                stray.append(f"UNTERMINATED_FRAME:{current[0]}")
            current = (int(start.group(1)), int(start.group(2)), [])
            continue
        end = _FRAME_END.match(line)
        if end:
            if current is None or int(end.group(1)) != current[0]:
                stray.append(f"UNMATCHED_END:{end.group(1)}")
            else:
                messages.append(
                    TlcMessage(current[0], current[1], "\n".join(current[2]))
                )
            current = None
            continue
        if current is not None:
            current[2].append(line)
    if current is not None:
        stray.append(f"UNTERMINATED_FRAME:{current[0]}")
    return messages, stray


def _parse_state(body: str) -> TlcTraceState | None:
    lines = [line for line in body.splitlines() if line.strip()]
    if not lines:
        return None
    head = _STATE_HEAD.match(lines[0])
    if not head:
        return None
    label = head.group(2)
    action = "Init" if label.startswith("Initial predicate") else label.split(" ", 1)[0]
    values: list[tuple[str, str]] = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("/\\ ") and " = " in stripped:
            name, value = stripped[3:].split(" = ", 1)
            values.append((name.strip(), value.strip()))
        elif values:
            name, value = values[-1]
            values[-1] = (name, value + " " + stripped)
        else:
            values.append(("_", stripped))
    return TlcTraceState(int(head.group(1)), action, tuple(sorted(values)))


def _int(text: str) -> int:
    return int(text.replace(",", ""))


def parse_tool_output(stdout: str) -> TlcTranscript:
    """Pure: drive the transcript state machine over TLC ``-tool`` stdout."""

    messages, errors = _frames(stdout)
    phase = PREAMBLE
    phases = [PREAMBLE]
    tool_version: str | None = None
    outcome = "INCOMPLETE"
    violated: str | None = None
    trace: list[TlcTraceState] = []
    loop: str | None = None
    generated = distinct = left = depth = None
    errs = list(errors)

    for message in messages:
        target = _CODE_PHASE.get(message.code)
        if target is None:
            if message.severity == 1:
                outcome = "TOOL_ERROR"
                errs.append(f"TLC_ERROR:{message.code}:{message.body.strip()[:200]}")
            continue
        if target != phase:
            if target not in _ALLOWED[phase]:
                errs.append(f"ILLEGAL_TRANSITION:{phase}->{target}@{message.code}")
            phase = target
            phases.append(phase)
        if message.code == 2262:
            match = _VERSION.search(message.body)
            tool_version = match.group(1) if match else message.body.strip()
        elif message.code in (2110, 2107):
            outcome = "INVARIANT_VIOLATED"
            match = _INVARIANT.search(message.body)
            violated = match.group(1) if match else None
        elif message.code == 2116:
            outcome = "TEMPORAL_VIOLATED"
        elif message.code == 2114:
            outcome = "DEADLOCK"
        elif message.code == 2217:
            state = _parse_state(message.body)
            if state is None:
                errs.append("UNPARSEABLE_STATE")
            else:
                trace.append(state)
        elif message.code == 2218:
            loop = "STUTTERING"
        elif message.code == 2122:
            match = _BACK_TO.match(message.body.strip())
            loop = f"LASSO:{match.group(1)}" if match else "LASSO"
        elif message.code == 2193:
            if outcome == "INCOMPLETE":
                outcome = "SUCCESS"
        elif message.code == 2199:
            match = _STATS.search(message.body)
            if match:
                generated, distinct, left = (_int(g) for g in match.groups())
        elif message.code == 2194:
            match = _DEPTH.search(message.body)
            if match:
                depth = int(match.group(1))

    if trace and outcome not in ("INVARIANT_VIOLATED", "TEMPORAL_VIOLATED", "DEADLOCK"):
        errs.append("TRACE_WITHOUT_VIOLATION")
    return TlcTranscript(
        messages=tuple(messages),
        phases=tuple(phases),
        final_phase=phase,
        tool_version=tool_version,
        outcome=outcome,
        violated_invariant=violated,
        trace=tuple(trace),
        loop=loop,
        states_generated=generated,
        distinct_states=distinct,
        left_on_queue=left,
        depth=depth,
        errors=tuple(errs),
    )


def classify_tlc(
    exit_code: int | None,
    transcript: TlcTranscript,
    *,
    expected_property: str | None = None,
) -> TlcVerdict:
    """Pure: map (exit code, transcript) to a verdict. Every verdict is
    conditioned on observed transcript content, never on exit code alone."""

    if exit_code is None:
        return TlcVerdict.UNKNOWN
    if transcript.outcome == "TOOL_ERROR" or exit_code >= 150:
        return TlcVerdict.TOOL_ERROR
    if any(error.startswith("ILLEGAL_TRANSITION") for error in transcript.errors):
        return TlcVerdict.UNKNOWN
    if transcript.final_phase != FINISHED:
        return TlcVerdict.UNKNOWN
    if (
        exit_code == 0
        and transcript.outcome == "SUCCESS"
        and transcript.has_stats
        and transcript.left_on_queue == 0
    ):
        return TlcVerdict.PROPERTY_HOLDS_IN_BOUND
    if (
        exit_code == 12
        and transcript.outcome == "INVARIANT_VIOLATED"
        and transcript.trace
    ):
        if (
            expected_property is not None
            and transcript.violated_invariant != expected_property
        ):
            return TlcVerdict.UNKNOWN
        return TlcVerdict.COUNTEREXAMPLE_FOUND
    if (
        exit_code == 13
        and transcript.outcome == "TEMPORAL_VIOLATED"
        and transcript.trace
    ):
        return TlcVerdict.COUNTEREXAMPLE_FOUND
    if exit_code == 11 and transcript.outcome == "DEADLOCK" and transcript.trace:
        return TlcVerdict.COUNTEREXAMPLE_FOUND
    return TlcVerdict.UNKNOWN


# ── TLC execution ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TlcRun:
    property_name: str
    property_kind: str  # invariant | liveness
    cfg: str
    argv: tuple[str, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    transcript: TlcTranscript
    verdict: TlcVerdict


def tlc_argv(
    tc: TlaToolchain,
    module_name: str,
    cfg_name: str,
    metadir: str,
    *,
    deadlock_check: bool,
) -> tuple[str, ...]:
    argv = [
        tc.java_executable,
        "-XX:+UseParallelGC",
        "-cp",
        str(tc.jar_path),
        "tlc2.TLC",
        "-tool",
        "-workers",
        "1",
        "-fp",
        "0",
        "-seed",
        "0",
    ]
    if not deadlock_check:
        argv.append("-deadlock")  # calibrated: this flag DISABLES deadlock checking
    argv.extend(["-metadir", metadir, "-config", cfg_name, f"{module_name}.tla"])
    return tuple(argv)


def run_tlc(
    tc: TlaToolchain,
    workdir: Path,
    proj: TlaProjection,
    cfg_text: str,
    *,
    property_name: str,
    property_kind: str,
    deadlock_check: bool,
    timeout_s: int = 120,
) -> TlcRun:
    workdir = Path(workdir)
    (workdir / f"{proj.module_name}.tla").write_text(proj.tla)
    cfg_name = f"{proj.module_name}.{property_name}.cfg"
    (workdir / cfg_name).write_text(cfg_text)
    metadir = workdir / f"tlc-meta-{proj.module_name}-{property_name}"
    shutil.rmtree(metadir, ignore_errors=True)
    argv = tlc_argv(
        tc, proj.module_name, cfg_name, metadir.name, deadlock_check=deadlock_check
    )
    try:
        completed = subprocess.run(
            argv,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        exit_code: int | None = completed.returncode
        stdout, stderr = completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = (
            (exc.stdout or b"").decode()
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = f"TIMEOUT after {timeout_s}s"
    finally:
        shutil.rmtree(metadir, ignore_errors=True)
    transcript = parse_tool_output(stdout)
    expected = property_name if property_kind == "invariant" else None
    verdict = classify_tlc(exit_code, transcript, expected_property=expected)
    return TlcRun(
        property_name,
        property_kind,
        cfg_text,
        argv,
        exit_code,
        stdout,
        stderr,
        transcript,
        verdict,
    )


# ── OCEL projection of a counterexample ────────────────────────────────────


def counterexample_to_ocel(
    run: TlcRun, *, run_id: str, spec_digest: str, config_digest: str
):
    """Project a counterexample trace to a validated OCEL 2.0 log.

    One ``TlcRun`` container object, one ``TlaState`` object per distinct
    state digest, one ``TlaProperty`` object. Events: ``StateVisited`` per
    trace step (timestamp = logical step index), then ``PropertyViolated``,
    then ``Stuttering`` or ``LassoBack`` when the trace ends in a loop.
    """

    from autofde_lab.ocel.log import OcelLog
    from autofde_lab.ocel.model import OcelAttribute, OcelAttributeValue, OcelObject

    tr = run.transcript
    if not tr.trace:
        raise ValueError("counterexample_to_ocel requires a non-empty trace")
    string = OcelAttributeValue.string
    property_id = f"property-{run.property_name}"
    log = OcelLog.new().with_objects(
        OcelObject(
            run_id,
            "TlcRun",
            (
                OcelAttribute("spec_digest", string(spec_digest)),
                OcelAttribute("config_digest", string(config_digest)),
            ),
        ),
        OcelObject(
            property_id,
            "TlaProperty",
            (
                OcelAttribute("name", string(run.property_name)),
                OcelAttribute("kind", string(run.property_kind)),
            ),
        ),
    )
    declared: set[str] = set()
    for state in tr.trace:
        state_id = f"state-{state.state_digest}"
        if state_id not in declared:
            declared.add(state_id)
            log = log.with_objects(
                OcelObject(
                    state_id,
                    "TlaState",
                    tuple(
                        OcelAttribute(name, string(value))
                        for name, value in state.values
                    ),
                )
            )
    step = 0
    for state in tr.trace:
        log = log.append_event(
            f"evt-{step:04d}-StateVisited",
            "StateVisited",
            [(run_id, "run"), (f"state-{state.state_digest}", "state")],
            timestamp_ns=step,
            attributes={
                "action": string(state.action),
                "index": OcelAttributeValue.integer(state.index),
            },
        )
        step += 1
    terminal = f"state-{tr.trace[-1].state_digest}"
    log = log.append_event(
        f"evt-{step:04d}-PropertyViolated",
        "PropertyViolated",
        [(run_id, "run"), (property_id, "property"), (terminal, "state")],
        timestamp_ns=step,
        attributes={"outcome": string(tr.outcome)},
    )
    step += 1
    if tr.loop == "STUTTERING":
        log = log.append_event(
            f"evt-{step:04d}-Stuttering",
            "Stuttering",
            [(run_id, "run"), (terminal, "state")],
            timestamp_ns=step,
        )
    elif tr.loop is not None and tr.loop.startswith("LASSO"):
        log = log.append_event(
            f"evt-{step:04d}-LassoBack",
            "LassoBack",
            [(run_id, "run"), (terminal, "state")],
            timestamp_ns=step,
            attributes={"loop": string(tr.loop)},
        )
    return log.validate()


# ── court ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TlcCourtReceipt:
    payload: dict[str, Any]
    runs: tuple[TlcRun, ...]
    sany: SanyResult | None
    ocel_logs: dict[str, Any] = field(default_factory=dict)

    @property
    def replay_identity(self) -> str:
        return self.payload["replay"]["identity_digest"]

    @property
    def verdicts(self) -> dict[str, str]:
        return {p["name"]: p["verdict"] for p in self.payload["properties"]}


def _portable_argv(argv: tuple[str, ...], tc: TlaToolchain) -> list[str]:
    """argv with host-specific paths replaced by stable placeholders."""

    mapping = {tc.java_executable: "java", str(tc.jar_path): "$TLA2TOOLS_JAR"}
    return [mapping.get(item, item) for item in argv]


def _property_plan(system: TransitionSystem) -> list[tuple[str, str, str]]:
    plan = [
        (
            inv.name,
            "invariant",
            render_cfg(system, invariants=(inv.name,), properties=()),
        )
        for inv in system.invariants
    ]
    plan.extend(
        (
            live.name,
            "liveness",
            render_cfg(system, invariants=(), properties=(live.name,)),
        )
        for live in system.liveness
    )
    return plan


def court(
    system: TransitionSystem,
    tc: TlaToolchain,
    *,
    workdir: Path,
    deadlock_check: bool,
    deadlock_reason: str | None = None,
    replay_command: str | None = None,
    timeout_s: int = 120,
) -> TlcCourtReceipt:
    """Parse with SANY, then run TLC once per property; receipt everything."""

    if not deadlock_check and not deadlock_reason:
        raise ValueError("disabling deadlock checking requires a recorded reason")
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    proj = render_tla(system)
    spec_digest = _text_digest(proj.tla)
    sany = sany_parse(tc, workdir, proj)
    runs: list[TlcRun] = []
    properties: list[dict[str, Any]] = []
    ocel_logs: dict[str, Any] = {}
    tool_version: str | None = None
    if sany.verdict is TlcVerdict.MODEL_PARSE_ALIVE:
        for name, kind, cfg in _property_plan(system):
            run = run_tlc(
                tc,
                workdir,
                proj,
                cfg,
                property_name=name,
                property_kind=kind,
                deadlock_check=deadlock_check,
                timeout_s=timeout_s,
            )
            runs.append(run)
            tool_version = tool_version or run.transcript.tool_version
            config_digest = _text_digest(cfg)
            entry: dict[str, Any] = {
                "name": name,
                "kind": kind,
                "verdict": run.verdict.value,
                "config_digest": config_digest,
                "argv": _portable_argv(run.argv, tc),
                "exit_code": run.exit_code,
                "outcome": run.transcript.outcome,
                "states_generated": run.transcript.states_generated,
                "distinct_states": run.transcript.distinct_states,
                "depth": run.transcript.depth,
                "transcript_phases": list(run.transcript.phases),
                "transcript_errors": list(run.transcript.errors),
                "stdout_digest": _text_digest(run.stdout),
                "stderr_digest": _text_digest(run.stderr),
                "counterexample": None,
            }
            if run.verdict is TlcVerdict.COUNTEREXAMPLE_FOUND:
                tr = run.transcript
                run_id = f"tlc-run-{system.name}-{name}"
                log = counterexample_to_ocel(
                    run,
                    run_id=run_id,
                    spec_digest=spec_digest,
                    config_digest=config_digest,
                )
                ocel_logs[name] = log
                entry["counterexample"] = {
                    "property": name,
                    "violation": tr.outcome,
                    "length": len(tr.trace),
                    "loop": tr.loop,
                    "actions": [s.action for s in tr.trace],
                    "initial_state_digest": tr.trace[0].state_digest,
                    "terminal_state_digest": tr.trace[-1].state_digest,
                    "transition_trace_digest": tr.trace_digest,
                    "ocel_digest": "sha256:" + log.digest(),
                    "replay_command": replay_command,
                }
            properties.append(entry)

    check_complete = bool(runs) and all(
        r.verdict
        in (TlcVerdict.PROPERTY_HOLDS_IN_BOUND, TlcVerdict.COUNTEREXAMPLE_FOUND)
        and r.transcript.has_stats
        for r in runs
    )
    if sany.verdict is not TlcVerdict.MODEL_PARSE_ALIVE:
        model_check = TlcVerdict.UNKNOWN
    elif check_complete:
        model_check = TlcVerdict.MODEL_CHECK_ALIVE
    elif any(r.verdict is TlcVerdict.TOOL_ERROR for r in runs):
        model_check = TlcVerdict.TOOL_ERROR
    else:
        model_check = TlcVerdict.UNKNOWN

    replay_identity = digest(
        {
            "subject": system.system_id,
            "spec_digest": spec_digest,
            "parse": sany.verdict.value,
            "properties": [
                (
                    p["name"],
                    p["verdict"],
                    p["distinct_states"],
                    p["counterexample"]["transition_trace_digest"]
                    if p["counterexample"]
                    else None,
                    p["counterexample"]["ocel_digest"] if p["counterexample"] else None,
                )
                for p in properties
            ],
        }
    )
    payload: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "subject": system.system_id,
        "model": system.name,
        "spec_digest": spec_digest,
        "projection_id": proj.projection_id,
        "projection_warnings": list(proj.warnings),
        "tool_identity": "tla2tools.jar (tla2sany.SANY, tlc2.TLC)",
        "tool_version": tool_version,
        "tla2tools_release": TLA2TOOLS_VERSION,
        "jar_sha256": tc.jar_sha256,
        "java_version": tc.java_version,
        "parse": {
            "verdict": sany.verdict.value,
            "exit_code": sany.exit_code,
            "argv": _portable_argv(sany.argv, tc),
            "errors": list(sany.errors),
            "stdout_digest": _text_digest(sany.stdout),
        },
        "properties_checked": [p["name"] for p in properties],
        "properties": properties,
        "model_check": model_check.value,
        "formal_proof": {
            "verdict": TlcVerdict.UNSUPPORTED.value,
            "reason": FORMAL_PROOF_UNSUPPORTED,
        },
        "bounds": {
            "search": "breadth-first, exhaustive over reachable states within constraints",
            "workers": 1,
            "deadlock_check": deadlock_check,
            "deadlock_exemption_reason": None if deadlock_check else deadlock_reason,
            "state_constraints": [
                {"name": c.name, "expression": c.expression}
                for c in system.state_constraints
            ],
            "constant_values": [list(item) for item in system.constant_values],
            "fairness": [f"{f.kind}_vars({f.target})" for f in system.fairness],
        },
        "authority": "NONE",
        "evidence_ceiling": EVIDENCE_CEILING,
        "replay": {
            "command": replay_command,
            "identity_digest": replay_identity,
            "identity_basis": "subject, spec digest, parse verdict, per-property "
            "(verdict, distinct states, trace digest, ocel digest); raw stdout "
            "carries timestamps and is a byte witness only",
        },
    }
    payload["receipt_digest"] = digest(payload)
    return TlcCourtReceipt(payload, tuple(runs), sany, ocel_logs)


def to_formal_evidence(
    receipt: TlcCourtReceipt, run: TlcRun, intent: FormalVerificationIntent
) -> FormalVerificationEvidence:
    """Bridge one per-property run into the FormalResult contract.

    Admission is exact-subject/tool bound: a real TLC observation cannot be
    relabeled with a different projection, tool version, executable digest, or
    property intent. The bridge carries no authority and never upgrades bounded
    model checking to formal proof.
    """

    payload = receipt.payload
    expected_executable = "sha256:" + str(payload["jar_sha256"])
    checks = (
        (
            intent.projection_id == payload["projection_id"],
            "FORMAL_INTENT_PROJECTION_MISMATCH",
        ),
        (
            intent.tool_identity == "tlc2.TLC",
            "FORMAL_INTENT_TOOL_MISMATCH",
        ),
        (
            intent.tool_version == payload["tool_version"],
            "FORMAL_INTENT_TOOL_VERSION_MISMATCH",
        ),
        (
            intent.executable_digest == expected_executable,
            "FORMAL_INTENT_EXECUTABLE_MISMATCH",
        ),
        (
            payload["jar_sha256"] == TLA2TOOLS_SHA256,
            "FORMAL_EVIDENCE_UNPINNED_TLA2TOOLS",
        ),
        (
            payload["parse"]["verdict"] == TlcVerdict.MODEL_PARSE_ALIVE.value,
            "FORMAL_EVIDENCE_SANY_NOT_ALIVE",
        ),
        (
            run.property_name in payload["properties_checked"],
            "FORMAL_EVIDENCE_PROPERTY_NOT_IN_RECEIPT",
        ),
    )
    for admitted, code in checks:
        if not admitted:
            raise ValueError(code)

    matching = [
        item for item in payload["properties"] if item["name"] == run.property_name
    ]
    if len(matching) != 1:
        raise ValueError("FORMAL_EVIDENCE_PROPERTY_CARDINALITY")
    observed = matching[0]
    if observed["verdict"] != run.verdict.value:
        raise ValueError("FORMAL_EVIDENCE_VERDICT_DRIFT")
    if observed["stdout_digest"] != _text_digest(run.stdout):
        raise ValueError("FORMAL_EVIDENCE_STDOUT_DIGEST_DRIFT")

    mapping = {
        TlcVerdict.PROPERTY_HOLDS_IN_BOUND: FormalResult.PASS,
        TlcVerdict.COUNTEREXAMPLE_FOUND: FormalResult.COUNTEREXAMPLE,
        TlcVerdict.TOOL_ERROR: FormalResult.TOOL_ERROR,
    }
    result = mapping.get(run.verdict, FormalResult.UNKNOWN)
    counterexample = None
    if result is FormalResult.COUNTEREXAMPLE:
        counterexample = FormalCounterexampleTrace.from_states(
            run.property_name, tuple(s.state_digest for s in run.transcript.trace)
        )
    return FormalVerificationEvidence(
        intent_id=intent.intent_id,
        projection_id=receipt.payload["projection_id"],
        exit_code=run.exit_code if run.exit_code is not None else -1,
        result=result,
        properties_checked=(run.property_name,),
        stdout_digest=_text_digest(run.stdout),
        stderr_digest=_text_digest(run.stderr),
        states_generated=run.transcript.states_generated,
        distinct_states=run.transcript.distinct_states,
        counterexample=counterexample,
    )


def write_court_outputs(receipt: TlcCourtReceipt, out: Path) -> dict[str, str]:
    """Write receipt.json, per-property logs and counterexample OCEL files."""

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    if receipt.sany is not None:
        (out / "sany.stdout.log").write_text(receipt.sany.stdout)
    for run in receipt.runs:
        (out / f"tlc.{run.property_name}.stdout.log").write_text(run.stdout)
        (out / f"tlc.{run.property_name}.stderr.log").write_text(run.stderr)
        (out / f"{run.property_name}.cfg").write_text(run.cfg)
    for name, log in receipt.ocel_logs.items():
        path = out / f"counterexample.{name}.ocel.json"
        path.write_text(canonical_json(log.to_ocel2_json()) + "\n")
        written[name] = str(path)
    (out / "receipt.json").write_text(canonical_json(receipt.payload) + "\n")
    written["receipt"] = str(out / "receipt.json")
    return written


__all__ = [
    "DEADLOCK_EXEMPTION_REASON",
    "FORMAL_PROOF_UNSUPPORTED",
    "TLA2TOOLS_SHA256",
    "TLA2TOOLS_SIZE",
    "TLA2TOOLS_VERSION",
    "SanyResult",
    "TlaToolchain",
    "TlcCourtReceipt",
    "TlcRun",
    "TlcTranscript",
    "TlcVerdict",
    "ToolchainUnavailable",
    "classify_sany",
    "classify_tlc",
    "counterexample_to_ocel",
    "court",
    "parse_tool_output",
    "run_tlc",
    "sany_parse",
    "to_formal_evidence",
    "write_court_outputs",
]
