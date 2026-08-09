# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The real, current DecisionBasis point for `sregym`'s `stratus` driver, and the real
invocation it materializes to. Every field is read from or grounded in the exact vendored
source this session already exercised for real (`vendor/gyms/sregym`, `stratus` agent,
`misconfig_app_hotel_res` problem) -- see the citation on each field below.

`current_sregym_stratus_basis()` reads the real vendor config file at call time rather than
duplicating its values -- see `decision_basis.py`'s module docstring for why (no-dual-
bookkeeping). If the vendored file changes, this function's return value changes with it,
by construction, not by remembering to update a second copy.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from autofde_lab.sota.decision_basis import (
    Budget,
    DecisionBasis,
    Model,
    Planner,
    RepairPolicy,
    ToolPolicy,
    VerificationPolicy,
)

SREGYM_ROOT = Path(__file__).resolve().parents[3] / "vendor" / "gyms" / "sregym"

#: Real, exact path this session's real `stratus` driver run reads its retry/tool/step config
#: from -- cited: vendor/gyms/sregym/clients/stratus/stratus_agent/driver/driver.py:438-439,
#: `mitigation_agent_config_path = file_parent_dir.parent / "configs" /
#: "mitigation_agent_config.yaml"`, resolved relative to the driver module -- i.e. exactly
#: this path.
MITIGATION_AGENT_CONFIG_PATH = (
    SREGYM_ROOT / "clients" / "stratus" / "configs" / "mitigation_agent_config.yaml"
)

#: Real, exact final grading class for the problem this session actually ran
#: (`misconfig_app_hotel_res`) -- cited:
#: vendor/gyms/sregym/sregym/conductor/oracles/incorrect_image_mitigation.py:13-35,
#: `IncorrectImageMitigationOracle.evaluate()` -- a pure `kubectl get deployment` comparison,
#: zero LLM, zero network beyond the cluster. NOT the internal "weak oracles"
#: (`AlertOracle`/`ClusterStateOracle`, vendor/gyms/sregym/clients/stratus/stratus_agent/
#: driver/driver.py:47-49) that `RepairPolicy`'s `retry_mode="validate"` consults to decide
#: whether to keep retrying -- those inform the repair loop, they are never the final verdict.
MISCONFIG_APP_HOTEL_RES_VERIFICATION_ORACLE = "IncorrectImageMitigationOracle"


def current_sregym_stratus_basis(
    *,
    model_id: str = "openai/gemma-4-26b-a4b-it",
    api_base: str = "http://127.0.0.1:8080/v1",
    api_key_placeholder: str = "local",
    problem_id: str = "misconfig_app_hotel_res",
    wall_clock_timeout_s: int = 900,
) -> DecisionBasis:
    """The real DecisionBasis point this session's real `sregym`/`stratus` run is (or was)
    actually exercising -- D0 = (Gemma, stratus, CurrentStratusToolPolicy,
    ExistingRetryValidateMode, RealBenchmarkOracle, CurrentAgentTimeoutAndDefaultLimits).

    ``model_id``/``api_base``/``api_key_placeholder``/``problem_id``/``wall_clock_timeout_s``
    default to the exact real values this session's real `uv run main.py --agent stratus
    --model openai/gemma-4-26b-a4b-it --problem misconfig_app_hotel_res --agent-timeout 900`
    invocation used (with `AGENT_API_BASE=http://127.0.0.1:8080/v1`,
    `AGENT_API_KEY=local`) -- overridable because they are CLI-level knobs in the real
    harness, not vendor-hardcoded facts, unlike the tool/repair/step fields below which come
    from the real vendored YAML.
    """
    config = yaml.safe_load(MITIGATION_AGENT_CONFIG_PATH.read_text())

    # Real tool names, read directly off the real config's own sync_tools/async_tools lists
    # -- cited: vendor/gyms/sregym/clients/stratus/configs/mitigation_agent_config.yaml. Note
    # this tool set does NOT include a Loki/log-query tool even though sregym's mcp_server/
    # wires one up generally (mcp_server/loki_server.py) -- consistent with
    # LanggraphToolConfig (clients/stratus/configs/langgraph_tool_configs.py:6-24) also
    # omitting a loki_mcp_url field. A real, cited absence, not an oversight papered over.
    tool_names = tuple(
        tool["name"]
        for tool in (*config.get("sync_tools", []), *config.get("async_tools", []))
    )

    return DecisionBasis(
        model=Model(
            id=model_id,
            api_base=api_base,
            api_key_placeholder=api_key_placeholder,
            description=(
                "Real local TurboFieldfare/Gemma server, OpenAI-compatible, confirmed live "
                "this session (curl .../health -> {'status':'ok'}); zero paid credential."
            ),
        ),
        planner=Planner(
            name="sregym:stratus:mitigation_agent",
            description=(
                "sregym's real mitigation_agent decision loop "
                "(clients/stratus/stratus_agent/driver/driver.py); each step is one tool "
                "call, per the vendored config's own comment "
                "('# each step is defined as one tool call')."
            ),
        ),
        tool_policy=ToolPolicy(
            tool_names=tool_names,
            description=f"Real tool set read from {MITIGATION_AGENT_CONFIG_PATH}.",
        ),
        repair_policy=RepairPolicy(
            mode=str(config["retry_mode"]),
            max_attempts=int(config["max_retry_attempts"]),
            description=(
                "sregym's real retry_mode values are none/naive/validate "
                "(driver.py:490-602); 'validate' additionally rolls back and consults a "
                "real internal weak oracle (AlertOracle/ClusterStateOracle) between "
                "attempts -- that internal signal is part of THIS dimension, never the "
                "final VerificationPolicy verdict."
            ),
        ),
        verification_policy=VerificationPolicy(
            oracle_name=MISCONFIG_APP_HOTEL_RES_VERIFICATION_ORACLE,
            description=(
                "Real, final, unmodified benchmark oracle for misconfig_app_hotel_res -- "
                "pure kubectl get deployment comparison, zero LLM."
            ),
        ),
        budget=Budget(
            max_steps=int(config["max_step"]),
            max_retry_attempts=int(config["max_retry_attempts"]),
            wall_clock_timeout_s=wall_clock_timeout_s,
            llm_max_retries=5,
            description=(
                "max_steps/max_retry_attempts read from the real vendored config; "
                "wall_clock_timeout_s is this session's real --agent-timeout CLI value; "
                "llm_max_retries=5 is llm_backend/get_llm_backend.py's real "
                "LLM_QUERY_MAX_RETRIES default (os.getenv('LLM_QUERY_MAX_RETRIES', '5'))."
            ),
        ),
        extra={"problem_id": problem_id},
    )


def materialize_sregym_invocation(basis: DecisionBasis) -> tuple[list[str], dict[str, str]]:
    """The real, exact argv + env this DecisionBasis point runs as, for the `sregym`/`stratus`
    path -- the inverse of `current_sregym_stratus_basis()`: given a point in the search
    space, produce the real command that would exercise it.

    Only the fields this repo's real CLI (`sregym/main.py`) actually exposes as knobs are
    threaded through (`--model`, `--problem`, `--agent-timeout`, `AGENT_API_BASE`,
    `AGENT_API_KEY`); the tool/repair/step fields are NOT independently settable via CLI
    today (they live in the vendored YAML `basis` was read from) -- varying them for a real
    search means writing/pointing at a different real config file, which is exactly named as
    future work, not silently pretended to already exist as a CLI flag.
    """
    if basis.planner.name != "sregym:stratus:mitigation_agent":
        raise ValueError(
            f"materialize_sregym_invocation only knows the stratus planner identity; "
            f"got {basis.planner.name!r}"
        )
    argv = [
        "uv", "run", "main.py",
        "--agent", "stratus",
        "--model", basis.model.id,
        "--problem", basis.extra.get("problem_id", "misconfig_app_hotel_res"),
        "--agent-timeout", str(basis.budget.wall_clock_timeout_s),
    ]
    env: dict[str, str] = {}
    if basis.model.api_base:
        env["AGENT_API_BASE"] = basis.model.api_base
    if basis.model.api_key_placeholder:
        env["AGENT_API_KEY"] = basis.model.api_key_placeholder
    return argv, env
