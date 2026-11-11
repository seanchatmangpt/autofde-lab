"""Chicago-style tests for scripts/stub_register.py: real files, real subprocesses."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "stub_register.py"


def run(src: Path, disp: Path, repo: Path, *flags: str, doc: Path | None = None):
    cmd = [sys.executable, str(SCRIPT), "--src-root", str(src), "--dispositions", str(disp),
           "--repo", str(repo), *flags]
    if doc:
        cmd += ["--doc", str(doc)]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def mirror(tmp_path: Path, files: dict[str, str]) -> tuple[Path, Path]:
    src = tmp_path / "src" / "autofde_lab"
    for rel, body in files.items():
        p = src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    disp = tmp_path / "disp.toml"
    disp.write_text("")
    return src, disp


def test_abstract_sites_are_not_open(tmp_path):
    src, disp = mirror(tmp_path, {"a/m.py": (
        "import abc\nfrom typing import Protocol\n"
        "class A(abc.ABC):\n    @abc.abstractmethod\n    def f(self):\n"
        "        raise NotImplementedError\n"
        "class P(Protocol):\n    def g(self) -> int: ...\n")})
    r = run(src, disp, tmp_path, "--check")
    assert r.returncode == 0, r.stdout
    assert "ABSTRACT_BY_DESIGN" in r.stdout


def test_open_kinds_detected(tmp_path):
    src, disp = mirror(tmp_path, {"a/m.py": (
        "def a():\n    raise NotImplementedError\n"
        "def b():\n    raise NotImplementedError('x')\n"
        "def c():\n    pass\n"
        "def d():  # TODO later\n    return 1\n"
        "x = 1  # PLACEHOLDER\n")})
    r = run(src, disp, tmp_path, "--check")
    assert r.returncode == 1
    for kind in ("NIE_BARE", "NIE_CALL", "EMPTY_BODY", "TODO", "STUB_WORD"):
        assert kind in r.stdout, r.stdout


def test_closed_requires_existing_test_and_blocked_requires_evidence(tmp_path):
    src, disp = mirror(tmp_path, {"a/m.py": "def c():\n    pass\n"})
    key = "autofde_lab/a/m.py::c::EMPTY_BODY"
    disp.write_text(f'["{key}"]\ndisposition = "CLOSED"\n'
                    'evidence = "tests/nope/test_missing.py::t"\nlane = "L"\n')
    r = run(src, disp, tmp_path, "--check")
    assert r.returncode == 1 and "CLOSED_TEST_MISSING" in r.stdout
    (tmp_path / "tests" / "nope").mkdir(parents=True)
    (tmp_path / "tests" / "nope" / "test_missing.py").write_text("")
    # closed means the stub is gone: the site no longer scans
    (src / "a" / "m.py").write_text("def c():\n    return 1\n")
    assert run(src, disp, tmp_path, "--check").returncode == 0
    (src / "a" / "m.py").write_text("def c():\n    pass\n")
    disp.write_text(f'["{key}"]\ndisposition = "BLOCKED"\nevidence = ""\nlane = "L"\n')
    r = run(src, disp, tmp_path, "--check")
    assert r.returncode == 1 and "BLOCKED_NO_EVIDENCE" in r.stdout
    disp.write_text(f'["{key}"]\ndisposition = "BLOCKED"\nevidence = "cmd: x"\nlane = "L"\n')
    assert run(src, disp, tmp_path, "--check").returncode == 0


def test_write_is_deterministic(tmp_path):
    src, disp = mirror(tmp_path, {"a/m.py": "def c():\n    pass\n"})
    d1, d2 = tmp_path / "1.md", tmp_path / "2.md"
    run(src, disp, tmp_path, "--write", doc=d1)
    run(src, disp, tmp_path, "--write", doc=d2)
    assert d1.read_bytes() == d2.read_bytes()
    text = d1.read_text()
    assert text.startswith("# STUB-REGISTER") and "By directory" in text
    assert all(len(line) <= 100 for line in text.splitlines()[:12])


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_shim_court_gate_refuses_unregistered_nie(tmp_path):
    """Copy a real src file, insert an unregistered NIE, gate must REFUSE; restore is exact."""
    real = next(p for p in sorted((REPO / "src" / "autofde_lab").rglob("*.py"))
                if p.stat().st_size > 0 and "NotImplementedError" not in p.read_text(
                    errors="replace"))
    rel = real.relative_to(REPO / "src" / "autofde_lab").as_posix()
    src, disp = mirror(tmp_path, {})
    copy = src / rel
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(real.read_bytes())
    base_sha = _sha(copy)
    before = run(src, disp, tmp_path, "--check")

    shim = copy.read_bytes() + b"\n\ndef _shim_court():  # SHIM-COURT\n    raise NotImplementedError\n"
    copy.write_bytes(shim)
    during = run(src, disp, tmp_path, "--check")
    assert during.returncode == 1, during.stdout
    assert "NIE_BARE" in during.stdout and "_shim_court" in during.stdout

    copy.write_bytes(real.read_bytes())
    after = run(src, disp, tmp_path, "--check")
    assert _sha(copy) == base_sha
    assert (after.returncode, after.stdout) == (before.returncode, before.stdout)
    assert "_shim_court" not in after.stdout


# ---- REGRESSED_STUB: a CLOSED key that scans as a stub again must fail the gate ----

def test_closed_key_reintroduced_is_regressed_and_restore_passes(tmp_path):
    src, disp = mirror(tmp_path, {"a/m.py": "def c():\n    return 1\n"})
    key = "autofde_lab/a/m.py::c::NIE_BARE"
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_c.py").write_text("")
    disp.write_text(f'["{key}"]\ndisposition = "CLOSED"\n'
                    'evidence = "tests/test_c.py::t"\nlane = "L"\n')
    assert run(src, disp, tmp_path, "--check").returncode == 0
    target = src / "a" / "m.py"
    clean = target.read_bytes()
    target.write_text("def c():\n    raise NotImplementedError\n")
    r = run(src, disp, tmp_path, "--check")
    assert r.returncode == 1, r.stdout
    assert f"REGRESSED_STUB {key}" in r.stdout
    target.write_bytes(clean)
    assert run(src, disp, tmp_path, "--check").returncode == 0


def test_regressed_stub_exempts_abstract_sites(tmp_path):
    src, disp = mirror(tmp_path, {"a/m.py": (
        "import abc\nclass A(abc.ABC):\n    @abc.abstractmethod\n    def f(self):\n"
        "        raise NotImplementedError\n")})
    key = "autofde_lab/a/m.py::A.f::NIE_BARE"
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_c.py").write_text("")
    disp.write_text(f'["{key}"]\ndisposition = "CLOSED"\n'
                    'evidence = "tests/test_c.py::t"\nlane = "L"\n')
    r = run(src, disp, tmp_path, "--check")
    assert r.returncode == 0, r.stdout
    assert "REGRESSED_STUB" not in r.stdout


# ---- real raise sites behind the NIE_CALL register rows ----

def _up():
    pytest.importorskip("unified_planning")
    import unified_planning.shortcuts as ups
    return ups


def test_htn_resolve_arg_raises_typed_on_unsupported_node():
    ups = _up()
    from autofde_lab.hub.domain.htn.planner import UnsupportedConstructError, _resolve_arg
    with pytest.raises(UnsupportedConstructError, match="argument expression"):
        _resolve_arg(ups.Int(3), {})


def test_htn_eval_number_raises_typed_on_unsupported_node():
    ups = _up()
    from autofde_lab.hub.domain.htn.planner import UnsupportedConstructError, _eval_number
    with pytest.raises(UnsupportedConstructError, match="numeric expression"):
        _eval_number(ups.TRUE(), {}, frozenset())


def test_htn_eval_condition_raises_typed_on_unsupported_node():
    ups = _up()
    from autofde_lab.hub.domain.htn.planner import UnsupportedConstructError, _eval_condition
    with pytest.raises(UnsupportedConstructError, match="condition node"):
        _eval_condition(ups.Plus(1, 2), {}, frozenset())


def _fluent_effect(kind, numeric):
    ups = _up()
    from unified_planning.model import Effect
    ftype = ups.IntType() if numeric else ups.BoolType()
    fl = ups.Fluent("f", ftype)
    value = ups.Int(1) if numeric else ups.TRUE()
    act = ups.InstantaneousAction("act")
    act.effects.append(Effect(fl(), value, ups.TRUE(), kind))
    return act


def test_htn_apply_effects_raises_on_unsupported_boolean_effect_kind():
    ups = _up()
    from unified_planning.model import EffectKind
    from autofde_lab.hub.domain.htn.planner import UnsupportedConstructError, _apply_effects
    act = _fluent_effect(EffectKind.INCREASE, numeric=False)
    with pytest.raises(UnsupportedConstructError, match="boolean effect kind"):
        _apply_effects(act, {}, frozenset())


def test_htn_apply_effects_raises_on_unsupported_numeric_effect_kind():
    _up()
    from unified_planning.model import EffectKind
    from autofde_lab.hub.domain.htn.planner import UnsupportedConstructError, _apply_effects
    act = _fluent_effect(EffectKind.ASSIGN, numeric=True)
    act.effects[0]._kind = "BOGUS"
    with pytest.raises(UnsupportedConstructError, match="unsupported effect kind"):
        _apply_effects(act, {}, frozenset())


def test_htn_initial_state_raises_on_unsupported_initial_value():
    ups = _up()
    from autofde_lab.hub.domain.htn.planner import (
        HTNTotalOrderPlanner, UnsupportedConstructError)

    class _Problem:  # hand-written real interface: only initial_values is read
        initial_values = {ups.Fluent("g", ups.IntType())(): ups.Plus(1, 2)}

    planner = HTNTotalOrderPlanner(_Problem())
    with pytest.raises(UnsupportedConstructError, match="initial value"):
        planner.initial_state()


def test_rllib_dummy_shape_refuses_unsupported_child_space():
    import gymnasium as gym
    from ray.rllib.utils.spaces.repeated import Repeated
    from autofde_lab.hub.solver.ray_rllib.gnn.utils.spaces import space_utils as rl_su
    rep = Repeated(gym.spaces.MultiBinary(2), max_len=3)
    with pytest.raises(rl_su.UnsupportedInputError, match="unsupported child space"):
        rl_su._add_dummy_shape_to_repeated_space(rep)
    ok = Repeated(gym.spaces.Discrete(4), max_len=3)
    rl_su._add_dummy_shape_to_repeated_space(ok)
    assert ok._shape == (3, 1)


def test_gnn_space_refuses_non_box_node_space_real_call():
    import gymnasium as gym
    from autofde_lab.hub.solver.utils.gnn import space_utils as su
    g = gym.spaces.Graph(node_space=gym.spaces.Discrete(3), edge_space=None)
    with pytest.raises(su.UnsupportedInputError, match="unsupported node space"):
        su.add_onehot_encoded_discrete_feature_to_graph_space(g, 2)


def test_obs_as_tensor_refuses_vectorized_graph_obs_and_converts_arrays():
    import gymnasium as gym
    import numpy as np
    import torch as th
    from autofde_lab.hub.solver.stable_baselines.gnn.common import utils as sb_utils
    gi = gym.spaces.GraphInstance(nodes=np.zeros((2, 1)), edges=None, edge_links=None)
    with pytest.raises(sb_utils.UnsupportedInputError, match="vectorized"):
        sb_utils.obs_as_tensor([gi, gi], th.device("cpu"))
    t = sb_utils.obs_as_tensor(np.arange(3), th.device("cpu"))
    assert t.tolist() == [0, 1, 2]
