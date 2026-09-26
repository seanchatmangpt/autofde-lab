"""OCEL projection falsifiers for SWE-Prometheus/VGG evidence."""

from __future__ import annotations

import copy

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.prometheus import REPORT_SCHEMA
from autofde_lab.iec.crowns.prometheus_ocel import OCEL_SCHEMA, project_ocel
from autofde_lab.iec.crowns.prometheus_probe import PAIR_SCHEMA, RUN_SCHEMA


def receipt(
    probe_id: str,
    *,
    role: str,
    side: str,
    dimension: str | None = None,
    observed_at: str = "2026-09-26T04:00:00Z",
) -> dict:
    return {
        "probe_id": probe_id,
        "role": role,
        "dimension": dimension,
        "status": "pass",
        "exit_code": 0,
        "stdout_digest": f"sha256:stdout-{probe_id}-{side}",
        "stderr_digest": f"sha256:stderr-{probe_id}-{side}",
        "duration_ms": 1.5,
        "observed_at": observed_at,
        "semantic_id": f"sha256:receipt-{probe_id}-{side}",
    }


def fixtures():
    base = {
        "schema": RUN_SCHEMA,
        "side": "base",
        "run_id": "sha256:base-run",
        "receipts": [
            receipt(
                "tests",
                role="governance",
                side="base",
                dimension="tests_ci",
                observed_at="2026-09-26T04:00:00Z",
            ),
            receipt(
                "behavior",
                role="behavior",
                side="base",
                observed_at="2026-09-26T04:00:01Z",
            ),
        ],
    }
    treated = {
        "schema": RUN_SCHEMA,
        "side": "treated",
        "run_id": "sha256:treated-run",
        "receipts": [
            receipt(
                "tests",
                role="governance",
                side="treated",
                dimension="tests_ci",
                observed_at="2026-09-26T04:00:02Z",
            ),
            receipt(
                "mutation",
                role="mutation",
                side="treated",
                observed_at="2026-09-26T04:00:03Z",
            ),
        ],
    }
    pair = {
        "schema": PAIR_SCHEMA,
        "pair_id": "sha256:pair",
        "repository": "org/repo",
        "base_commit": "abc",
        "patch_digest": "sha256:patch",
        "base_run_id": "sha256:base-run",
        "treated_run_id": "sha256:treated-run",
        "behavior": "preserved",
        "gate_strength": "detected",
    }
    report = {
        "schema": REPORT_SCHEMA,
        "id": "sha256:report",
        "subject": "git:org/repo@abc",
        "patch_digest": "sha256:patch",
        "gate": "PASS",
        "paper": {"ngi": 0.5},
        "vgg": {"standing": "ALIVE", "value": 0.5},
    }
    return base, treated, pair, report


def test_projects_observed_receipts_and_derived_court_events() -> None:
    base, treated, pair, report = fixtures()
    result = project_ocel(base, treated, pair, report)
    assert result["schema"] == OCEL_SCHEMA
    assert len(result["events"]) == 6
    # 14 = 4 fixed objects (repository_snapshot, patch, governance_case,
    # vgg_report) + 6 governance_dimension (one per DIMENSIONS member) + 4
    # evidence_receipt (one per observed probe receipt). The former pin of 11
    # predated the governance-dimension extension 3 -> 6 introduced by the
    # SWE-Prometheus VGG evidence court (#191, 6d806a49), which added the
    # structure_maintainability, reproducible_environment, and
    # dependency_security dimension objects.
    assert len(result["objects"]) == 14
    assert result["events"][-2]["time"] == "2026-09-26T04:00:03Z"
    assert result["events"][-1]["time"] == "2026-09-26T04:00:03Z"
    assert {event["type"] for event in result["events"]} == {
        "probe.execute",
        "pair.evaluate",
        "vgg.evaluate",
    }


def test_treated_probe_is_related_to_patch_and_dimension() -> None:
    base, treated, pair, report = fixtures()
    result = project_ocel(base, treated, pair, report)
    event = next(
        event
        for event in result["events"]
        if event["type"] == "probe.execute"
        and any(
            attribute["name"] == "side" and attribute["value"] == "treated"
            for attribute in event["attributes"]
        )
        and any(
            attribute["name"] == "probe_id" and attribute["value"] == "tests"
            for attribute in event["attributes"]
        )
    )
    relationships = {
        (rel["objectId"], rel["qualifier"]) for rel in event["relationships"]
    }
    assert ("sha256:patch", "under-patch") in relationships
    assert (
        "dimension:tests_ci",
        "governance-dimension",
    ) in relationships


def test_pair_and_vgg_logical_time_basis_is_explicit() -> None:
    base, treated, pair, report = fixtures()
    result = project_ocel(base, treated, pair, report)
    derived = [
        event
        for event in result["events"]
        if event["type"] in {"pair.evaluate", "vgg.evaluate"}
    ]
    for event in derived:
        assert {
            attribute["value"]
            for attribute in event["attributes"]
            if attribute["name"] == "time_basis"
        } == {"latest-input-observation"}


def test_missing_or_naive_observed_time_is_refused() -> None:
    for bad in (None, "2026-09-26T04:00:00"):
        base, treated, pair, report = fixtures()
        base["receipts"][0]["observed_at"] = bad
        with pytest.raises(
            IECRefusal,
            match="REFUSED_OCEL_WITHOUT_OBSERVED_TIME",
        ):
            project_ocel(base, treated, pair, report)


def test_report_subject_or_patch_drift_is_refused() -> None:
    base, treated, pair, report = fixtures()
    drift = copy.deepcopy(report)
    drift["subject"] = "git:other/repo@abc"
    with pytest.raises(
        IECRefusal,
        match="REFUSED_EXACT_SUBJECT_MISMATCH",
    ):
        project_ocel(base, treated, pair, drift)

    drift = copy.deepcopy(report)
    drift["patch_digest"] = "sha256:other"
    with pytest.raises(
        IECRefusal,
        match="REFUSED_EXACT_SUBJECT_MISMATCH",
    ):
        project_ocel(base, treated, pair, drift)


def test_run_identity_must_match_pair() -> None:
    base, treated, pair, report = fixtures()
    base["run_id"] = "sha256:wrong"
    with pytest.raises(
        IECRefusal,
        match="REFUSED_EXACT_SUBJECT_MISMATCH",
    ):
        project_ocel(base, treated, pair, report)


def test_projection_is_content_deterministic() -> None:
    base, treated, pair, report = fixtures()
    first = project_ocel(base, treated, pair, report)
    second = project_ocel(
        copy.deepcopy(base),
        copy.deepcopy(treated),
        copy.deepcopy(pair),
        copy.deepcopy(report),
    )
    assert first == second
    assert first["id"] == second["id"]
