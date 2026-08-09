# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Real SHACL conformance checking for `powl.py`'s POWL v2 projection,
against `~/mfw`'s own committed shapes.

Why this exists, distinct from `powl.py::validate_powl`: `validate_powl`
hand-reimplements the constraints from `~/mfw/mfw-planner/shapes/
powl2.shacl.ttl` (3 `sh:NodeShape`s, 6 `sh:property` blocks) as Python
`if` statements. `docs/ecosystem-standing.md` names the actual defect that
caused: a pass-1 review graded S3b `ALIVE` "on vocabulary resemblance, not
on validation" -- the hand-reimplementation drifted from the real shapes
it was supposed to mirror, and nothing caught it because nothing ran the
real shapes. This module runs the real shapes, via `pyshacl` (an
independent, spec-compliant SHACL engine), against the actual committed
file -- not a second hand-written copy of it.

`pyshacl`/`rdflib` are declared only under the optional `ofmf` extra
(`pyproject.toml`), not the core package -- this module imports them
lazily, inside the function, so importing this module never hard-requires
that extra. Callers without it get a clear, named remedy, not a bare
`ImportError` traceback -- matching this repo's existing "probe honestly,
name the remedy" discipline (`adapters/base.py`'s `AdapterStatus`,
`.claude/hooks/no-hand-edit-generated.sh`).

This is deliberately NOT wired into `powl.py::parse_powl_turtle`'s
always-on decode path -- that path stays dependency-free. This is an
additional, explicit, optional conformance layer callers (chiefly
`tests/ecosystem/test_powl_roundtrip_chicago.py`) opt into.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from autofde_lab.adapters.base import resolve_home

MFW_SHAPES_PATH: Path = (
    Path(resolve_home("MFW_HOME", "~/mfw"))
    / "mfw-planner"
    / "shapes"
    / "powl2.shacl.ttl"
)


class ShaclDependencyMissing(RuntimeError):
    """`pyshacl`/`rdflib` are not importable in this environment.

    Both are declared under the `ofmf` optional extra
    (`pyproject.toml`'s `[project.optional-dependencies].ofmf`), not the
    core package -- install it with `uv sync --extra ofmf` to enable real
    SHACL conformance checking.
    """


@dataclass(frozen=True)
class ShaclConformanceResult:
    """The real, unmodified result of running `pyshacl.validate()`.

    `report_text` is `pyshacl`'s own human-readable validation report --
    quote it verbatim in any status claim about conformance, never
    paraphrase or re-derive it.
    """

    conforms: bool
    report_text: str
    violation_count: int
    shapes_path: Path


def check_shacl_conformance(
    turtle: str, *, shapes_path: Path | None = None
) -> ShaclConformanceResult:
    """Validate `turtle` (POWL v2 Turtle, as emitted by
    `powl.py::project_plan_to_powl`) against mfw's real committed SHACL
    shapes, using a real SHACL engine.

    Raises `FileNotFoundError` if the shapes file is absent (e.g. `~/mfw`
    not checked out) -- callers should catch this and skip with a named
    `BLOCKED:` reason, per this repo's existing convention, rather than
    treat a missing sibling checkout as a validation failure.

    Raises `ShaclDependencyMissing` if `pyshacl`/`rdflib` are not
    installed.
    """
    path = shapes_path if shapes_path is not None else MFW_SHAPES_PATH
    if not path.exists():
        raise FileNotFoundError(f"SHACL shapes file not found: {path}")

    try:
        import pyshacl
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ShaclDependencyMissing(
            "pyshacl/rdflib not importable; install with `uv sync --extra ofmf` "
            "to enable real SHACL conformance checking"
        ) from exc

    conforms, _results_graph, report_text = pyshacl.validate(
        turtle,
        shacl_graph=path.read_text(),
        data_graph_format="turtle",
        shacl_graph_format="turtle",
    )
    violation_count = report_text.count("Constraint Violation")
    return ShaclConformanceResult(
        conforms=bool(conforms),
        report_text=str(report_text),
        violation_count=violation_count,
        shapes_path=path,
    )
