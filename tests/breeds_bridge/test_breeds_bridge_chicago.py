"""Chicago-style test for the wasm4pm-cognition breeds_bridge.

Real collaborator only: this test invokes the real, locally-built
`abductive_ibe` example binary from the sibling `wasm4pm` checkout via a
real subprocess and asserts on its real stdout/parsed fields. No
unittest.mock, Mock, MagicMock, patch, or monkeypatch is used anywhere in
this module.

The binary is only available on machines with a built wasm4pm checkout, so
this test degrades to a real, named pytest.mark.skipif when it is absent —
the same pattern this repo already uses for the TurboFieldfare local-model
server (see .claude/rules/testing-chicago-style.md).

Module is imported by file path (importlib), not via the `autofde_lab`
package import machinery: this worktree is git-isolated from the main
`autofde-lab` checkout, and the scikit-build-core editable install redirects
`autofde_lab.*` package imports to the main checkout's `src/` regardless of
sys.path/PYTHONPATH order (it controls the parent package's __path__
directly). Loading by file path exercises the exact same source this test
lives beside, without depending on that redirect having been re-synced.
Once this branch is merged into the main checkout, plain
`from autofde_lab.breeds_bridge import ...` imports will work normally.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "autofde_lab" / "breeds_bridge" / "__init__.py"
)
_spec = importlib.util.spec_from_file_location("autofde_lab_breeds_bridge_under_test", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
breeds_bridge = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = breeds_bridge
_spec.loader.exec_module(breeds_bridge)


pytestmark = pytest.mark.skipif(
    not breeds_bridge.binary_available(),
    reason=(
        "wasm4pm-cognition abductive_ibe example binary not built at "
        f"{breeds_bridge.ABDUCTIVE_IBE_BINARY} — build it with: "
        "cd ~/wasm4pm && cargo build --release --example abductive_ibe -p wasm4pm-cognition"
    ),
)


def test_binary_available_matches_real_filesystem_state():
    # This assertion is trivially true given the skipif above fired or not,
    # but it pins the real, observable filesystem fact the skip decision is
    # based on rather than trusting the decision silently.
    assert breeds_bridge.ABDUCTIVE_IBE_BINARY.is_file()


def test_run_abductive_ibe_real_invocation_returns_real_parsed_output():
    result = breeds_bridge.run_abductive_ibe()

    # Real process really ran and emitted a real BLAKE3 hash prefix — this
    # is the breed's own commitment to its output, not something this test
    # fabricates.
    assert len(result.output_hash_prefix) == 16
    int(result.output_hash_prefix, 16)  # real hex digest, decodable

    # The example's hardcoded scenario is a differential-diagnosis IBE
    # problem with three hypotheses; the breed's real dispatch pipeline
    # produced an explanation string describing its ECHO coherence result.
    assert "ECHO" in result.explanation or "coherence" in result.explanation.lower()
    assert result.raw_stdout.startswith("abductive_ibe ok")


def test_run_abductive_ibe_missing_binary_raises_named_error(tmp_path):
    missing = tmp_path / "does_not_exist_abductive_ibe"
    with pytest.raises(breeds_bridge.BreedBridgeError, match="not found"):
        breeds_bridge.run_abductive_ibe(binary_path=missing)
