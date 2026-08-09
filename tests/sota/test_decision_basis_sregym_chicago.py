# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for the sregym/stratus DecisionBasis extraction (Lane B).

Every collaborator is real: `current_sregym_stratus_basis()` reads the REAL, checked-out
vendor config file at `vendor/gyms/sregym/clients/stratus/configs/mitigation_agent_config.yaml`
(no mock, no fixture copy) and `materialize_sregym_invocation()` is asserted against the exact
real command line this session actually ran for the `misconfig_app_hotel_res` problem via the
`stratus` driver, backed by the real local TurboFieldfare/Gemma server. No `unittest.mock`,
`Mock`, `patch`, or `monkeypatch` anywhere in this file.

If the vendored file is absent (submodule not checked out), tests report a named skip rather
than substituting a fake -- the same discipline `level4_gymact_bridge.py`'s `skip_reason()`
uses for the sibling `gymact` checkout.
"""

from __future__ import annotations

import pytest

from autofde_lab.sota.decision_basis import DecisionBasis
from autofde_lab.sota.materialize_sregym import (
    MITIGATION_AGENT_CONFIG_PATH,
    current_sregym_stratus_basis,
    materialize_sregym_invocation,
)

pytestmark = pytest.mark.skipif(
    not MITIGATION_AGENT_CONFIG_PATH.is_file(),
    reason=(
        f"BLOCKED:SREGYM_CHECKOUT_ABSENT: {MITIGATION_AGENT_CONFIG_PATH} does not exist "
        "-- vendor/gyms/sregym submodule not checked out"
    ),
)


def test_current_sregym_stratus_basis_reads_the_real_vendor_config() -> None:
    basis = current_sregym_stratus_basis()
    assert isinstance(basis, DecisionBasis)

    # Real values read straight from the real, checked-out YAML -- not a hardcoded guess.
    # If the vendor bumps these, this test's failure IS the correct signal that D0 drifted.
    assert basis.repair_policy.mode == "validate"
    assert basis.repair_policy.max_attempts == 10
    assert basis.budget.max_steps == 20
    assert basis.budget.max_retry_attempts == 10

    # Real tool set, read off the real config's sync_tools/async_tools lists.
    assert basis.tool_policy.tool_names == (
        "wait_tool",
        "get_traces",
        "get_services",
        "get_operations",
        "get_dependency_graph",
        "get_metrics",
        "exec_kubectl_cmd_safely",
        "f_submit_tool",
    )

    assert basis.planner.name == "sregym:stratus:mitigation_agent"
    assert basis.verification_policy.oracle_name == "IncorrectImageMitigationOracle"


def test_basis_carries_no_real_credential() -> None:
    """`Model.api_key_placeholder` must never be an ambient secret -- only a placeholder or an
    env-var NAME, per this dimension's own docstring contract."""
    basis = current_sregym_stratus_basis()
    assert basis.model.api_key_placeholder == "local"
    # A real credential would never be a bare lowercase word matching no real provider's key
    # format (OpenAI/Anthropic keys are long, prefixed, high-entropy strings) -- this is a
    # structural, not merely observational, check that the placeholder convention holds.
    assert len(basis.model.api_key_placeholder) < 20
    assert basis.model.api_key_placeholder.islower()


def test_materialize_matches_the_real_command_this_session_actually_ran() -> None:
    """The load-bearing assertion: D0's materializer must reproduce, byte-for-byte, the real
    argv/env this session's real, live `uv run main.py` invocation used for the
    `misconfig_app_hotel_res` problem -- confirmed live via a real
    `current_sregym_stratus_basis()` + `materialize_sregym_invocation()` call against the real
    vendored config, cross-checked against the actual shell command executed this session:

        env -u ANTHROPIC_API_KEY -u ZAI_API_KEY \\
          AGENT_API_BASE="http://127.0.0.1:8080/v1" AGENT_API_KEY="local" \\
          uv run main.py --agent stratus --model openai/gemma-4-26b-a4b-it \\
          --problem misconfig_app_hotel_res --agent-timeout 900

    This is the round-trip proof that the abstraction is faithful to current behavior, not an
    invented one: today's hardcoded invocation is D0, exactly.
    """
    basis = current_sregym_stratus_basis()
    argv, env = materialize_sregym_invocation(basis)

    assert argv == [
        "uv", "run", "main.py",
        "--agent", "stratus",
        "--model", "openai/gemma-4-26b-a4b-it",
        "--problem", "misconfig_app_hotel_res",
        "--agent-timeout", "900",
    ]
    assert env == {
        "AGENT_API_BASE": "http://127.0.0.1:8080/v1",
        "AGENT_API_KEY": "local",
    }


def test_materialize_refuses_an_unknown_planner_identity() -> None:
    """A DecisionBasis point whose planner isn't the real stratus identity must be refused,
    never silently materialized against the wrong vendor -- the same "typed refusal over a
    confident wrong plan" discipline this repo already applies to PDDL requirements
    (CLAUDE.md rule 3) and to `predict_step_postconditions`'s unsupported-provider guard."""
    from dataclasses import replace

    basis = current_sregym_stratus_basis()
    wrong = replace(basis, planner=replace(basis.planner, name="harbor:terminus-2"))
    with pytest.raises(ValueError, match="stratus planner identity"):
        materialize_sregym_invocation(wrong)


def test_override_knobs_are_real_cli_level_overrides_not_vendor_config_edits() -> None:
    """model_id/api_base/problem_id/wall_clock_timeout_s are real CLI-level knobs
    (`sregym/main.py`'s own `--model`/`--problem`/`--agent-timeout` flags) -- overriding them
    here does NOT edit the vendored YAML, and the tool/repair/step fields (which DO come from
    that YAML) stay fixed regardless."""
    basis = current_sregym_stratus_basis(
        model_id="openai/a-different-model",
        problem_id="a_different_problem",
        wall_clock_timeout_s=60,
    )
    argv, _ = materialize_sregym_invocation(basis)
    assert "openai/a-different-model" in argv
    assert "a_different_problem" in argv
    assert "60" in argv
    # Vendor-config-sourced fields are untouched by a CLI-level override.
    assert basis.repair_policy.mode == "validate"
    assert basis.budget.max_steps == 20
