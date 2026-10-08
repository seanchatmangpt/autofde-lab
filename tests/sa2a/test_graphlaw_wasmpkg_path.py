"""The praxis wasm package location is relocatable by environment, and the default is unchanged.

Real subprocesses (a fresh interpreter per case) so the module-level constant is evaluated
under the exact environment being tested -- no monkeypatching.
"""

import os
import subprocess
import sys
from pathlib import Path

MODULE = (
    Path(__file__).resolve().parents[2]
    / "src/autofde_lab/sa2a/admission/graphlaw_bridge.py"
)
DEFAULT = "/Users/sac/praxis/crates/praxis-graphlaw-wasm/pkg"
# Load this checkout's file by path (it is pure stdlib), so the result cannot depend on which
# copy of the package happens to be installed or hooked ahead of sys.path.
CODE = (
    "import sys, importlib.util as u;"
    f"s=u.spec_from_file_location('gb', {str(MODULE)!r});"
    "m=u.module_from_spec(s); sys.modules['gb']=m; s.loader.exec_module(m); print(m.PRAXIS_WASMPKG_DIR)"
)


def _constant(env_value):
    env = {k: v for k, v in os.environ.items() if k != "AUTOFDE_PRAXIS_WASMPKG_DIR"}
    if env_value is not None:
        env["AUTOFDE_PRAXIS_WASMPKG_DIR"] = env_value
    out = subprocess.run(
        [sys.executable, "-c", CODE],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip().splitlines()[-1]


def test_default_location_is_unchanged():
    assert _constant(None) == DEFAULT


def test_environment_relocates_the_package(tmp_path):
    assert _constant(str(tmp_path)) == str(tmp_path)
