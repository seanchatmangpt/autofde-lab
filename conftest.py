"""TEMPORARY verification-only shim.

This worktree's `.venv` is a symlink to `/Users/sac/autofde-lab/.venv`, whose
scikit-build editable install hardcodes absolute source paths back to
`/Users/sac/autofde-lab` (the non-worktree checkout). Left alone, running
tests "in the worktree" would silently import and exercise the ORIGINAL
repo's `autofde_lab` sources, not this worktree's -- exactly the kind of
false-positive/negative the OCEL/testing discipline in this repo forbids.

Redirect the scikit-build `ScikitBuildRedirectingFinder`'s known source-file
and search-location maps to this worktree's `src/` before any test module is
collected, so imports of `autofde_lab.*` really resolve here.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ORIGINAL_PREFIX = "/Users/sac/autofde-lab"
_WORKTREE_PREFIX = str(_HERE)

if _ORIGINAL_PREFIX != _WORKTREE_PREFIX:
    for finder in sys.meta_path:
        if type(finder).__name__ != "ScikitBuildRedirectingFinder":
            continue
        known_source_files = getattr(finder, "known_source_files", None)
        if isinstance(known_source_files, dict):
            for mod_name, path in list(known_source_files.items()):
                if isinstance(path, str) and path.startswith(_ORIGINAL_PREFIX):
                    known_source_files[mod_name] = _WORKTREE_PREFIX + path[len(_ORIGINAL_PREFIX):]
        search_locations = getattr(finder, "submodule_search_locations", None)
        if isinstance(search_locations, dict):
            for mod_name, locs in list(search_locations.items()):
                new_locs = set()
                for loc in locs:
                    if isinstance(loc, str) and loc.startswith(_ORIGINAL_PREFIX):
                        new_locs.add(_WORKTREE_PREFIX + loc[len(_ORIGINAL_PREFIX):])
                    else:
                        new_locs.add(loc)
                search_locations[mod_name] = new_locs
        # Drop any already-imported autofde_lab modules so they get
        # re-resolved against the patched maps.
        for mod_name in [m for m in sys.modules if m == "autofde_lab" or m.startswith("autofde_lab.")]:
            del sys.modules[mod_name]
