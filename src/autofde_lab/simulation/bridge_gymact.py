"""gymact <-> autofde-lab bridge adapter (lane W10).

Serves gymact's real autonomous execution loop (:class:`gymact.execution_loop.AutonomousLoop`)
as an episode backend inside autofde-lab's outcome matrix: one call to
:func:`run_episode_backend` builds a gymact world from a JSON-able ``world_spec``,
runs the loop with deterministic in-process fakes, and maps the result into the
pinned outcome-row schema (beam4pm docs/jira/v26.9.25/_LANES-strategic-loop.md
RESOLUTIONS #7):

    {backend: "gymact", doctrine_id: str, world_id: str, seed: int,
     metrics: map, feasible: bool, receipt_digests: [str]}

so fault-corpus episodes become adversarial worlds with OCEL receipt evidence.

 gymact import mechanism (probed, recorded -- see :func:`import_report`)
-------------------------------------------------------------------------
The ladder below is executed lazily at first use (never at module import, so
sibling lanes' in-flight edits cannot break our collection):

1. plain ``import gymact.execution_loop`` (site-packages distribution).
2. ``sys.path`` insertion of ``/Users/sac/gymact/src`` -- only when ``gymact``
   is not yet bound in ``sys.modules`` (fresh coherent bind of the local
   checkout; the path entry is popped after import, the cached package keeps
   its own ``__path__``).
3. ``importlib.util.spec_from_file_location`` overlay of the local
   ``execution_loop.py`` into an already-bound ``gymact`` package that lacks
   it (parallel-suite robustness: another collected test module may have
   imported the venv distribution first; the overlay module's
   ``from gymact.evidence import digest`` / ``gymact.models`` imports resolve
   against the bound package).

Nothing is pip-installed, network is never touched. Whichever mechanism fired
is recorded verbatim in ``IMPORT_REPORT`` and surfaced in every outcome row
(``metrics["gymact_import_mechanism"]``).

Measured in this environment (2026-09-25): the autofde-lab venv distribution
(pinned ``[tool.uv.sources]`` rev 524d0bc8) predates ``gymact.execution_loop``,
so mechanism 2 or 3 against the local checkout is what fires.

 Feasibility law (documented mapping -- ANTI-VACUITY SURFACE)
--------------------------------------------------------------
``feasible`` is decided ONLY by :data:`FEASIBILITY_BY_OUTCOME` over the
terminal ``LoopResult.outcome`` (a ``LegalOutcome`` value, gymact
src/gymact/execution_loop.py:74-81):

=================  ============================  =========  =======================
outcome            episode_standing              feasible   law
=================  ============================  =========  =======================
Recover            AUTONOMOUS                    True       verified receipt, exactly-once actuation (:656-899)
Replan             AUTONOMOUS                    True       lawful typed re-plan transition
Substitute         AUTONOMOUS                    True       lawful provider substitution (:662-669, :763-770)
Refuse             BLOCKED_AUTHORITY or FAILED   True       lawful refusal IS a successful outcome: typed, receipted, zero actuation (:475-536)
TypedBlock         BLOCKED_INFORMATION           True       budget/verification exhaustion is a TYPED block, never human escalation (:538-567, :962-980)
(anything else)    FAILED                        False      fail-closed: unknown outcome, illegal outcome, or escaped exception
=================  ============================  =========  =======================

Crash is NOT a terminal outcome: worker SIGKILL is answered in-loop by
Recover (retry / journal reconstruction, :680-740) or TypedBlock
(TYPED_BLOCK_RECEIPT_LOST, :700-704). ``WaitForHumanToNotice``
(IllegalOutcome, :84-91) is named only so courts can prove it unreachable:
``LoopResult.asserted_illegal_outcome`` is None by construction (:336-341) and
``AutonomousLoop.run`` (:596-899) has no human-notification path. This bridge
does not trust that proof blindly: it re-checks the assertion per run and maps
any violation fail-closed to ``feasible=False`` with
``metrics["illegal_outcome_observed"]=True``.

 Determinism
-------------
Same ``(world_spec, doctrine_id, seed)`` => byte-identical row. The loop gets
``random.Random(seed)`` (the sole randomness source, gymact
tests/explore_execution_loop/conftest.py:6-7 idiom); providers are scripted
(no RNG); receipt timestamps are virtual-tick-derived (execution_loop.py:1023-1026);
OCEL log timestamps derive from a fixed base datetime (execution_loop.py:351).
Receipt digests are sha256 over the receipt's canonical pydantic JSON
(``ExecutionReceipt.model_dump_json()`` -- the canonical serialization EXISTS,
so the repr fallback is not needed).

 gymact is READ-ONLY for this lane; the deterministic fakes below re-express
the documented provider protocol idioms from
gymact tests/explore_execution_loop/conftest.py (VirtualClock :54-64,
FakeRegistry :67-72, FakeProbe :75-84, FakeVerifier :87-108,
ScriptedProvider :111-205) because that scaffolding is a test-tree conftest,
not a published package surface. No W8-owned file
(fortune5_safe/{worldgen,model,engine,dfcm}.py) is imported here; consumers
bridge from their public shapes to this module's JSON seam.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import random
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "FEASIBILITY_BY_OUTCOME",
    "GymactUnavailable",
    "gymact_available",
    "import_report",
    "run_episode_backend",
]

GYMACT_SRC = "/Users/sac/gymact/src"

# Pinned outcome-row schema (RESOLUTIONS #7 -- W8 owns it, this module conforms).
ROW_BACKEND = "gymact"
ROW_KEYS = (
    "backend",
    "doctrine_id",
    "world_id",
    "seed",
    "metrics",
    "feasible",
    "receipt_digests",
)

# Feasibility law table keyed by LegalOutcome VALUE (not enum identity, so the
# mapping survives enum identity skew between import mechanisms). All five
# legal outcomes are feasible: every legal terminal is a bounded, typed,
# receipted transition. Unknown/illegal outcomes fail closed to False in
# code (_feasible_for), not by table omission (totality is tested).
FEASIBILITY_BY_OUTCOME: dict[str, bool] = {
    "Recover": True,
    "Replan": True,
    "Substitute": True,
    "Refuse": True,  # lawful refusal is a successful outcome
    "TypedBlock": True,  # typed block, never human escalation
}

LEGAL_OUTCOME_VALUES = frozenset(FEASIBILITY_BY_OUTCOME)
ILLEGAL_OUTCOME_VALUE = "WaitForHumanToNotice"

IMPORT_REPORT: dict[str, Any] = {
    "mechanism": None,
    "ladder": [],
    "gymact_file": None,
    "execution_loop_file": None,
}


class GymactUnavailable(ImportError):
    """No import mechanism in the ladder could expose
    ``gymact.execution_loop``; the row mapping cannot run."""


def _record_mechanism(name: str, loop_module: Any) -> None:
    import gymact as pkg

    IMPORT_REPORT["mechanism"] = name
    IMPORT_REPORT["gymact_file"] = str(getattr(pkg, "__file__", None))
    IMPORT_REPORT["execution_loop_file"] = str(getattr(loop_module, "__file__", None))


def _try_plain_import() -> Any | None:
    try:
        module = importlib.import_module("gymact.execution_loop")
    except ImportError as exc:
        IMPORT_REPORT["ladder"].append(f"plain-import: FAILED ({exc})")
        return None
    _record_mechanism("plain-import (site-packages distribution)", module)
    IMPORT_REPORT["ladder"].append(
        f"plain-import: OK ({IMPORT_REPORT['execution_loop_file']})"
    )
    return module


def _try_sys_path_insert() -> Any | None:
    src = GYMACT_SRC
    if not Path(src, "gymact", "execution_loop.py").is_file():
        IMPORT_REPORT["ladder"].append(f"sys-path-insert: SKIPPED ({src} absent)")
        return None
    if "gymact" in sys.modules:
        # A bound package cannot be rebound by sys.path precedence; the
        # overlay mechanism below owns this case.
        IMPORT_REPORT["ladder"].append(
            "sys-path-insert: SKIPPED (gymact already bound without execution_loop)"
        )
        return None
    sys.path.insert(0, src)
    try:
        module = importlib.import_module("gymact.execution_loop")
    except ImportError as exc:
        IMPORT_REPORT["ladder"].append(f"sys-path-insert: FAILED ({exc})")
        return None
    finally:
        try:
            sys.path.remove(src)
        except ValueError:
            pass
    if not str(getattr(module, "__file__", "")).startswith(src):
        IMPORT_REPORT["ladder"].append("sys-path-insert: FAILED (resolved elsewhere)")
        return None
    _record_mechanism(f"sys-path-insert of {src} (local checkout coherent bind)", module)
    IMPORT_REPORT["ladder"].append(
        f"sys-path-insert: OK ({IMPORT_REPORT['execution_loop_file']})"
    )
    return module


def _try_file_location_overlay() -> Any | None:
    src = GYMACT_SRC
    target = Path(src, "gymact", "execution_loop.py")
    if not target.is_file():
        IMPORT_REPORT["ladder"].append(f"file-location-overlay: SKIPPED ({target} absent)")
        return None
    bound = sys.modules.get("gymact")
    if bound is None:
        # Importing the package directly here would race the sys.path
        # mechanism; leave it to that mechanism instead.
        IMPORT_REPORT["ladder"].append(
            "file-location-overlay: SKIPPED (no bound gymact package)"
        )
        return None
    spec = importlib.util.spec_from_file_location("gymact.execution_loop", target)
    if spec is None or spec.loader is None:
        IMPORT_REPORT["ladder"].append("file-location-overlay: FAILED (no spec)")
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["gymact.execution_loop"] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - version-skew guard
        IMPORT_REPORT["ladder"].append(f"file-location-overlay: FAILED ({exc})")
        sys.modules.pop("gymact.execution_loop", None)
        return None
    _record_mechanism("", module)  # fills report fields first...
    IMPORT_REPORT["mechanism"] = (
        f"file-location-overlay of {target} onto bound gymact "
        f"({IMPORT_REPORT['gymact_file']})"
    )
    IMPORT_REPORT["ladder"].append(
        f"file-location-overlay: OK ({IMPORT_REPORT['execution_loop_file']})"
    )
    return module


def _load_gymact() -> Any:
    """Resolve ``gymact.execution_loop`` through the recorded mechanism ladder."""
    for attempt in (_try_plain_import, _try_sys_path_insert, _try_file_location_overlay):
        module = attempt()
        if module is not None:
            return module
    raise GymactUnavailable(
        "gymact.execution_loop unavailable: plain import failed, "
        f"{GYMACT_SRC} not usable via sys.path insert or file-location overlay; "
        f"ladder={IMPORT_REPORT['ladder']}"
    )


def gymact_available() -> bool:
    """True iff the gymact execution-loop surface resolved through some
    mechanism (recorded in :data:`IMPORT_REPORT`)."""
    try:
        _load_gymact()
    except GymactUnavailable:
        return False
    return True


def import_report() -> dict[str, Any]:
    """The probe report: which mechanism fired and the full ladder trace."""
    return dict(IMPORT_REPORT)


def _loop_module() -> Any:
    """The resolved execution-loop module: sys.modules cache first, then the
    recorded mechanism ladder. The ladder runs on FIRST use in any process --
    callers are not required to invoke :func:`gymact_available` first."""
    cached = sys.modules.get("gymact.execution_loop")
    if cached is not None:
        return cached
    return _load_gymact()


# --------------------------------------------------------------------------- #
# Deterministic in-process world (gymact conftest idioms, package-safe)
# --------------------------------------------------------------------------- #


@dataclass
class VirtualClock:
    """Deterministic virtual clock; the loop advances it via backoff only
    (gymact conftest.py:54-64 idiom)."""

    tick: int = 0

    def now(self) -> int:
        return self.tick

    def advance(self, ticks: int) -> None:
        self.tick += ticks


@dataclass
class StaticRegistry:
    """All-or-nothing authority validity (conftest.py:67-72 idiom)."""

    valid: bool = True

    def is_valid(self, grant: Any) -> bool:
        return self.valid


@dataclass
class StaticProbe:
    """Fixed resource readings comfortably above default budgets
    (conftest.py:75-84 idiom)."""

    disk_mb: int = 10_000
    cpu_cores: float = 8.0

    def disk_mb_available(self) -> int:
        return self.disk_mb

    def cpu_cores_available(self) -> float:
        return self.cpu_cores


@dataclass
class ScriptedVerifier:
    """Scripted verify results; the last entry repeats
    (conftest.py:87-108 idiom)."""

    results: Sequence[tuple[bool, str]] = field(default_factory=lambda: [(True, "ok")])

    def __post_init__(self) -> None:
        self.calls = 0

    def verify(self, subject_after: Any, effect_digest: str, request: Any) -> tuple[bool, str]:
        self.calls += 1
        index = min(self.calls - 1, len(self.results) - 1)
        return self.results[index]


@dataclass
class ScriptedProvider:
    """In-process ``ExecutionProvider`` with scripted faults consumed
    left-to-right one per call; once empty the provider behaves healthily
    (conftest.py:111-205 idiom). ``world[repo]`` is the subject SHA the
    outside world sees."""

    transport: str = "fake:autofde-primary"
    capabilities: Sequence[str] = ("exec",)
    authority_ceiling: str = "DO"
    availability: bool = True
    receipt_protocol: str = "fake+journal"
    world: dict[str, str] = field(default_factory=dict)
    claim_faults: list[Any] = field(default_factory=list)
    execute_faults: list[Any] = field(default_factory=list)
    effect: dict[str, Any] = field(default_factory=dict)
    explode_on_claim: str | None = None  # non-TransportFault exception type name
    on_execute: Callable[["ScriptedProvider"], None] | None = None

    def __post_init__(self) -> None:
        from collections import deque

        self._claim_faults = deque(self.claim_faults)
        self._execute_faults = deque(self.execute_faults)
        self.claim_calls = 0
        self.execute_calls = 0
        self.journal: dict[str, dict[str, Any]] = {}

    # -- execution_loop.ExecutionProvider protocol surface -------------------

    @property
    def cost(self) -> float:
        return 0.0

    @property
    def concurrency(self) -> int:
        return 1

    def current_subject_sha(self, repo: str) -> str:
        return self.world.get(repo, next(iter(self.world.values())))

    def resolve_subject(self, repo: str) -> Any:
        execution_loop = _loop_module()
        return execution_loop.SubjectRef(repo=repo, sha=self.current_subject_sha(repo))

    def claim(self, request: Any) -> Any:
        execution_loop = _loop_module()
        self.claim_calls += 1
        if self.explode_on_claim is not None:
            # A fault the loop does NOT catch: escapes run() as a real crash
            # (run() catches TransportFault only, execution_loop.py:636-641) --
            # the constructible forced-failure path for feasibility=False.
            raise RuntimeError(self.explode_on_claim)
        fault = self._claim_faults.popleft() if self._claim_faults else None
        if fault is not None:
            kind = fault[0] if isinstance(fault, (list, tuple)) else fault
            retry = fault[1] if isinstance(fault, (list, tuple)) and len(fault) > 1 else 1
            if kind == "worker_sigkill":
                raise execution_loop.WorkerCrashed(
                    applied_before=False, injection_point="mid-claim"
                )
            raise execution_loop.TransportFault(kind=kind, retry_after_ticks=retry)
        return execution_loop.ClaimPin(
            provider_execution_id=f"{self.transport}/{request.work_order}/{self.claim_calls}",
            pinned_subject_sha=self.current_subject_sha(request.subject.repo),
        )

    def execute(self, request: Any, provider_execution_id: str) -> dict[str, Any]:
        execution_loop = _loop_module()
        self.execute_calls += 1
        fault = self._execute_faults.popleft() if self._execute_faults else None
        if fault is not None:
            kind = fault[0]
            if kind == "crash_before_actuation":
                raise execution_loop.WorkerCrashed(
                    applied_before=False, injection_point="pre-actuation"
                )
            if kind == "crash_after_actuation":
                self.journal[provider_execution_id] = self._fragment()
                raise execution_loop.WorkerCrashed(
                    applied_before=True, injection_point="post-actuation-pre-receipt"
                )
            raise execution_loop.TransportFault(
                kind=fault[1], retry_after_ticks=fault[2] if len(fault) > 2 else 1
            )
        if self.on_execute is not None:
            self.on_execute(self)
        self.journal[provider_execution_id] = self._fragment()
        return self._fragment()

    def fetch_receipt(self, provider_execution_id: str) -> dict[str, Any] | None:
        return self.journal.get(provider_execution_id)

    def ack(self, receipt: Any) -> None:
        return None

    def _fragment(self) -> dict[str, Any]:
        return dict(self.effect)


@dataclass
class WorldBundle:
    """Everything :class:`AutonomousLoop` needs, built from one world_spec."""

    providers: list[Any]
    verifier: Any
    registry: Any
    probe: Any
    clock: VirtualClock


def _subject_sha(world_spec: dict[str, Any]) -> str:
    """Content-addressed, deterministic subject SHA for a world_spec."""
    canonical = json.dumps(world_spec, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def default_provider_factory(seed: int, world_spec: dict[str, Any]) -> WorldBundle:
    """Deterministic fakes per gymact's documented loop-episode construction
    idiom; ``seed`` is consumed by the loop RNG, never by the fakes. Every
    scripted-fault key in the world_spec is wired through here."""
    sha = _subject_sha(world_spec)
    provider = ScriptedProvider(
        transport=world_spec.get("transport", "fake:autofde-primary"),
        capabilities=tuple(world_spec.get("provider_capabilities") or ["exec"]),
        authority_ceiling=world_spec.get("provider_authority_ceiling", "DO"),
        availability=bool(world_spec.get("provider_available", True)),
        world={"autofde-lab": sha},
        claim_faults=list(world_spec.get("claim_faults") or []),
        execute_faults=list(world_spec.get("execute_faults") or []),
        effect={
            "effect_digest": hashlib.sha256(
                f"effect:{sha}".encode("utf-8")
            ).hexdigest(),
            "subject_after_sha": sha,
            "actuation_count": 1,
            "consequence": {"changed_files": 1, "work": "simulated"},
        },
        explode_on_claim=world_spec.get("explode_on_claim"),
    )
    return WorldBundle(
        providers=[provider],
        verifier=ScriptedVerifier(
            results=world_spec.get("verifier_results") or [(True, "ok")]
        ),
        registry=StaticRegistry(valid=bool(world_spec.get("registry_valid", True))),
        probe=StaticProbe(),
        clock=VirtualClock(),
    )


# --------------------------------------------------------------------------- #
# The backend
# --------------------------------------------------------------------------- #


def _feasible_for(outcome: str | None) -> bool:
    """Fail-closed feasibility: table hit wins; anything unlisted (unknown,
    illegal, or missing outcome) is infeasible."""
    if outcome is None:
        return False
    return FEASIBILITY_BY_OUTCOME.get(outcome, False)


def _normalize_world_spec(world_spec: dict[str, Any] | None) -> dict[str, Any]:
    spec = dict(world_spec or {})
    spec.setdefault("world_id", "unnamed-gymact-world")
    spec.setdefault("capability_requirements", ["exec"])
    spec.setdefault("authority_ceiling", "DO")
    spec.setdefault("claim_faults", [])
    spec.setdefault("execute_faults", [])
    spec.setdefault("work_order", f"WO-{spec['world_id']}")
    return spec


def run_episode_backend(
    world_spec: dict[str, Any] | None,
    doctrine_id: str,
    seed: int,
    provider_factory: Callable[[int, dict[str, Any]], WorldBundle] | None = None,
) -> dict[str, Any]:
    """Run ONE gymact AutonomousLoop episode and map it into the pinned
    outcome-row schema (RESOLUTIONS #7).

    :param world_spec: JSON-able world construction dict (world_id,
        capability_requirements, authority_ceiling, claim_faults,
        execute_faults, verifier_results, registry_valid, explode_on_claim,
        resource-constraint overrides).
    :param doctrine_id: the strategic doctrine this episode adjudicates.
    :param seed: sole randomness source (``random.Random(seed)`` for the
        loop's RNG; fakes are scripted).
    :param provider_factory: optional ``factory(seed, world_spec) ->
        WorldBundle`` override; default :func:`default_provider_factory`
        (gymact's deterministic in-process fake providers).
    :returns: the pinned outcome row; byte-identical for identical inputs.
    """
    execution_loop = _loop_module()
    spec = _normalize_world_spec(world_spec)
    factory = provider_factory or default_provider_factory
    bundle = factory(seed, spec)

    authority = execution_loop.AuthorityGrant(
        ceiling=spec["authority_ceiling"],
        grant=f"autofde-lab bridge doctrine={doctrine_id} world={spec['world_id']}",
        actor="autofde-lab:simulation:bridge_gymact",
    )
    constraints = execution_loop.ResourceConstraints(
        deadline_ticks=int(spec.get("deadline_ticks", 200)),
        max_retries=int(spec.get("max_retries", 3)),
        max_provider_switches=int(spec.get("max_provider_switches", 2)),
        max_subject_moves=int(spec.get("max_subject_moves", 2)),
    )
    request = execution_loop.ExecutionRequest(
        work_order=spec["work_order"],
        capability_requirements=list(spec["capability_requirements"]),
        subject=execution_loop.SubjectRef(repo="autofde-lab", sha=_subject_sha(spec)),
        authority=authority,
        evidence_requirements=["verifier"],
        resource_constraints=constraints,
    )

    loop = execution_loop.AutonomousLoop(
        bundle.providers,
        bundle.verifier,
        bundle.registry,
        bundle.probe,
        clock=bundle.clock.now,
        advance=bundle.clock.advance,
        rng=random.Random(seed),
    )

    exception: str | None = None
    result = None
    try:
        result = loop.run(request)
    except Exception as exc:  # escaped the loop entirely: forced-failure path
        exception = f"{type(exc).__name__}: {exc}"

    metrics: dict[str, Any] = {
        "exception": exception,
        "illegal_outcome_observed": False,
        "gymact_import_mechanism": IMPORT_REPORT["mechanism"],
        "gymact_execution_loop_file": IMPORT_REPORT["execution_loop_file"],
        "virtual_tick": bundle.clock.tick,
        "provider_claims": [
            getattr(provider, "claim_calls", None) for provider in bundle.providers
        ],
        "provider_executions": [
            getattr(provider, "execute_calls", None) for provider in bundle.providers
        ],
    }

    receipt_digests: list[str] = []
    if result is not None:
        outcome = result.outcome
        illegal = getattr(result, "asserted_illegal_outcome", "unavailable")
        if illegal is not None and illegal != "unavailable":
            metrics["illegal_outcome_observed"] = True
        metrics.update(
            {
                "outcome": outcome,
                "standing": result.standing.value,
                "episode_standing": result.episode_standing.value,
                "actuation_count": result.actuation_count,
                "typed_reason": result.typed_reason,
                "broken_term": (
                    result.broken_term.value if result.broken_term is not None else None
                ),
                "n_events": len(result.events),
                "event_types": sorted({event.event_type for event in result.events}),
                "ocel_log_digest": _ocel_log_digest(execution_loop, result, seed),
            }
        )
        if result.receipt is not None:
            # sha256 over the receipt's CANONICAL serialization
            # (pydantic model_dump_json -- deterministic: every field is
            # tick/seed-derived; the repr fallback is not needed).
            receipt_digests.append(
                hashlib.sha256(result.receipt.model_dump_json().encode("utf-8")).hexdigest()
            )
    else:
        # Escaped exception: crash-class, not a legal outcome. gymact's
        # EpisodeStanding vocabulary (execution_loop.py:94-114) has exactly
        # one standing for this: FAILED. AUTONOMOUS is reserved for lawful
        # completion and can only be entered, never claimed post-crash.
        metrics["outcome"] = None
        metrics["standing"] = "FAILED"
        metrics["episode_standing"] = "FAILED"

    return {
        "backend": ROW_BACKEND,
        "doctrine_id": doctrine_id,
        "world_id": spec["world_id"],
        "seed": int(seed),
        "metrics": metrics,
        "feasible": _feasible_for(metrics.get("outcome")),
        "receipt_digests": receipt_digests,
    }


def _ocel_log_digest(execution_loop: Any, result: Any, seed: int) -> str:
    """BLAKE3/RFC8785 digest of gymact's own validated OCEL 2.0 log assembly
    (execution_loop.loop_log, :344-401) for the episode's events -- the OCEL
    receipt evidence this backend contributes to the outcome matrix."""
    from gymact.evidence import digest  # resolved against the bound gymact

    return digest(execution_loop.loop_log([result], seed=seed))
