# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Test-collection shim: make this worktree's ``autofde_lab.case_library``
importable even though the installed ``.venv`` is editable-linked to the
shared checkout's ``src/`` (a different path than this worktree's own
``src/``).

Extends the already-imported ``autofde_lab`` package's ``__path__`` with
this worktree's ``src/autofde_lab`` directory, so ``import
autofde_lab.case_library`` finds the module physically present here without
needing a separate ``pip install -e`` of the worktree.
"""

from __future__ import annotations

from pathlib import Path

import autofde_lab

_worktree_src = Path(__file__).resolve().parents[2] / "src" / "autofde_lab"
if str(_worktree_src) not in autofde_lab.__path__:
    autofde_lab.__path__.append(str(_worktree_src))
