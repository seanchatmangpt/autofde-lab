"""Make this worktree's src/autofde_lab/case_library importable.

The venv's `autofde_lab` package is an editable install pointing at the main
repo checkout (a separate worktree), whose meta-path finder takes priority
over ordinary `sys.path` entries -- so a plain `sys.path`/`PYTHONPATH`
insertion of this worktree's `src/` does not shadow it. Extending the
already-imported package's `__path__` to also include this worktree's
`src/autofde_lab` directory lets `autofde_lab.case_library` (which only
exists here, not yet in the main checkout) be found, without touching or
depending on any other worktree's files.
"""

from __future__ import annotations

import os

import autofde_lab

_this_worktree_src_pkg_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src",
    "autofde_lab",
)

if _this_worktree_src_pkg_dir not in autofde_lab.__path__:
    autofde_lab.__path__.append(_this_worktree_src_pkg_dir)
