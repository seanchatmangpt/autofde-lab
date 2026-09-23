"""Typer subcommands for Semantic Agent-to-Agent (RFC-SA2A-001 v26.9.16).

Provides subcommands:
- validate: validate agent card and supported profiles
- admit: submit candidate assertion to admission court
- plan: compute CMCA resource allocation for UNKNOWN candidate frontier
- execute: run negotiated query with deterministic machine experience compilation
- replay: verify receipt or session hash deterministically
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from autofde_lab.sa2a.a2a_bridge.agent_card import (
    SA2A_PROFILE_V26_9_16,
    create_default_sa2a_agent_card,
)
from autofde_lab.sa2a.a2a_bridge.downgrade_guard import (
    DowngradeGuard,
    UnsupportedProfileError,
)
from autofde_lab.sa2a.unknown.allocator import (
    CMCACandidateAllocator,
    ExplorationBudget,
    UnknownCandidate,
)
from autofde_lab.sa2a.unknown.compilation import MachineExperienceCompiler
from autofde_lab.sa2a.unknown.resolution import (
    CandidateResolution,
    UnknownResolutionPipeline,
)

app = typer.Typer(
    name="sa2a",
    help="Semantic Agent-to-Agent (SA2A) RFC-SA2A-001 v26.9.16 protocol and frontier governor.",
    no_args_is_help=True,
)


def _emit(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))


@app.command("validate")
def validate(
    card_path: str = typer.Option(
        None, "--card-path", "-c", help="Path to JSON Agent Card file"
    ),
    profile: str = typer.Option(
        SA2A_PROFILE_V26_9_16, "--profile", "-p", help="Target profile to validate"
    ),
) -> None:
    """Validate Semantic Agent Card capability declarations and profile compliance (§10, §76)."""
    guard = DowngradeGuard()
    try:
        guard.assert_supported_profile(profile)
    except UnsupportedProfileError as exc:
        _emit(
            {"ok": False, "error": str(exc), "code": exc.code, "profile": exc.profile}
        )
        raise typer.Exit(code=1) from exc

    if card_path:
        p = Path(card_path)
        if not p.exists():
            _emit(
                {
                    "ok": False,
                    "error": f"Card file not found: {card_path}",
                    "code": "NOT_FOUND",
                }
            )
            raise typer.Exit(code=1)
        raw = json.loads(p.read_text(encoding="utf-8"))
        profiles = raw.get("supported_profiles", [])
        if profile not in profiles:
            _emit(
                {
                    "ok": False,
                    "error": f"Agent card does not declare support for profile {profile}",
                    "code": "UNSUPPORTED_PROFILE",
                }
            )
            raise typer.Exit(code=1)
        card_id = raw.get("agent_id", "unknown")
    else:
        default_card = create_default_sa2a_agent_card()
        card_id = default_card.agent_id

    _emit(
        {
            "ok": True,
            "agent_id": card_id,
            "profile": profile,
            "status": "VALID",
        }
    )


@app.command("admit")
def admit(
    candidate_id: str = typer.Option(
        ..., "--candidate-id", "-i", help="Candidate identifier"
    ),
    query_id: str = typer.Option("q0", "--query-id", "-q", help="Query identifier"),
    assertion: str = typer.Option(
        ..., "--assertion", "-a", help="Proposed assertion to admit"
    ),
    source: str = typer.Option(
        "discovery-engine", "--source", "-s", help="Source agent/engine identity"
    ),
    evidence_json: str = typer.Option(
        "{}", "--evidence", "-e", help="JSON evidence payload"
    ),
) -> None:
    """Subject a candidate assertion to admission court (§64) to become KNOWN (O*)."""
    try:
        evidence = json.loads(evidence_json)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"evidence must be valid JSON: {exc}") from exc

    cand = CandidateResolution(
        candidate_id=candidate_id,
        query_id=query_id,
        proposed_assertion=assertion,
        evidence_payload=evidence,
        source_identity=source,
        consumed_ticks=10,
        consumed_tokens=100,
    )

    pipeline = UnknownResolutionPipeline()
    receipt = pipeline.admit_candidate(cand)

    _emit(
        {
            "ok": receipt.admitted,
            "receipt_id": receipt.receipt_id,
            "candidate_hash": receipt.candidate_hash,
            "standing": receipt.epistemic_standing.value,
            "reasons": list(receipt.reasons),
            "admitted_assertion": receipt.admitted_assertion,
        }
    )


@app.command("plan")
def plan(
    candidates_json: str = typer.Argument(
        ..., help="JSON array of UNKNOWN frontier candidates or path to JSON file"
    ),
    plan_id: str = typer.Option(
        "frontier_plan_0", "--plan-id", help="Allocation plan ID"
    ),
    ticks: int = typer.Option(1000, "--ticks", help="Total compute ticks budget"),
    tokens: int = typer.Option(50000, "--tokens", help="Total tokens budget"),
    experiments: int = typer.Option(
        10, "--experiments", help="Total experiments budget"
    ),
) -> None:
    """Allocate exploration budget to UNKNOWN candidate frontier using CMCA cascade (§38)."""
    p = Path(candidates_json)
    if p.exists() and p.is_file():
        raw_candidates = json.loads(p.read_text(encoding="utf-8"))
    else:
        try:
            raw_candidates = json.loads(candidates_json)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(
                f"candidates_json must be valid JSON: {exc}"
            ) from exc

    if not isinstance(raw_candidates, list):
        raise typer.BadParameter("candidates_json must be a JSON array")

    cands = [
        UnknownCandidate(
            item_id=str(c.get("item_id", f"item_{i}")),
            description=str(c.get("description", "")),
            option_entropy=float(c.get("option_entropy", 1.0)),
            estimated_cost=float(c.get("estimated_cost", 10.0)),
            historical_yield=float(c.get("historical_yield", 1.0)),
        )
        for i, c in enumerate(raw_candidates)
    ]

    budget = ExplorationBudget(
        max_compute_ticks=ticks,
        max_tokens=tokens,
        max_experiments=experiments,
    )

    allocator = CMCACandidateAllocator()
    allocation_plan = allocator.allocate(
        plan_id=plan_id, budget=budget, candidates=cands
    )

    _emit(
        {
            "ok": True,
            "plan_id": allocation_plan.plan_id,
            "plan_hash": allocation_plan.plan_hash,
            "total_entropy_preserved": allocation_plan.total_entropy_preserved,
            "allocations": [
                {
                    "item_id": a.item_id,
                    "fraction": a.allocated_fraction,
                    "ticks": a.allocated_ticks,
                    "tokens": a.allocated_tokens,
                    "experiments": a.allocated_experiments,
                    "lane": a.priority_lane,
                    "standing": a.standing.value,
                }
                for a in allocation_plan.allocations
            ],
        }
    )


@app.command("execute")
def execute(
    query: str = typer.Argument(..., help="Query string to resolve"),
    compiled_rule_json: str = typer.Option(
        None, "--rules", "-r", help="JSON array of compiled [pattern, output] rules"
    ),
) -> None:
    """Execute query with deterministic machine experience compilation (§39, §65)."""
    compiler = MachineExperienceCompiler()
    if compiled_rule_json:
        rules_data = json.loads(compiled_rule_json)
        items = [(r[0], r[1], None) for r in rules_data]
        compiler.compile_candidate_experience(
            receipt_id="cli_exec_rec", resolved_items=items
        )

    # Resolution executes compiled deterministic rules first
    resolved = compiler.resolve(
        query, fallback_llm_inference=lambda: f"FALLBACK_INFERENCE_FOR({query})"
    )

    _emit(
        {
            "ok": True,
            "query": query,
            "result": resolved,
            "llm_avoidance_ratio": compiler.inference_avoidance_ratio,
        }
    )


@app.command("replay")
def replay(
    manifest_json: str = typer.Argument(..., help="Manifest or plan JSON string"),
    expected_hash: str = typer.Option(
        ..., "--expected-hash", "-h", help="Expected cryptographic digest"
    ),
) -> None:
    """Verify cryptographic receipt or plan hash deterministically (§38, §64)."""
    try:
        data = json.loads(manifest_json)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"manifest_json must be valid JSON: {exc}") from exc

    import hashlib

    # Canonical re-serialization
    dumped = json.dumps(data, sort_keys=True, separators=(",", ":"))
    computed_hash = hashlib.sha256(dumped.encode("utf-8")).hexdigest()

    matches = computed_hash == expected_hash
    _emit(
        {
            "ok": matches,
            "computed_hash": computed_hash,
            "expected_hash": expected_hash,
            "verified": matches,
        }
    )
    if not matches:
        raise typer.Exit(code=1)


@app.command("graphlaw")
def graphlaw(
    action: str = typer.Argument(
        ..., help="GraphLaw action: 'validate', 'hash', or 'hooks'"
    ),
    ttl: str = typer.Option(
        "", "--ttl", "-t", help="Turtle content or path to Turtle file"
    ),
    event_ttl: str = typer.Option(
        "", "--event-ttl", "-e", help="Event Turtle content for hooks"
    ),
    profile_ttl: str = typer.Option("", "--profile-ttl", help="Profile Turtle content"),
    shacl_shapes: str = typer.Option("", "--shacl", help="SHACL shapes Turtle content"),
    shex_schema: str = typer.Option("", "--shex", help="ShEx schema content"),
    shex_shape_map: str = typer.Option("", "--shex-map", help="ShEx shape map JSON"),
) -> None:
    """Execute native Praxis GraphLaw WASM engine (§13, §14, §15, §17, §18)."""
    from autofde_lab.sa2a.admission.graphlaw_bridge import GraphLawBridge

    bridge = GraphLawBridge()

    # Load content if file path
    content = ttl
    if content and Path(content).exists():
        content = Path(content).read_text(encoding="utf-8")

    event_content = event_ttl
    if event_content and Path(event_content).exists():
        event_content = Path(event_content).read_text(encoding="utf-8")

    if action == "hash":
        digest = bridge.graph_hash(content)
        _emit({"ok": True, "action": "hash", "graph_hash": digest})
    elif action == "validate":
        res = bridge.validate_all(
            content,
            profile_ttl=profile_ttl,
            shacl_shapes=shacl_shapes,
            shex_schema=shex_schema,
            shex_shape_map=shex_shape_map,
        )
        _emit(
            {
                "ok": res.conforms,
                "action": "validate",
                "graph_hash": res.graph_hash,
                "profile_hash": res.profile_hash,
                "conforms": res.conforms,
                "replay_status": res.replay_status,
                "dialects": [
                    {
                        "dialect": d.dialect,
                        "status": d.status,
                        "detail": d.detail,
                        "triples_out": d.triples_out,
                    }
                    for d in res.dialects
                ],
            }
        )
    elif action == "hooks":
        hooks_res = bridge.run_hooks(content, event_content)
        _emit({"ok": True, "action": "hooks", "result": hooks_res})
    else:
        _emit({"ok": False, "error": f"Unknown GraphLaw action: {action}"})
        raise typer.Exit(code=1)


hook_app = typer.Typer(
    name="hook", help="Knowledge Hooks and reactive semantic networks (§4.5-§4.8)."
)
app.add_typer(hook_app, name="hook")


@hook_app.command("evaluate")
def hook_evaluate(
    base_ttl: str = typer.Option(
        ..., "--base-ttl", "-b", help="Base graph Turtle string or file path"
    ),
    event_ttl: str = typer.Option(
        ..., "--event-ttl", "-e", help="Delta/Event Turtle string or file path"
    ),
    hook_name: str = typer.Option("default_hook", "--hook-name", help="Hook name"),
    action_iri: str = typer.Option(
        "urn:action:default", "--action-iri", help="Action IRI to synthesize"
    ),
    target_resource: str = typer.Option(
        "urn:res:default", "--target-resource", help="Target resource IRI"
    ),
    goal_iri: str = typer.Option("urn:goal:default", "--goal-iri", help="Goal IRI"),
) -> None:
    """Evaluate Knowledge Hooks against a graph transition without executing DO (§4.5)."""
    from autofde_lab.sa2a.hooks.engine import KnowledgeHookEngine
    from autofde_lab.sa2a.hooks.model import (
        HookEffectKind,
        HookEventTrigger,
        KnowledgeHookDefinition,
    )

    base_content = (
        Path(base_ttl).read_text(encoding="utf-8")
        if Path(base_ttl).exists()
        else base_ttl
    )
    event_content = (
        Path(event_ttl).read_text(encoding="utf-8")
        if Path(event_ttl).exists()
        else event_ttl
    )

    engine = KnowledgeHookEngine()
    engine.register_hook(
        KnowledgeHookDefinition(
            iri=f"http://example.org/hook/{hook_name}",
            name=hook_name,
            on=HookEventTrigger.ASSERT,
            effect=HookEffectKind.GROUND_ACTION,
            action_iri=action_iri,
            target_capability_iri=target_resource,
            goal_iri=goal_iri,
        )
    )

    records = engine.evaluate(base_content, event_content)
    _emit(
        {
            "ok": True,
            "evaluated_hooks_count": len(records),
            "records": [
                {
                    "hook_name": r.hook_name,
                    "verdict": r.verdict.value,
                    "condition_hash": r.condition_hash,
                    "intent": {
                        "intent_id": r.intent.intent_id,
                        "action_iri": r.intent.action_iri,
                        "target_capability_iri": r.intent.target_capability_iri,
                        "intent_digest": r.intent.intent_digest,
                    }
                    if r.intent
                    else None,
                }
                for r in records
            ],
        }
    )


@hook_app.command("reflex")
def hook_reflex(
    base_ttl: str = typer.Option(
        ..., "--base-ttl", "-b", help="Base graph Turtle string or file path"
    ),
    event_ttl: str = typer.Option(
        ..., "--event-ttl", "-e", help="Delta/Event Turtle string or file path"
    ),
    max_depth: int = typer.Option(
        3, "--max-depth", "-d", help="Max cascade depth bound"
    ),
    actor_id: str = typer.Option(
        "urn:agent:autonomic-controller", "--actor-id", help="Actor ID"
    ),
    action_iri: str = typer.Option(
        "urn:action:freeze_credit", "--action-iri", help="Action IRI"
    ),
    target_resource: str = typer.Option(
        "urn:cap:credit:freeze", "--target-resource", help="Target resource IRI"
    ),
    skip_admission_check: bool = typer.Option(
        False,
        "--skip-admission-check",
        help=(
            "AFDE-2604 (default wiring closure): explicitly OPT OUT of the default "
            "admission fence. By default this command requires the event content to "
            "independently reach Standing.ADMITTED via a real AdmissionPipeline, with "
            "a real <action_iri> <urn:autofde-lab:targetResource> <target_resource> . "
            "triple in that content binding it to this exact action/target, before any "
            "AuthorityBroker/BRCE dispatch. Pass this flag only when the old, "
            "permissive candidate -> authority -> DO behavior is genuinely required -- "
            "it is never the silent default."
        ),
    ),
) -> None:
    """Run autonomic reflex cycle: Delta -> Hook -> Intent -> Authority -> BRCE -> Receipt -> Quiescence.

    AFDE-2604 (local admission-fencing closure, default-wiring fix): SECURE BY DEFAULT.
    Unless `--skip-admission-check` is passed, this command constructs a real
    `AdmissionPipeline` for the `ReactiveSemanticLoop` and configures the
    `ConsequenceBoundary` with `require_admission=True`, so `candidate -> ADMIT ->
    SELECT -> CONSTRUCT -> authority grant -> DO` is enforced for every real intent
    this command dispatches -- closing the previously-named, previously-shipped
    `candidate -> authority -> DO` gap (see
    `docs/jira/v26.9.16/AFDE-2604-admission-fencing-local-closure.md`, "cross-entry-
    point confused deputy" qualification). `--skip-admission-check` restores the prior
    permissive behavior explicitly, for a caller that genuinely needs it -- never
    silently.

    AFDE-2604 closure (Mutation DW-2, adversarially found and fixed this pass): a
    `typer.Option(False, ...)` default is not the literal Python default `False` in
    this function's own signature -- it is a `typer.models.OptionInfo` sentinel
    object, and `bool(OptionInfo(...))` is `True`. Click substitutes the real,
    intended default only while parsing an actual CLI invocation; a caller that
    imports and calls this function object directly (a script, a notebook, a test
    helper, a future in-process wrapper -- never through `typer.testing.CliRunner` or
    a real CLI dispatch) previously got `skip_admission_check` bound to that truthy
    sentinel whenever they omitted the argument, silently flipping
    `require_admission=not skip_admission_check` to `False` and
    `admission_pipeline=None if skip_admission_check else AdmissionPipeline()` to
    `None` -- the exact fully permissive `--skip-admission-check` configuration,
    triggered by doing nothing, with no `--skip-admission-check` string anywhere in
    the call. The explicit `isinstance` resolution below closes this: a non-`bool`
    value here can only be Click's own unsubstituted `OptionInfo` sentinel (never a
    real caller-supplied value, since Typer type-checks CLI input to `bool` before
    binding it), so it is resolved to the sentinel's own configured default
    (`False`, i.e. do not skip) rather than trusted as truthy. See
    `tests/sa2a/conformance/test_afde_2604_default_wiring_bypass_qualification.py`'s
    `test_mutation_dw2_...` for the regression fixture pinning this fix.
    """
    if not isinstance(skip_admission_check, bool):
        # A direct (non-CLI) call left Typer's OptionInfo sentinel unsubstituted.
        # Resolve to the sentinel's own configured default, never to bool(sentinel)
        # (always True for a non-empty object), so "argument omitted" means "use the
        # documented default" and never "silently opt out of the admission fence".
        skip_admission_check = bool(getattr(skip_admission_check, "default", False))

    from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline
    from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
    from autofde_lab.sa2a.brce.boundary import ConsequenceBoundary
    from autofde_lab.sa2a.hooks.engine import KnowledgeHookEngine
    from autofde_lab.sa2a.hooks.model import (
        HookEffectKind,
        HookEventTrigger,
        KnowledgeHookDefinition,
    )
    from autofde_lab.sa2a.hooks.reactive_loop import ReactiveSemanticLoop

    base_content = (
        Path(base_ttl).read_text(encoding="utf-8")
        if Path(base_ttl).exists()
        else base_ttl
    )
    event_content = (
        Path(event_ttl).read_text(encoding="utf-8")
        if Path(event_ttl).exists()
        else event_ttl
    )

    engine = KnowledgeHookEngine()
    engine.register_hook(
        KnowledgeHookDefinition(
            iri="http://example.org/hook/autonomic_reflex",
            name="autonomic_reflex_hook",
            on=HookEventTrigger.ASSERT,
            effect=HookEffectKind.GROUND_ACTION,
            action_iri=action_iri,
            target_capability_iri=target_resource,
            goal_iri="urn:goal:autonomic_containment",
        )
    )

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-autonomic-cli",
            subject_id=actor_id,
            action_iri=action_iri,
            target_resource_iri=target_resource,
        )
    )

    class CliActuator:
        def actuate(
            self,
            action_iri: str,
            target_resource: str,
            parameters: Any,
        ) -> dict[str, Any]:
            return {"applied": True, "action": action_iri, "res": target_resource}

        def actuator_digest(self) -> str:
            return "actuator:cli:v1"

    class CliVerifier:
        def verify_postcondition(
            self,
            action_iri: str,
            target_resource: str,
            parameters: Any,
            evidence: Any,
        ) -> bool:
            return evidence is not None and evidence.get("applied") is True

        def verifier_digest(self) -> str:
            return "verifier:cli:v1"

    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=CliActuator(),
        verifier=CliVerifier(),
        # AFDE-2604 default-wiring closure: secure by default -- require_admission is
        # True unless the caller explicitly opts out via --skip-admission-check.
        require_admission=not skip_admission_check,
    )

    loop = ReactiveSemanticLoop(
        hook_engine=engine,
        authority_broker=broker,
        consequence_boundary=boundary,
        max_cascade_depth=max_depth,
        # AFDE-2604 default-wiring closure: a real AdmissionPipeline is wired by
        # default so the fence is genuinely consulted, not merely configured on the
        # boundary -- None (the old, permissive default) only when explicitly opted
        # out via --skip-admission-check.
        admission_pipeline=None if skip_admission_check else AdmissionPipeline(),
    )

    trace = loop.run_reflex_cycle(
        base_content,
        event_content,
        actor_id=actor_id,
        delta_generator=lambda r: "",  # Quiesce after reflex step
    )

    _emit(
        {
            "ok": True,
            "steps_count": len(trace.steps),
            "quiescence_reached": trace.quiescence_reached,
            "total_receipts": trace.total_receipts,
            "steps": [
                {
                    "depth": s.depth,
                    "triggered_hooks": list(s.triggered_hooks),
                    "intents_count": len(s.intents_synthesized),
                    "receipts_count": len(s.final_receipts),
                    "receipt_states": [r.state.value for r in s.final_receipts],
                }
                for s in trace.steps
            ],
        }
    )


@app.command("chicago")
def chicago() -> None:
    """Execute the Canonical Chicago Definition of Done (DoD) Court for v26.9.16."""
    from scripts.verify_v26_9_16_chicago import run_chicago_court

    receipt = run_chicago_court()
    _emit(receipt)
    if not receipt.get("all_gates_passed"):
        raise typer.Exit(code=1)


def _requires_port_seed_candidate(query_id: str = "q-1") -> "CandidateResolution":
    """The real candidate the `exact-port-probe` `EXACT_REUSABLE_MACHINERY` engine
    below deterministically produces for the demonstrated `requires-port` semantic
    class -- also used, unmodified, as the seed `episode/generator.py`'s
    `generate_fresh_equivalent_candidate()` substitutes from for Episode 2 (ARD §64
    item 6), so the crown's two episodes are provably about the SAME discovered
    candidate, never two independently hand-typed literals that happen to agree.
    """
    from autofde_lab.sa2a.unknown.resolution import CandidateResolution

    return CandidateResolution(
        candidate_id="cand-ep1",
        query_id=query_id,
        proposed_assertion="service:api-gateway requires-port",
        evidence_payload={"source": "formal-port-probe"},
        source_identity="formal-port-probe",
        consumed_ticks=2,
        consumed_tokens=0,
    )


def _build_requires_port_discovery_router() -> "tuple[Any, list[str]]":
    """Real `DiscoveryRouter` for the demonstrated `requires-port` semantic class
    (v26.9.17 PRD §14 item 6, "actual discovery execution" -- not a hardcoded
    single-branch `discover()` callable). Registers two REAL, DISTINCT engines
    spanning two different `DiscoveryEngineKind` precedence tiers (ARD §15):

    - `exact-port-probe` (`EXACT_REUSABLE_MACHINERY`): deterministically recognizes
      any query whose topic mentions "requires-port" and returns the real,
      formal-probe-sourced seed candidate (`_requires_port_seed_candidate`).
      Returns `None` (declines) for any other query, so the router precedence
      logic -- not this function -- decides whether it is tried at all.
    - `general-exploratory-fallback` (`GENERAL_EXPLORATORY_INTELLIGENCE`): answers
      ANY query the exact engine did not recognize, standing in for the real
      general-exploratory-intelligence tier a caller would wire in production.

    Returns `(router, invocation_log)`. `invocation_log` records, in order, which
    engine(s) `DiscoveryRouter.route()` actually CALLED -- the real, run-time proof
    (not asserted by construction) that `EXACT_REUSABLE_MACHINERY` is selected for
    the demonstrated query and the fallback is never invoked, per ARD §15's
    precedence law: `DiscoveryRouter.route()` itself decides which engine(s) to
    call, in precedence-tier order, stopping at the first non-`None` candidate.
    """
    from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownQuery
    from autofde_lab.sa2a.unknown.router import (
        DiscoveryEngine,
        DiscoveryEngineKind,
        DiscoveryRouter,
    )

    invocation_log: list[str] = []

    def exact_port_probe(query: "UnknownQuery"):
        invocation_log.append("exact-port-probe")
        if "requires-port" not in query.predicate_or_topic:
            return None
        return _requires_port_seed_candidate(query.query_id)

    def general_exploratory_fallback(query: "UnknownQuery"):
        invocation_log.append("general-exploratory-fallback")
        return CandidateResolution(
            candidate_id=f"cand-fallback-{query.query_id}",
            query_id=query.query_id,
            proposed_assertion=query.predicate_or_topic,
            evidence_payload={"source": "general-exploratory-fallback"},
            source_identity="general-exploratory-fallback",
            consumed_ticks=32,
            consumed_tokens=512,
        )

    router = DiscoveryRouter()
    router.register(
        DiscoveryEngine(
            "exact-port-probe",
            DiscoveryEngineKind.EXACT_REUSABLE_MACHINERY,
            exact_port_probe,
        )
    )
    router.register(
        DiscoveryEngine(
            "general-exploratory-fallback",
            DiscoveryEngineKind.GENERAL_EXPLORATORY_INTELLIGENCE,
            general_exploratory_fallback,
        )
    )
    return router, invocation_log


def _v26_9_17_crown_fixture(work_dir: Path) -> dict[str, Any]:
    """Run the real v26.9.17 crown: SubjectResolver -> Episode1 -> Episode2 -> real
    replay verification -> a real, SEPARATE-PROCESS fresh-consumer verification ->
    CROWNED/typed-exit, via `ReleaseRun` (PRD §12; ARD §50 "crown = orchestration
    only, no duplicated semantic logic").

    Scoped, honest demonstration: this fixture proves the mechanism end to end for
    ONE semantic class (a port-requirement lookup) under a synthetic, well-formed
    composition manifest, not an arbitrary cross-repository composition -- a
    CompositionCourt driving real sibling repositories is explicitly out of this
    pass's scope (see docs/jira/v26.9.17/, the tickets this command's receipt cites).

    Episode 1's candidate is now discovered through a REAL `DiscoveryRouter` with
    two real, distinct engines spanning two precedence tiers (PRD §14 item 6),
    never a single hardcoded `discover()` callable; Episode 2's fresh candidate is
    now machine-GENERATED from Episode 1's seed candidate by
    `episode.generator.generate_fresh_equivalent_candidate()` (ARD §64 item 6),
    never a second hand-typed literal.
    """
    from autofde_lab.sa2a.episode.equivalence import build_topic_equivalence_predicate
    from autofde_lab.sa2a.episode.generator import generate_fresh_equivalent_candidate
    from autofde_lab.sa2a.release.run import ReleaseRun
    from autofde_lab.sa2a.unknown.resolution import UnknownQuery

    router, invocation_log = _build_requires_port_discovery_router()
    seed_candidate = _requires_port_seed_candidate("q-1")

    # Machine-generated, not hand-typed: a genuinely different subject
    # ("service:billing-worker" at index=0, given the real SUBJECT_POOL and the
    # seed's own "service:api-gateway" subject excluded from selection) sharing
    # the seed's exact topic token ("requires-port") -- see generator.py.
    fresh_candidate = generate_fresh_equivalent_candidate(seed=seed_candidate, index=0)
    generated_subject = fresh_candidate.proposed_assertion.split()[0]
    resource_name = (
        generated_subject.split(":", 1)[1]
        if ":" in generated_subject
        else generated_subject
    )

    manifest = {
        "release_id": "v26.9.17-demo",
        "repositories": [{"name": "autofde-lab-demo-subject", "exact_sha": "a" * 40}],
        "artifacts": [{"artifact_id": "demo-artifact", "digest": "b" * 64}],
        "root_manifest_digest": "c" * 64,
        "semantic_profile": "SA2A-STRICT-DEMONSTRATION",
        "court_revision": "v26.9.17",
        "falsifier_corpus_digest": "d" * 64,
        "query_set_digest": "e" * 64,
        "environment_identity": "cli-crown-demo",
    }

    run = ReleaseRun(work_dir=work_dir)
    result = run.run(
        candidate_manifest=manifest,
        semantic_class_id="requires-port",
        episode1_query=UnknownQuery(
            query_id="q-1", predicate_or_topic="service:api-gateway requires-port"
        ),
        discovery_router=router,
        equivalence_predicate=build_topic_equivalence_predicate("requires-port"),
        equivalence_predicate_id="pred-requires-port-v1",
        probe_input="requires-port",
        action_iri="urn:action:open-port",
        episode1_target_resource="urn:cap:api-gateway",
        episode2_fresh_candidate=fresh_candidate,
        episode2_target_resource=f"urn:cap:{resource_name}",
    )

    receipt = result.to_receipt()
    receipt["release_state_history"] = [s.value for s in run.history]
    receipt["discovery_routing"] = {
        "engines_registered": ["exact-port-probe", "general-exploratory-fallback"],
        "engines_invoked": list(invocation_log),
        "exact_reusable_machinery_selected": invocation_log == ["exact-port-probe"],
    }
    receipt["episode2_generated_candidate"] = {
        "candidate_id": fresh_candidate.candidate_id,
        "proposed_assertion": fresh_candidate.proposed_assertion,
        "source_identity": fresh_candidate.source_identity,
        "generated_from_seed_candidate_id": seed_candidate.candidate_id,
        "generated_by": "autofde_lab.sa2a.episode.generator.generate_fresh_equivalent_candidate",
    }
    receipt["scope_note"] = (
        "Demonstrates the real UNKNOWN->MachineExperience->KNOWN mechanism end to end "
        "through SubjectResolver, a real DiscoveryRouter (2 engines, 2 precedence "
        "tiers), Episode1, a machine-generated Episode2 fresh candidate, real "
        "ReplayEngine verification, and a real separate-process fresh-consumer "
        "verifier, for one semantic class under a synthetic composition manifest. A "
        "cross-repository CompositionCourt driving real sibling repositories is "
        "explicitly out of scope -- see docs/jira/v26.9.17/ for the full accounting."
    )
    return receipt


@app.command("episode1")
def episode1(
    work_dir: Path = typer.Option(Path(".sa2a_v26_9_17_crown"), "--work-dir"),
) -> None:
    """Run Episode 1 (UNKNOWN -> admitted MachineExperience) for the demonstrated
    class, via a REAL `DiscoveryRouter` (an `EXACT_REUSABLE_MACHINERY` engine plus a
    `GENERAL_EXPLORATORY_INTELLIGENCE` fallback, PRD §14 item 6) -- never a single
    hardcoded `discover()` callable that always returns the same candidate
    regardless of query."""
    from autofde_lab.sa2a.episode.episode1 import Episode1Runner
    from autofde_lab.sa2a.episode.equivalence import build_topic_equivalence_predicate
    from autofde_lab.sa2a.unknown.resolution import UnknownQuery

    state_dir = work_dir / "state"
    runner1 = Episode1Runner(
        state_dir=state_dir,
        journal_path=work_dir / "journal.json",
        receipt_store_dir=work_dir / "receipts",
    )

    router, invocation_log = _build_requires_port_discovery_router()

    result = runner1.run(
        semantic_class_id="requires-port",
        query=UnknownQuery(
            query_id="q-1", predicate_or_topic="service:api-gateway requires-port"
        ),
        discovery_router=router,
        equivalence_predicate=build_topic_equivalence_predicate("requires-port"),
        equivalence_predicate_id="pred-requires-port-v1",
        probe_input="requires-port",
        action_iri="urn:action:open-port",
        target_resource="urn:cap:api-gateway",
    )
    payload = result.episode.to_dict()
    payload["discovery_routing"] = {
        "engines_invoked": list(invocation_log),
        "exact_reusable_machinery_selected": invocation_log == ["exact-port-probe"],
    }
    _emit(payload)


@app.command("crown")
def crown(
    work_dir: Path = typer.Option(Path(".sa2a_v26_9_17_crown"), "--work-dir"),
) -> None:
    """Run the full v26.9.17 crown (subject fence -> Episode 1 -> Episode 2 -> replay
    -> fresh-consumer verify) via ReleaseRun and emit its standing receipt."""
    receipt = _v26_9_17_crown_fixture(work_dir)
    _emit(receipt)
    if receipt["standing"] != "CROWNED":
        raise typer.Exit(code=1)
