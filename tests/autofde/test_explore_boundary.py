# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""``skdecide.autofde`` is a leaf: nothing in the core may import it.

The dependency arrow points one way — ``autofde`` depends on
:mod:`skdecide.powl`, and ``skdecide/{powl,agent,ocel,fabric}`` must not depend
on ``autofde``. That keeps the extraction boundary real for when AutoFDE moves
to its own repository: a core module importing it would silently make the move
a breaking change.

Shape copied from ``tests/adapters/test_adapters.py``'s
``test_no_adapter_module_imports_a_sibling_at_module_level`` — module-level
imports read with :mod:`ast`, not text search.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "skdecide"
AUTOFDE = SRC / "autofde"

#: Core packages that must never depend on autofde.
CORE_PACKAGES = ("powl", "agent", "ocel", "fabric")

CORE_MODULES = sorted(
    p
    for pkg in CORE_PACKAGES
    for p in (SRC / pkg).rglob("*.py")
    if "__pycache__" not in p.parts
)


def _imported_names(tree: ast.AST) -> list[str]:
    """Every dotted name imported anywhere in the module, not only at top level."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                names.append(node.module or "")
    return names


def test_core_modules_were_actually_found():
    """Guard against a vacuous pass from a bad glob."""
    assert len(CORE_MODULES) > 10, CORE_MODULES
    assert AUTOFDE.is_dir()


def test_no_core_module_imports_autofde():
    """One property, every core module — offenders accumulated, not short-circuited.

    Collapsed from a 40-way parametrize: the falsifier is identical for every
    path, so N red items carried no more information than one red item whose
    message names *every* offending module. ``break``/first-failure would lose
    that, so the loop accumulates.
    """
    offenders: list[str] = []
    for path in CORE_MODULES:
        tree = ast.parse(path.read_text(), filename=str(path))
        bad = [n for n in _imported_names(tree) if "autofde" in n]
        if bad:
            offenders.append(f"{path.relative_to(SRC)} imports {bad}")
    assert not offenders, "core modules import autofde:\n" + "\n".join(offenders)


def test_core_modules_do_not_reach_autofde_dynamically():
    offenders = [
        str(path.relative_to(SRC))
        for path in CORE_MODULES
        if "autofde" in path.read_text()
    ]
    assert not offenders, f"core modules mention autofde: {offenders}"


def test_skdecide_top_level_init_does_not_import_autofde():
    tree = ast.parse((SRC / "__init__.py").read_text())
    assert not [n for n in _imported_names(tree) if "autofde" in n]


def test_autofde_depends_only_on_powl_within_skdecide():
    """The arrow points one way, and at exactly one core package."""
    allowed = {"skdecide.powl", "skdecide.autofde"}
    offenders: list[str] = []
    for path in sorted(AUTOFDE.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for name in _imported_names(tree):
            if name.startswith("skdecide"):
                root = ".".join(name.split(".")[:2])
                if root not in allowed:
                    offenders.append(f"{path.name} imports {name}")
    assert not offenders, offenders
