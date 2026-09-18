"""Chicago-style Fortune-5 Semantic A2A production simulation crown.

No mocks: generated worlds, real semantic pipeline, real receipts, real OCEL
projection, real file persistence, and a real HTTP server socket.
"""

from __future__ import annotations

import http.client
import json
import threading
from dataclasses import replace
from http.server import ThreadingHTTPServer

from autofde_lab.fortune5.production import (
    ArtifactStore,
    SimulationService,
    generate_formal_projection,
    generate_world,
    run_simulation,
    verify_ocel2,
    verify_projection_coherence,
)
from autofde_lab.fortune5.production.ocel import project_events_to_ocel2
from autofde_lab.fortune5.production.model import Command, stable_id
from autofde_lab.fortune5.production.native_sa2a import (
    execute_command_through_native_sa2a,
    prove_unbound_admission_refuses,
)
from autofde_lab.fortune5.production.server import make_handler
from autofde_lab.fortune5.production.world import SCALE_PROFILES
from autofde_lab.sa2a.brce.boundary import REFUSED_ADMISSION_CONTENT_NOT_BOUND


def _ocel(run):
    return project_events_to_ocel2(
        run_id=run.run_id,
        world=run.world,
        events=run.events,
        prepared=run.prepared_receipts,
        final=run.final_receipts,
        routes=tuple(run.known_routes),
    )


def test_world_generator_is_deterministic_and_general() -> None:
    for profile, (regions, templates) in SCALE_PROFILES.items():
        first = generate_world(seed=41, scale_profile=profile, horizon_rounds=20)
        second = generate_world(seed=41, scale_profile=profile, horizon_rounds=20)
        assert first.world_digest == second.world_digest
        assert first.canonical == second.canonical
        assert len(first.regions) == regions
        assert len(first.services) == regions * templates
        assert len({service.service_id for service in first.services}) == len(first.services)
        assert all(not service.service_id.startswith("M") for service in first.services)


def test_formal_projection_is_deterministic_and_coherent() -> None:
    world = generate_world(seed=2, scale_profile="enterprise", horizon_rounds=20)
    a = generate_formal_projection(world)
    b = generate_formal_projection(world)
    assert a == b
    ok, violations = verify_projection_coherence(a)
    assert ok, violations
    assert a.world_digest == world.world_digest
    assert "(:action failover" in a.hddl
    assert "(:action failover" in a.fond
    assert ["authorize", "actuate"] in a.powl["order"]


def test_fortune5_end_to_end_zero_unreceipted_authority_closed() -> None:
    world = generate_world(seed=7, scale_profile="fortune5", horizon_rounds=40)
    run = run_simulation(world, rounds=40)
    court = verify_ocel2(_ocel(run))
    assert court["ok"], court["violations"]
    assert court["actuations"] > 0
    assert court["unreceipted_actuations"] == 0
    assert court["authority_violations"] == 0
    assert court["duplicate_effects"] == 0
    assert run.summary.actuations == len(run.final_receipts)
    assert run.summary.energy_budget_violations == 0
    assert run.summary.cost_budget_violations == 0
    assert run.summary.carbon_budget_violations == 0


def test_unknown_promotes_to_known_and_frontier_retires_for_repeat() -> None:
    world = generate_world(seed=1, scale_profile="demo", horizon_rounds=20)
    run = run_simulation(world, rounds=20)
    assert run.summary.frontier_invocations > 0
    assert run.summary.known_routes > 0
    assert run.summary.known_route_hits > 0
    promote_events = [event for event in run.events if event.event_type == "promote_known"]
    known_proposals = [
        event for event in run.events
        if event.event_type == "propose"
        and dict(event.attributes).get("route_source") == "known"
    ]
    assert promote_events
    assert known_proposals


def test_replay_same_seed_same_ocel_and_state() -> None:
    first = run_simulation(
        generate_world(seed=99, scale_profile="enterprise", horizon_rounds=25),
        rounds=25,
    )
    second = run_simulation(
        generate_world(seed=99, scale_profile="enterprise", horizon_rounds=25),
        rounds=25,
    )
    assert first.summary.replay_digest == second.summary.replay_digest
    assert first.summary.ocel_digest == second.summary.ocel_digest
    assert first.final_state == second.final_state
    assert [event.canonical() for event in first.events] == [
        event.canonical() for event in second.events
    ]


def test_no_authority_means_no_actuation() -> None:
    world = generate_world(seed=5, scale_profile="demo", horizon_rounds=20)
    denied = replace(world, authority_grants=())
    run = run_simulation(denied, rounds=20)
    assert run.summary.slo_breaches > 0
    assert run.summary.refused_authority > 0
    assert run.summary.actuations == 0
    assert len(run.final_receipts) == 0


def test_artifact_store_is_atomic_and_verifiable(tmp_path) -> None:
    run = run_simulation(
        generate_world(seed=3, scale_profile="demo", horizon_rounds=15),
        rounds=15,
    )
    store = ArtifactStore(tmp_path)
    manifest = store.persist(run)
    assert "bundle_digest" in manifest
    verification = store.verify(run.run_id)
    assert verification["ok"], verification["failures"]
    run_dir = tmp_path / run.run_id.replace(":", "_")
    assert json.loads((run_dir / "ocel2.json").read_text())["events"]
    assert json.loads((run_dir / "readiness.json").read_text())["technical_standing"] in {
        "ALIVE", "PARTIAL_ALIVE",
    }


def test_real_http_surface_runs_simulation() -> None:
    service = SimulationService()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=20
        )
        connection.request(
            "POST",
            "/api/v1/simulations",
            body=json.dumps({"seed": 11, "rounds": 12, "scale_profile": "demo"}),
            headers={"content-type": "application/json"},
        )
        response = connection.getresponse()
        payload = json.loads(response.read())
        assert response.status == 201
        assert payload["world"]["services"] == 16
        assert payload["summary"]["unreconciled_actuations"] == 0
        run_id = payload["run_id"]
        connection.request("GET", f"/api/v1/simulations/{run_id}/ocel")
        ocel_response = connection.getresponse()
        ocel = json.loads(ocel_response.read())
        assert ocel_response.status == 200
        assert ocel["events"]
        assert ocel["objects"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _native_command(service_id: str) -> Command:
    return Command(
        command_id=stable_id("native-command", service_id, "scale_out"),
        message_id=stable_id("native-message", service_id),
        actor_id="agent:sre",
        actor_role="sre",
        action="scale_out",
        target_service=service_id,
        parameters=(("replicas", "2"),),
        risk=0.30,
        route_id=stable_id("native-route", "config_drift", service_id),
        source="known",
    )


def test_real_sa2a_core_admission_construct_authority_brce_receipt_and_replay() -> None:
    world = generate_world(seed=17, scale_profile="demo", horizon_rounds=12)
    service = world.services[0]
    command = _native_command(service.service_id)
    execution = execute_command_through_native_sa2a(command, service)
    assert execution.admission.is_admitted
    assert execution.result.success
    assert execution.result.prepared_receipt is not None
    assert execution.result.final_receipt is not None
    assert execution.result.final_receipt.postcondition_verified
    assert execution.replay.success
    assert execution.replay.replayed
    assert execution.replay.final_receipt is execution.result.final_receipt
    assert execution.actuator_calls == 1


def test_real_sa2a_core_refuses_content_unbound_to_exact_action_target() -> None:
    world = generate_world(seed=19, scale_profile="demo", horizon_rounds=12)
    service = world.services[0]
    command = _native_command(service.service_id)
    result = prove_unbound_admission_refuses(command, service)
    assert not result.success
    assert result.refusal_code == REFUSED_ADMISSION_CONTENT_NOT_BOUND
    assert result.prepared_receipt is None
