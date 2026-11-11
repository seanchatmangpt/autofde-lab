"""Coprocessor kinds ``rl_shielded`` and ``powl`` (lane B4).

rl_shielded: PPO (hub StableBaseline) trained briefly on a seeded gymnasium
stand-dispatch environment. A symbolic applicability shield (stand free in the
observation and not in ``blocked_stands``) masks inapplicable actions at emit
time, so the emitted action sequence never double-books a stand. The same
trained policy is also run unshielded in the same call; both conflict rates are
reported in diagnostics.

powl: projects VAL-format plan lines through the in-repo POWL2 projector,
strictly decodes and validates the Turtle (autofde_lab.fabric.powl), and returns
the ordered activity lines recovered from the decoded model.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List

from autofde_lab.coprocessor.envelope import (
    Envelope,
    Result,
    Status,
    blocked,
    refused,
    register_kind,
)

MAX_TRAIN_SECONDS = 60.0
MAX_TIMESTEPS = 200_000
EVAL_EPISODES = 20


def _int(payload: Dict[str, Any], key: str, default: int) -> int:
    val = payload.get(key, default)
    if isinstance(val, bool) or not isinstance(val, int):
        raise ValueError(f"{key} must be an integer")
    return val


def _make_env_class():
    import gymnasium as gym
    import numpy as np

    class StandDispatchEnv(gym.Env):
        """One flight per step; the action picks a stand; an occupied pick conflicts."""

        def __init__(self, n_stands: int, horizon: int, seed: int):
            self.n, self.horizon = n_stands, horizon
            self.rng = random.Random(seed)
            self.observation_space = gym.spaces.Box(
                0.0, 1.0, shape=(n_stands + 1,), dtype=np.float32
            )
            self.action_space = gym.spaces.Discrete(n_stands)
            self.log: List[tuple] = []
            self.t, self.counter = 0, [0] * n_stands

        def _obs(self):
            top = max(self.n - 1, 1)
            free = next((i for i, c in enumerate(self.counter) if c == 0), 0)
            return np.array(
                [c / top for c in self.counter] + [free / top], dtype=np.float32
            )

        def reset(self, *, seed=None, options=None):
            self.t, self.counter, self.log = 0, [0] * self.n, []
            return self._obs(), {}

        def step(self, action):
            stand = int(action)
            dwell = self.rng.randint(1, max(self.n - 1, 1))
            conflict = self.counter[stand] > 0
            self.counter[stand] = max(self.counter[stand], dwell)
            self.log.append((self.t, stand, dwell, conflict))
            self.t += 1
            self.counter = [max(c - 1, 0) for c in self.counter]
            return self._obs(), (-1.0 if conflict else 1.0), self.t >= self.horizon, False, {}

    return StandDispatchEnv


def _applicable(obs, n: int, blocked_stands: frozenset) -> List[int]:
    top = max(n - 1, 1)
    return [
        s for s in range(n)
        if round(float(obs[s]) * top) == 0 and s not in blocked_stands
    ]


def _episode(env, act, shield: bool, blocked_stands: frozenset):
    obs, _ = env.reset()
    done, deferred = False, 0
    while not done:
        a = int(act(obs))
        if shield:
            ok = _applicable(obs, env.n, blocked_stands)
            if not ok:
                deferred += 1
                # Defer: book nothing this step; the occupancy clock still advances.
                env.log.append((env.t, -1, 0, False))
                env.t += 1
                env.counter = [max(c - 1, 0) for c in env.counter]
                obs, done = env._obs(), env.t >= env.horizon
                continue
            if a not in ok:
                a = ok[0]
        obs, _, done, _, _ = env.step(a)
    conflicts = sum(1 for *_, c in env.log if c)
    return conflicts, deferred


@register_kind("rl_shielded", module="kinds_rl")
def _rl_shielded(env: Envelope) -> Result:
    p, o = env.payload, env.options
    try:
        n = _int(p, "n_stands", 4)
        horizon = _int(p, "horizon", 20)
        seed = _int(p, "seed", 0)
        steps = _int(o, "timesteps", 20_000)
        budget = float(o.get("max_seconds", MAX_TRAIN_SECONDS))
        blocked_stands = frozenset(int(s) for s in p.get("blocked_stands", []))
    except (ValueError, TypeError) as exc:
        return refused(f"bad payload: {exc}", kind="rl_shielded")
    if n < 2 or horizon < 1:
        return refused("n_stands must be >= 2 and horizon >= 1", kind="rl_shielded")
    if not 1 <= steps <= MAX_TIMESTEPS or not 0 < budget <= MAX_TRAIN_SECONDS:
        return refused(
            f"timesteps must be in [1,{MAX_TIMESTEPS}] and max_seconds in (0,{MAX_TRAIN_SECONDS}]",
            kind="rl_shielded",
        )
    if any(s < 0 or s >= n for s in blocked_stands):
        return refused("blocked_stands outside [0, n_stands)", kind="rl_shielded")
    if len(blocked_stands) >= n:
        return Result(
            Status.INFEASIBLE, kind="rl_shielded", solver="applicability-shield",
            diagnostics={"reason": "every stand is blocked; no applicable action at step 0"},
        )
    try:
        from autofde_lab.hub.domain.gym import GymDomain
        from autofde_lab.hub.solver.stable_baselines import StableBaseline
        from stable_baselines3 import PPO
    except ImportError as exc:
        return blocked(exc.name or "stable_baselines3", kind="rl_shielded")

    Env = _make_env_class()
    started = time.monotonic()
    with StableBaseline(
        domain_factory=lambda: GymDomain(Env(n, horizon, seed)),
        algo_class=PPO, baselines_policy="MlpPolicy",
        learn_config={"total_timesteps": steps}, verbose=0,
    ) as solver:
        solver.solve()
        train_s = time.monotonic() - started
        if train_s > budget:
            return refused(
                f"training took {train_s:.1f}s > budget {budget}s", kind="rl_shielded"
            )

        def act(obs):
            return solver.sample_action(obs)

        eval_seed = seed + 1
        shielded_rates, unshielded_rates, deferred_total = [], [], 0
        for tag, shield in (("u", False), ("s", True)):
            e = Env(n, horizon, eval_seed)
            for _ in range(EVAL_EPISODES):
                c, d = _episode(e, act, shield, blocked_stands)
                (shielded_rates if shield else unshielded_rates).append(c)
                deferred_total += d if shield else 0
        # Emitted plan: one shielded episode on a fresh env.
        e = Env(n, horizon, seed + 2)
        c, d = _episode(e, act, True, blocked_stands)
        actions = [
            {"t": t, "stand": s, "dwell": dw} if s >= 0 else {"t": t, "stand": None, "dwell": 0}
            for t, s, dw, _ in e.log
        ]
    return Result(
        Status.PLAN, kind="rl_shielded", actions=actions, cost=float(c),
        solver="stable_baselines3.PPO+applicability-shield",
        diagnostics={
            "shielded_conflicts": c,
            "shielded_conflicts_mean": sum(shielded_rates) / len(shielded_rates),
            "unshielded_conflicts_mean": sum(unshielded_rates) / len(unshielded_rates),
            "deferred": d,
            "eval_episodes": EVAL_EPISODES,
            "train_seconds": round(train_s, 3),
        },
    )


@register_kind("powl", module="kinds_rl")
def _powl(env: Envelope) -> Result:
    plan = env.payload.get("plan")
    if not isinstance(plan, list) or not all(isinstance(x, str) for x in plan):
        return refused("payload.plan must be a list of VAL plan lines", kind="powl")
    steps = [x for x in plan if x.strip() and not x.strip().startswith(";")]
    if not steps:
        return refused("plan has no action lines", kind="powl")
    base = str(env.payload.get("base_iri", "urn:skdecide:plan"))
    try:
        from autofde_lab.fabric.powl import (
            PowlDecodeError,
            parse_powl_turtle,
            project_plan_to_powl,
            validate_powl,
        )
    except ImportError as exc:
        return blocked(exc.name or "autofde_lab.fabric.powl", kind="powl")
    try:
        turtle = project_plan_to_powl(plan, base_iri=base)
        model = validate_powl(parse_powl_turtle(turtle))
    except PowlDecodeError as exc:
        return refused(f"POWL2 decode/validation failed: {exc}", kind="powl")
    lines = []
    for child in model.ordered_children():
        leaf = model.leaves[child.child_model]
        args = [
            model.bindings[b].bound_object.rsplit("/object/", 1)[-1]
            for b in leaf.binds_parameter
        ]
        lines.append("(" + " ".join([leaf.activity_label] + args) + ")")
    return Result(
        Status.PLAN, kind="powl", actions=lines, cost=float(len(lines)),
        solver="autofde_lab.fabric.powl",
        diagnostics={"turtle_bytes": len(turtle), "base_iri": base},
    )
