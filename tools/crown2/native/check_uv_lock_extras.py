#!/usr/bin/env python3
"""Falsifier: every [project.optional-dependencies] extra in pyproject.toml must
appear in uv.lock's `provides-extras`, and no extra may name an unlocked package.

Why: plain `uv sync --extra=all` re-resolves the universal lock; an extra added
to pyproject after uv.lock was written (here `ocpq` -> unpublished `wasm4pm`,
commit b4b22be2 vs lock d2bb7039) makes the whole resolution unsatisfiable
even though `all` never includes that extra. `uv sync --extra=all --frozen`
sidesteps it. This script turns that diagnosis into an exit code so the next
bootstrap does not need to rediscover it.

Exit 0: no drift. Exit 1: drift, with the exact extras/packages named.
stdlib only (tomllib, py>=3.11).
"""
from __future__ import annotations

import os
import re
import sys
import tomllib

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def main() -> int:
    with open(os.path.join(REPO, "pyproject.toml"), "rb") as f:
        extras = tomllib.load(f)["project"].get("optional-dependencies", {})
    with open(os.path.join(REPO, "uv.lock"), "rb") as f:
        lock = tomllib.load(f)
    root = next(p for p in lock["package"] if p.get("source", {}).get("editable") == ".")
    provided = set(root.get("metadata", {}).get("provides-extras", []))
    locked_names = {p["name"] for p in lock["package"]}

    drift: list[str] = []
    for extra, reqs in extras.items():
        if extra not in provided:
            drift.append(f"extra {extra!r} is in pyproject but not in uv.lock provides-extras")
        for req in reqs:
            name = re.split(r"[\[<>=!~; ]", req.strip(), maxsplit=1)[0].lower().replace("_", "-")
            if name == "autofde-lab":
                continue
            if name not in locked_names:
                drift.append(f"extra {extra!r} requires {name!r} which is not in uv.lock")
    if drift:
        print("DRIFT (plain `uv sync --extra=all` will fail to resolve; use --frozen):")
        for d in drift:
            print("  - " + d)
        return 1
    print(f"OK: {len(extras)} extras all locked in uv.lock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
