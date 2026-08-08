# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Real GymAct-backed BlindEnvironment -- subprocess bridge to ~/gymact.

Follows the exact pattern established by
`tests/ecosystem/test_gymact_terragoat_bridge_chicago.py`: gymact's own
venv runs a small bridge script that imports gymact and drives a real
`GymAct` kernel episode; this process never imports gymact directly. The
bridge script is the ONLY thing that ever sees the provider's real
capability semantics -- what crosses the process boundary back to
autofde-lab is exactly the same two-method shape as
`level4_generator.BlindEnvironment`: action names, and
(applicable, observed_pre_facts, delta_added, delta_removed) per probe.

`episode_id` (minted by GymAct itself, per episode) is the trial's real
isolation key -- one subprocess-driven episode per trial, never shared.

Real provider API confirmed against `~/gymact/tests/test_cube_counter.py`:
`GymAct().register_provider(ProviderInstance())`, then
`gym.materialize(MaterializationIntent(provider=<provider.name>, config=...))`,
`gym.observe(episode_id).state` (a dict), `gym.act(ActuationIntent(...))`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

HOME = Path.home()
GYMACT = HOME / "gymact"
GYMACT_VENV_PYTHON = GYMACT / ".venv" / "bin" / "python"

# provider registry name -> (import path, class name)
_PROVIDERS = {
    "cube_counter": ("gymact.gyms.cube_counter", "CubeCounterProvider", "cube-counter"),
    "cube_container_counter": (
        "gymact.gyms.cube_container_counter",
        "CubeContainerCounterProvider",
        "cube-container-counter",
    ),
}

_BRIDGE_SCRIPT = '''
import asyncio
import importlib
import json
import sys


async def main(module_path: str, class_name: str, provider_name: str, config: dict, requests: list) -> dict:
    from gymact import GymAct, MaterializationIntent
    from gymact.models import ActuationIntent

    provider_cls = getattr(importlib.import_module(module_path), class_name)
    gym = GymAct()
    gym.register_provider(provider_cls())

    materialization = await gym.materialize(MaterializationIntent(provider=provider_name, config=config))
    if not materialization.accepted:
        return {"materialize_failed": True, "reason": materialization.receipt.reason}
    episode_id = materialization.episode.episode_id

    # capabilities() lives on the materialized Environment object, which
    # GymAct keeps internal to the kernel rather than returning it from
    # materialize() -- capabilities are static per provider/config (no
    # actuation happens here), so reading them off a second, disposable,
    # never-actuated Environment instance is side-effect-free and gives
    # the real binding->iri mapping without reaching into kernel internals.
    probe_provider = provider_cls()
    probe_env = await probe_provider.materialize(scenario=None, config=config)
    caps = {c.binding: c for c in probe_env.capabilities()}
    await probe_env.teardown()

    results = []
    for req in requests:
        binding = req["action"]
        cap = caps.get(binding)
        if cap is None:
            results.append({"action": binding, "applicable": False, "reason": "UNKNOWN_CAPABILITY_LOCAL"})
            continue
        before = await gym.observe(episode_id)
        before_state = dict(before.state)
        outcome = await gym.act(ActuationIntent(episode_id=episode_id, capability=cap.iri, payload=req.get("payload", {})))
        after = await gym.observe(episode_id)
        after_state = dict(after.state)
        results.append({
            "action": binding,
            "applicable": bool(outcome.accepted),
            "observed_pre_facts": sorted(f"{k}={v}" for k, v in before_state.items()),
            "delta_added": sorted(
                f"{k}={after_state[k]}" for k in after_state
                if before_state.get(k) != after_state.get(k)
            ),
            "delta_removed": sorted(
                f"{k}={before_state[k]}" for k in before_state
                if before_state.get(k) != after_state.get(k)
            ),
            "standing": outcome.standing.value if hasattr(outcome.standing, "value") else str(outcome.standing),
            "reason": outcome.receipt.reason if outcome.receipt else None,
        })

    final_state = after_state if requests else dict((await gym.observe(episode_id)).state)
    ocel_log = gym.episode_ocel_log(episode_id)
    await gym.teardown(episode_id)
    return {
        "episode_id": episode_id,
        "results": results,
        "final_observe": final_state,
        "ocel_log": ocel_log,
    }


if __name__ == "__main__":
    module_path, class_name, provider_name = sys.argv[1], sys.argv[2], sys.argv[3]
    config = json.loads(sys.argv[4])
    requests = json.loads(sys.argv[5])
    out = asyncio.run(main(module_path, class_name, provider_name, config, requests))
    print(json.dumps(out, default=str))
'''


def skip_reason() -> Optional[str]:
    if not GYMACT.is_dir():
        return f"BLOCKED:GYMACT_CHECKOUT_ABSENT: {GYMACT} does not exist"
    if not GYMACT_VENV_PYTHON.is_file():
        return f"BLOCKED:GYMACT_VENV_ABSENT: {GYMACT_VENV_PYTHON} does not exist"
    return None


class RealBlindEnvironment:
    """The only interface a discovery agent may use against a REAL provider.
    Each `try_action` round-trips one subprocess call -- one live GymAct
    episode per Trial (fresh materialize+teardown each call, kept simple
    and correct over kept-alive-across-calls; correctness over throughput
    for this first real increment). `episode_id` returned by the LAST call
    is retained for evidence purposes but each probe is its own
    materialize/act/observe/teardown round-trip against a config that
    encodes prior history via `payload`, since a fresh episode always
    starts from the provider's real initial state -- so `try_action`
    passes the FULL action history as `requests`, replaying it plus the
    new probe each time. This keeps isolation perfect (fresh state per
    call, no possibility of cross-probe contamination) at the cost of
    O(n^2) actuation calls across a full discovery run -- acceptable for
    these bounded providers and honestly documented rather than hidden."""

    def __init__(self, provider_key: str, config: dict, evidence_dir: Path) -> None:
        if provider_key not in _PROVIDERS:
            raise ValueError(f"unknown provider {provider_key!r}; known: {sorted(_PROVIDERS)}")
        self._module_path, self._class_name, self._provider_name = _PROVIDERS[provider_key]
        self._config = config
        self._evidence_dir = evidence_dir
        self._evidence_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._evidence_dir / "probes.jsonl"
        self._bridge_script = self._evidence_dir / "bridge.py"
        self._bridge_script.write_text(_BRIDGE_SCRIPT, encoding="utf-8")
        self._history: list[dict] = []
        self._last_episode_id: Optional[str] = None
        self._last_ocel: Optional[dict] = None

    def available_actions(self) -> list[str]:
        return ["increment", "decrement", "increment_by"]

    def try_action(self, action: str, payload: Optional[dict] = None) -> dict:
        req = {"action": action, "payload": payload or {}}
        requests = self._history + [req]
        result = self._call(requests)
        self._last_episode_id = result.get("episode_id")
        self._last_ocel = result.get("ocel_log")
        record = result["results"][-1]
        # Only advance history on real, applied success -- a refused probe
        # doesn't change real state, so it must not be replayed forward.
        if record.get("applicable"):
            self._history.append(req)
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def episode_ocel_log(self) -> Optional[dict]:
        return self._last_ocel

    def episode_id(self) -> Optional[str]:
        return self._last_episode_id

    def _call(self, requests: list[dict]) -> dict:
        completed = subprocess.run(
            [
                str(GYMACT_VENV_PYTHON),
                str(self._bridge_script),
                self._module_path,
                self._class_name,
                self._provider_name,
                json.dumps(self._config),
                json.dumps(requests),
            ],
            capture_output=True,
            text=True,
            cwd=str(GYMACT),
            timeout=120,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"gymact bridge subprocess failed:\nstdout={completed.stdout}\nstderr={completed.stderr}")
        return json.loads(completed.stdout.strip().splitlines()[-1])
