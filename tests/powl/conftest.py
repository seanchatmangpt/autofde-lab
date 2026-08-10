# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Worktree-local import fixup, test-support only (no test logic here).

This repo's editable install (``_autofde_lab_editable.ScikitBuildRedirectingFinder``)
bakes an absolute ``known_source_files`` map at ``pip install -e`` time, so
``autofde_lab.powl``'s ``__path__`` is pinned to the *main checkout*'s
``src/autofde_lab/powl`` directory regardless of ``PYTHONPATH``. Running tests
from a ``git worktree`` (this session's isolation mechanism) against a module
that exists only in the worktree therefore fails to import with the main
checkout's venv. This appends the worktree's own ``src/autofde_lab/powl``
directory to the already-imported package's ``__path__`` so
``autofde_lab.powl.turtle_bridge`` resolves to *this* worktree's file, not a
copy pasted into the shared checkout.
"""

from __future__ import annotations

import pathlib

import autofde_lab.powl as _powl_pkg

_worktree_powl_dir = pathlib.Path(__file__).resolve().parent.parent.parent / "src" / "autofde_lab" / "powl"
if str(_worktree_powl_dir) not in _powl_pkg.__path__:
    _powl_pkg.__path__.append(str(_worktree_powl_dir))
