from __future__ import annotations

from autofde_lab.agent.software_manufacturing_history import (
    HistoricalEvent,
    ReplayWorld,
    compile_history,
)


def _event(
    index: int,
    kind: str,
    *,
    paths: tuple[str, ...] = (),
    intent: str | None = None,
    sha: str = "",
    depends_on: tuple[str, ...] = (),
) -> HistoricalEvent:
    metadata: dict[str, object] = {
        "episode": "august-full-stack-example",
        "objective": "close-full-stack-delivery-loop",
    }
    if intent:
        metadata["intent"] = intent
    if depends_on:
        metadata["depends_on"] = depends_on
    return HistoricalEvent(
        event_id=f"e{index:05d}",
        timestamp=f"2026-08-31T12:{index:02d}:00Z",
        repository="seanchatmangpt/beam4pm",
        kind=kind,
        ref="feat/full-stack",
        sha=sha,
        changed_paths=paths,
        metadata=metadata,
    )


def _full_stack_events() -> tuple[HistoricalEvent, ...]:
    return (
        _event(0, "branch_created", intent="open-workstream"),
        _event(
            1,
            "commit",
            paths=("src/beam4pm/runtime.ex",),
            intent="implement-runtime",
            sha="1" * 40,
        ),
        _event(
            2,
            "commit",
            paths=("tests/runtime_test.exs",),
            intent="falsify-runtime",
            sha="2" * 40,
        ),
        _event(
            3,
            "commit",
            paths=("infra/aws/main.tf",),
            intent="manufacture-infrastructure",
            sha="3" * 40,
        ),
        _event(
            4,
            "commit",
            paths=("Dockerfile", "k8s/deployment.yaml"),
            intent="qualify-container",
            sha="4" * 40,
        ),
        _event(
            5,
            "commit",
            paths=("security/iam-policy.json",),
            intent="enforce-authority",
            sha="5" * 40,
        ),
        _event(
            6,
            "commit",
            paths=("src/beam4pm/otel.ex",),
            intent="instrument-observability",
            sha="6" * 40,
        ),
        _event(
            7,
            "commit",
            paths=(".github/workflows/ci.yml",),
            intent="repair-exact-head-ci",
            sha="7" * 40,
        ),
        _event(
            8,
            "commit",
            paths=("docs/runbook.md",),
            intent="publish-runbook",
            sha="8" * 40,
        ),
        _event(9, "pull_request", intent="open-pr"),
        _event(10, "workflow_run", intent="exact-head-green"),
        _event(11, "merge", intent="merge-qualified-head"),
        _event(12, "release", intent="publish-release"),
        _event(
            13,
            "default_branch_containment",
            intent="prove-default-branch-containment",
        ),
    )


def test_compile_full_stack_history_into_replayable_plan() -> None:
    manifest, plans = compile_history(
        _full_stack_events(),
        period="2026-08",
        reported_commit_count=24_340,
    )

    assert manifest["reported_commit_count"] == 24_340
    assert manifest["observed_commit_count"] == 8
    assert manifest["complete_history_observed"] is False
    assert len(plans) == 1

    plan = plans[0]
    surfaces = set(plan["surfaces"])
    assert {
        "source",
        "tests",
        "ci_cd",
        "iac",
        "container",
        "github",
        "docs",
        "security",
        "observability",
        "cloud",
        "release",
    }.issubset(surfaces)
    assert plan["world"]["closure_expected"] is True
    assert plan["authority"]["do_authority"] is False
    assert len(plan["historical_trace"]["commit_shas"]) == 8


def test_replay_world_enforces_dependencies_and_closes() -> None:
    _, plans = compile_history(_full_stack_events(), period="2026-08")
    world = ReplayWorld(plans[0])
    steps = plans[0]["plan"]["steps"]

    first = steps[0]["id"]
    second = steps[1]["id"]
    assert world.admissible_actions() == (first,)

    try:
        world.apply(second, agent="challenger")
    except ValueError as exc:
        assert "not admissible" in str(exc)
    else:
        raise AssertionError("replay accepted a dependency-violating action")

    receipt = world.run_reference()
    assert receipt["state"] == "ALIVE"
    assert receipt["authority"] == "NONE"
    assert receipt["do_authority"] is False
    assert receipt["evidence_kind"] == "SIMULATION_RECEIPT"
    assert len(receipt["completed_steps"]) == len(steps)


def test_reported_commit_total_never_masquerades_as_observed_history() -> None:
    manifest, _ = compile_history(
        _full_stack_events()[:3],
        period="2026-08",
        reported_commit_count=24_340,
    )

    assert manifest["reported_commit_count"] == 24_340
    assert manifest["observed_commit_count"] == 2
    assert manifest["complete_history_observed"] is False


def test_24340_commit_scale_compiles_compactly_and_deterministically() -> None:
    events = tuple(
        HistoricalEvent(
            event_id=f"c{index:05d}",
            timestamp="2026-08-31T23:59:59Z",
            repository="seanchatmangpt/scale-court",
            kind="commit",
            ref="experiment/24k",
            sha=f"{index:040x}",
            changed_paths=("src/manufacture.py",),
            metadata={
                "episode": "august-24k-scale-court",
                "objective": "prove-24340-event-planning-capacity",
                "intent": "manufacture-transition",
            },
        )
        for index in range(24_340)
    )

    manifest_a, plans_a = compile_history(
        events,
        period="2026-08",
        reported_commit_count=24_340,
    )
    manifest_b, plans_b = compile_history(
        reversed(events),
        period="2026-08",
        reported_commit_count=24_340,
    )

    assert manifest_a["observed_commit_count"] == 24_340
    assert manifest_a["complete_history_observed"] is True
    assert manifest_a["corpus_digest"] == manifest_b["corpus_digest"]
    assert plans_a[0]["plan_digest"] == plans_b[0]["plan_digest"]
    assert len(plans_a[0]["plan"]["steps"]) == 1
    assert plans_a[0]["plan"]["steps"][0]["count"] == 24_340
    assert len(plans_a[0]["historical_trace"]["commit_shas"]) == 24_340
