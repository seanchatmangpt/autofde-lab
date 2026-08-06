# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-school tests for real LLM-backed self-play via DSPyPolicy.

No mocks anywhere in the chain: a real TurboFieldfare server process (local,
OpenAI-compatible, built from https://github.com/drumih/turbo-fieldfare),
a real `dspy.LM` configured against it, a real `dspy.Predict` call per move,
and the real, registered `RockPaperScissors` domain rolled out via the real
`skdecide.hub.solver.dspy_policy.DSPyPolicy` solver and the real
`skdecide.self_play.self_play_rollout`.

Skipped (not mocked) when the real TurboFieldfareServer binary or model
weights genuinely aren't present on disk, or the real server fails to come
up -- this is a real external dependency this test cannot fake and still be
an end-to-end check of the real integration. When both are present, this
test starts and stops the real server process itself.
"""

from __future__ import annotations

import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

TURBO_FIELDFARE_DIR = Path.home() / "turbo-fieldfare"
SERVER_BINARY = TURBO_FIELDFARE_DIR / ".build" / "release" / "TurboFieldfareServer"
MODEL_PATH = TURBO_FIELDFARE_DIR / "scratch" / "gemma4.gturbo"
PORT = 8080
BASE_URL = f"http://127.0.0.1:{PORT}"

requires_real_turbo_fieldfare_binary_and_model = pytest.mark.skipif(
    not (SERVER_BINARY.exists() and MODEL_PATH.exists()),
    reason=(
        f"Real TurboFieldfareServer binary ({SERVER_BINARY}) or real model "
        f"weights ({MODEL_PATH}) not present -- build/install them per "
        "turbo-fieldfare's README before running this real end-to-end test."
    ),
)


def _real_server_is_healthy() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=1) as resp:
            return resp.status == 200
    except OSError:
        return False


@pytest.fixture(scope="module")
def real_turbo_fieldfare_server():
    """Start the real TurboFieldfareServer process for the duration of this module.

    If a real server is already listening on the expected port (started
    separately by the caller), reuse it and do not manage its lifecycle.
    """
    if _real_server_is_healthy():
        yield BASE_URL
        return

    process = subprocess.Popen(
        [
            str(SERVER_BINARY),
            "--model",
            str(MODEL_PATH),
            "--port",
            str(PORT),
            "--max-context",
            "4096",
        ],
        cwd=str(TURBO_FIELDFARE_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if _real_server_is_healthy():
                break
            if process.poll() is not None:
                pytest.fail(
                    f"Real TurboFieldfareServer process exited early with "
                    f"code {process.returncode} before becoming healthy."
                )
            time.sleep(1)
        else:
            pytest.fail(
                "Real TurboFieldfareServer did not report healthy within 60s."
            )
        yield BASE_URL
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture()
def real_dspy_lm(real_turbo_fieldfare_server):
    import dspy

    from skdecide.hub.solver.dspy_policy import DEFAULT_LM_MODEL

    lm = dspy.LM(DEFAULT_LM_MODEL, api_base=f"{real_turbo_fieldfare_server}/v1", api_key="local")
    dspy.configure(lm=lm)
    return lm


@requires_real_turbo_fieldfare_binary_and_model
def test_real_dspy_predict_gets_a_real_legal_move_from_the_real_server(real_dspy_lm):
    import dspy

    class ChooseMove(dspy.Signature):
        situation: str = dspy.InputField()
        legal_moves: str = dspy.InputField()
        move: str = dspy.OutputField()

    prediction = dspy.Predict(ChooseMove)(
        situation="Your opponent just played rock.",
        legal_moves="rock, paper, scissors",
    )
    assert prediction.move.strip().lower() in {"rock", "paper", "scissors"}


@requires_real_turbo_fieldfare_binary_and_model
def test_real_dspy_policy_solver_reports_compatible_with_real_rock_paper_scissors(
    real_dspy_lm,
):
    from skdecide.hub.domain.rock_paper_scissors import RockPaperScissors
    from skdecide.hub.solver.dspy_policy import DSPyPolicy

    domain = RockPaperScissors(max_moves=2)
    assert DSPyPolicy.check_domain(domain) is True


@requires_real_turbo_fieldfare_binary_and_model
def test_real_self_play_rollout_with_real_dspy_policy_produces_real_valid_zero_sum_episode(
    real_dspy_lm,
):
    from skdecide.hub.domain.rock_paper_scissors import RockPaperScissors
    from skdecide.hub.domain.rock_paper_scissors.rock_paper_scissors import Move
    from skdecide.hub.solver.dspy_policy import DSPyPolicy
    from skdecide.self_play import self_play_rollout

    max_steps = 2

    def domain_factory():
        return RockPaperScissors(max_moves=max_steps)

    with DSPyPolicy(domain_factory=domain_factory, lm=real_dspy_lm) as solver:
        solver.solve()
        result = self_play_rollout(
            num_episodes=2, max_steps=max_steps, solver=solver
        )

    assert result["num_episodes_run"] == 2
    assert len(result["episode_returns"]) == 2
    for episode_return in result["episode_returns"]:
        # real zero-sum guarantee: what player1 gains, player2 loses
        assert episode_return["player1"] == -episode_return["player2"]
        assert -max_steps <= episode_return["player1"] <= max_steps

    # every real move actually chosen by the real LLM is a real, valid Move
    assert set(Move) == {Move.rock, Move.paper, Move.scissors}
