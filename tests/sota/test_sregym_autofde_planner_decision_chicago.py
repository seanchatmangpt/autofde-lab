# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for `clients/autofde_lab_planner/driver.py`'s pure decision functions --
the non-LLM planner registered in sregym's own `agents.yaml` as `autofde_lab_planner`, built
per this session's explicit correction ("use all the planning available" instead of defaulting
to an LLM tool-calling agent).

These exercise the real module, imported directly from the real, checked-out vendor path --
not a copy, not a mock of it. They test only the pure decision functions (no live cluster, no
MCP server, no LLM required) -- the real I/O functions (`call_kubectl`, `submit`,
`observe_all_images`, ...) require a real, live sregym deployment and are exercised by the real
end-to-end trial, not by this file.

Zero mocks. No `unittest.mock`, `Mock`, `patch`, or `monkeypatch` anywhere in this file.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SREGYM_ROOT = Path(__file__).resolve().parents[2] / "vendor" / "gyms" / "sregym"
DRIVER_PATH = SREGYM_ROOT / "clients" / "autofde_lab_planner" / "driver.py"

pytestmark = pytest.mark.skipif(
    not DRIVER_PATH.is_file(),
    reason=f"BLOCKED:SREGYM_AUTOFDE_PLANNER_DRIVER_ABSENT: {DRIVER_PATH} does not exist",
)


def _load_driver_module():
    """Imports the real driver.py module directly from its real, checked-out vendor path,
    without needing sregym's own package machinery (fastmcp/requests are real third-party
    deps available in this repo's own venv too, so the module body itself imports cleanly
    even though the pure functions below never touch those imports at call time)."""
    spec = importlib.util.spec_from_file_location("autofde_lab_planner_driver", DRIVER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # driver.py inserts sregym's own root onto sys.path at import time (for `from logger import
    # init_logger` and `from clients.harness.problem_id import resolve_problem_id`) -- real,
    # not faked, matching how sregym's own `main.py` launches this exact file as `__main__`.
    if str(SREGYM_ROOT) not in sys.path:
        sys.path.insert(0, str(SREGYM_ROOT))
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver():
    return _load_driver_module()


def test_parse_deployment_list_handles_real_kubectl_jsonpath_output(driver):
    # Real shape kubectl produces for `-o jsonpath='{.items[*].metadata.name}'`.
    assert driver.parse_deployment_list("frontend geo profile rate  reservation \n") == [
        "frontend",
        "geo",
        "profile",
        "rate",
        "reservation",
    ]
    assert driver.parse_deployment_list("") == []


def test_parse_single_value_strips_whitespace(driver):
    assert driver.parse_single_value("  ghcr.io/sregym/hotel-reservation:latest\n") == (
        "ghcr.io/sregym/hotel-reservation:latest"
    )


def test_find_mismatched_deployments_detects_only_real_divergence(driver):
    canonical = "ghcr.io/sregym/hotel-reservation:latest"
    observed = {
        "frontend": canonical,
        "geo": "yinfangchen/geo:app3",
        "rate": canonical,
        "profile": "",  # an empty/unreadable observation must never be reported as mismatched
    }
    assert driver.find_mismatched_deployments(observed, canonical) == ["geo"]


def test_parse_jaeger_services_parses_the_real_tool_output_shape(driver):
    """`mcp_server/jaeger_server.py:get_services()` returns `str(response.json()["data"])`
    -- a Python-list repr, verified against the real vendored source this session."""
    assert driver.parse_jaeger_services("['frontend', 'geo', 'profile', 'rate']") == [
        "frontend",
        "geo",
        "profile",
        "rate",
    ]
    assert driver.parse_jaeger_services("None") == []
    assert driver.parse_jaeger_services("") == []


_REAL_DEPLOYMENT_LIST = [
    "consul",
    "frontend",
    "geo",
    "jaeger",
    "memcached-profile",
    "memcached-rate",
    "memcached-reserve",
    "mongodb-geo",
    "mongodb-profile",
    "mongodb-rate",
    "mongodb-recommendation",
    "mongodb-reservation",
    "mongodb-user",
    "profile",
    "rate",
    "recommendation",
    "reservation",
    "search",
    "user",
]
_REAL_MICROSERVICE_NAMES = ["frontend", "geo", "profile", "rate", "recommendation", "reservation", "search", "user"]


def test_filter_traced_application_deployments_excludes_real_infra_sidecars(driver):
    """Regression test #1 for a real defect this session's first live trial exposed: an
    earlier version of this driver flagged (and attempted to "fix")
    consul/jaeger/memcached-*/mongodb-* deployments as mismatched, because it compared every
    real k8s Deployment's image against the app's single canonical image without first
    restricting to genuine application microservices. sregym's own independent LLM judge
    caught the same defect (D3 'Scope Precision' scored 0.67/1.00 on the real run: 'The agent
    lists many other deployments (consul, jaeger, mongodb, etc.) as being part of the
    mismatch/fault.') -- independent, convergent confirmation of the manually-diagnosed root
    cause. Real deployment list observed live this session (results/0809_0128)."""
    in_scope = driver.filter_traced_application_deployments(_REAL_DEPLOYMENT_LIST, traced_services=[])

    assert set(in_scope) == set(_REAL_MICROSERVICE_NAMES)
    for infra in ("consul", "jaeger", "memcached-profile", "mongodb-geo", "mongodb-user"):
        assert infra not in in_scope


def test_filter_traced_application_deployments_does_not_exclude_the_real_fault_when_tracing_is_incomplete(driver):
    """Regression test #2 for a second real defect this session's SECOND live trial exposed:
    an interim version of this driver used Jaeger's `get_services()` output as the sole
    ALLOW-list. Immediately after a fresh deployment, before the workload generator has
    produced enough traffic, Jaeger had only traced 1 of 8 real microservices
    (`['reservation']`, observed live this session) -- so gating on "is it traced" excluded
    `geo`, the actual injected-fault deployment, producing a false "no mismatch" diagnosis
    that missed the real fault entirely. The fix: the deny-list (known infra product
    names) is the primary signal, deterministic and available immediately; a genuinely
    traced name is only ever used to ALLOW, never to exclude."""
    incomplete_traced_services = ["reservation"]  # the real, live, incomplete signal observed

    in_scope = driver.filter_traced_application_deployments(_REAL_DEPLOYMENT_LIST, incomplete_traced_services)

    assert "geo" in in_scope
    assert set(in_scope) == set(_REAL_MICROSERVICE_NAMES)


def test_filter_traced_application_deployments_allows_a_traced_name_even_if_it_looks_like_infra(driver):
    """A deployment that has genuinely emitted traces is real, observed evidence of being
    application code and must be included even if its name happens to contain a generic
    infra-product token -- the traced signal is a real ALLOW override, not decoration."""
    in_scope = driver.filter_traced_application_deployments(["redis-cache-service"], ["redis-cache-service"])
    assert in_scope == ["redis-cache-service"]


def test_find_mismatched_deployments_reports_none_when_everything_matches(driver):
    canonical = "ghcr.io/sregym/hotel-reservation:latest"
    observed = {"frontend": canonical, "geo": canonical}
    assert driver.find_mismatched_deployments(observed, canonical) == []


def test_build_diagnosis_text_never_leaks_a_fault_injectors_hardcoded_root_cause(driver):
    """Integrity check: the diagnosis text is built ONLY from the observed_images/canonical
    values passed in -- assert the real vendor fault-injector's own hardcoded root-cause
    vocabulary (verbatim strings from misconfig_app.py's real root_cause text) is absent
    unless it happens to also appear in what was actually, mechanically observed."""
    canonical = "ghcr.io/sregym/hotel-reservation:latest"
    observed = {"geo": "yinfangchen/geo:app3"}
    text = driver.build_diagnosis_text(
        mismatched=["geo"], observed_images=observed, canonical_image=canonical, namespace="hotel-reservation"
    )
    assert "geo" in text
    assert "yinfangchen/geo:app3" in text
    assert canonical in text
    # The real fault-injector's own hardcoded root-cause prose (never read by this module)
    # must not appear -- if it did, that would mean the module somehow imported/leaked it.
    assert "crashes at runtime and drives repeated restart loops" not in text


def test_build_diagnosis_text_reports_a_clean_scan_honestly(driver):
    canonical = "ghcr.io/sregym/hotel-reservation:latest"
    text = driver.build_diagnosis_text(
        mismatched=[], observed_images={"geo": canonical}, canonical_image=canonical, namespace="hotel-reservation"
    )
    assert "No image misconfiguration detected" in text


def test_decide_mitigation_commands_builds_the_exact_real_kubectl_fix(driver):
    canonical = "ghcr.io/sregym/hotel-reservation:latest"
    commands = driver.decide_mitigation_commands(
        mismatched=["geo"],
        container_names={"geo": "hotel-reserv-geo"},
        canonical_image=canonical,
        namespace="hotel-reservation",
    )
    assert commands == [
        f"kubectl set image deployment/geo hotel-reserv-geo={canonical} -n hotel-reservation"
    ]


def test_decide_mitigation_commands_is_empty_when_nothing_is_mismatched(driver):
    assert driver.decide_mitigation_commands(
        mismatched=[], container_names={}, canonical_image="x", namespace="hotel-reservation"
    ) == []


def test_canonical_hotel_reservation_image_matches_the_apps_own_real_source_constant(driver):
    """Cross-checks against the real, checked-out `hotel_reservation.py` constant directly --
    not a duplicated/hand-copied string, avoiding this repo's own no-dual-bookkeeping trap.

    `hotel_reservation.py` transitively imports the real `kubernetes` Python client, which
    lives in sregym's OWN venv (`vendor/gyms/sregym/.venv`, confirmed this session:
    `.venv/bin/python -c "from sregym.service.apps.hotel_reservation import
    HOTEL_RESERVATION_APPLICATION_IMAGE"` -> `ghcr.io/sregym/hotel-reservation:latest`), not
    this repo's own `.venv` used for routine `just test` runs -- an environment gate
    (`UNSUPPORTED`, not incomplete work), named precisely rather than silently xfailed."""
    try:
        from sregym.service.apps.hotel_reservation import HOTEL_RESERVATION_APPLICATION_IMAGE
    except ModuleNotFoundError as e:
        pytest.skip(
            f"UNSUPPORTED:SREGYM_OWN_VENV_REQUIRED: {e} -- re-run with "
            f"{SREGYM_ROOT}/.venv/bin/python to exercise this import for real"
        )

    assert driver.canonical_hotel_reservation_image() == HOTEL_RESERVATION_APPLICATION_IMAGE


def test_agents_yaml_registers_the_new_planner_with_container_isolation_disabled():
    import yaml

    agents_yaml = SREGYM_ROOT / "agents.yaml"
    data = yaml.safe_load(agents_yaml.read_text())
    entries = {a["name"]: a for a in data["agents"]}
    assert "autofde_lab_planner" in entries
    entry = entries["autofde_lab_planner"]
    # Absolute interpreter path, not bare "python" -- a real defect this session's live
    # trial exposed: agent_launcher.py's subprocess inherits os.environ.copy() with no venv
    # activation, so bare "python" resolved to nothing (/bin/sh: python: command not found,
    # exit 127, empty result) until pinned to the real venv interpreter main.py itself runs
    # under.
    assert entry["kickoff_command"] == (
        f"{SREGYM_ROOT}/.venv/bin/python -m clients.autofde_lab_planner.driver"
    )
    assert entry["container_isolation"] is False
