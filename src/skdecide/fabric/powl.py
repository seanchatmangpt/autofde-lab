# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Project a computed plan into a POWL2 process model (Turtle).

A PDDL plan is a *sequence of selected transitions*. In the Chatman
ecosystem that sequence is not the deliverable -- the deliverable is the
process geometry the transitions become, expressed as POWL. The doctrine in
``~/mfw/docs/chatman-ecosystem/CHATMAN-EQUATION.md`` assigns the roles
explicitly: PDDL selects among admitted transitions; *"POWL manufactures
that transition as a child workflow."*

This module emits the same vocabulary and shape as the real committed
artifact ``~/mfw/runs/ticket-10/plan.powl.ttl`` -- ``powl2:Model`` /
``powl2:PartialOrder`` root, ``powl2:ChildBinding`` slots,
``powl2:ActivityLeaf`` steps with ``powl2:activityLabel`` and
``mfwp:planOrdinal``, and ``mfwp:ParameterBinding`` for each ground
argument -- so the output is comparable against, and validatable by, the
SHACL shapes already committed at ``~/mfw/mfw-planner/shapes/powl2.shacl.ttl``.

Digest honesty
--------------
mfw pins artifact identity with **blake3** (``mfwp:domainDigest
"blake3:..."``). The Python ``blake3`` package is not installed in this
environment, so :func:`blake3_digest` shells out to the real ``b3sum``
binary when present and otherwise **refuses** rather than substituting a
different algorithm behind a ``blake3:`` prefix. A sha256 labelled
``blake3:`` would be a forged identity that mfw's
``PLANNER_ENVIRONMENT_DRIFT`` check could never detect as wrong -- it would
simply mismatch, with a misleading reason.

Scope: this produces a candidate process model. It is not admitted, not
receipted, and not authorized to actuate anything.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Optional, Sequence

POWL2 = "https://truex.io/ontology/powl2#"
MFWP = "urn:mfw:powl-trace:"


class DigestUnavailable(RuntimeError):
    """Raised when a real blake3 digest cannot be computed.

    Deliberately fatal rather than falling back to another hash: a wrong
    algorithm under a ``blake3:`` label is worse than no digest.
    """


def blake3_digest(path: str) -> str:
    """Return ``blake3:<hex>`` for a file, or raise :class:`DigestUnavailable`.

    Tries the ``blake3`` Python package first, then the ``b3sum`` CLI. Never
    substitutes a different algorithm.
    """
    try:
        import blake3 as _blake3  # type: ignore

        with open(path, "rb") as handle:
            return f"blake3:{_blake3.blake3(handle.read()).hexdigest()}"
    except ImportError:
        pass

    b3sum = shutil.which("b3sum")
    if b3sum is None:
        raise DigestUnavailable(
            "neither the `blake3` Python package nor the `b3sum` binary is "
            "available; refusing to emit a digest under a `blake3:` label "
            "that was computed with a different algorithm"
        )
    result = subprocess.run(
        [b3sum, "--no-names", path],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise DigestUnavailable(
            f"b3sum failed on {path}: {result.stderr.strip()}"
        )
    return f"blake3:{result.stdout.strip()}"


def _parse_plan_line(line: str) -> tuple[str, list[str]]:
    """Split ``(name arg1 arg2)`` into ``("name", ["arg1", "arg2"])``."""
    tokens = line.strip().strip("()").split()
    if not tokens:
        return "", []
    return tokens[0], tokens[1:]


def project_plan_to_powl(
    plan_lines: Sequence[str],
    base_iri: str,
    domain_path: Optional[str] = None,
    problem_path: Optional[str] = None,
    planner_run: str = "run-skdecide",
) -> str:
    """Render a total-order POWL2 model for a plan, as Turtle.

    ``plan_lines`` are VAL-format ground action lines (``(move a l1 l2)``);
    comment lines beginning with ``;`` are ignored.
    """
    steps = [
        _parse_plan_line(line)
        for line in plan_lines
        if line.strip() and not line.strip().startswith(";")
    ]

    plan_iri = f"{base_iri}/plan"
    out: list[str] = [
        f"@prefix powl2: <{POWL2}> .",
        f"@prefix mfwp: <{MFWP}> .",
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
    ]

    root = [
        f"<{plan_iri}> a powl2:Model, powl2:PartialOrder ;",
        f"    powl2:derivedFrom <{base_iri}> ;",
    ]
    if domain_path is not None:
        root.append(f'    mfwp:domainDigest "{blake3_digest(domain_path)}" ;')
    if problem_path is not None:
        root.append(f'    mfwp:problemDigest "{blake3_digest(problem_path)}" ;')
    root.append(f'    mfwp:plannerRun "{planner_run}" ;')
    root.append('    mfwp:projection "total-order" ;')
    for index in range(len(steps)):
        root.append(f"    powl2:hasChild <{plan_iri}/binding-slot/{index}> ;")
    root.append(
        f'    mfwp:activityCount "{len(steps)}"^^xsd:integer .'
    )
    out.extend(root)
    out.append("")

    for index, (name, arguments) in enumerate(steps):
        step_iri = f"{plan_iri}/step/{index}"
        out.extend(
            [
                f"<{plan_iri}/binding-slot/{index}> a powl2:ChildBinding ;",
                f'    powl2:childIndex "{index}"^^xsd:integer ;',
                f"    powl2:childModel <{step_iri}> .",
                "",
                f"<{step_iri}> a powl2:Leaf, powl2:ActivityLeaf ;",
                f'    powl2:activityLabel "{name}" ;',
            ]
        )
        for arg_index in range(len(arguments)):
            out.append(
                f"    mfwp:bindsParameter <{step_iri}/binding/{arg_index}> ;"
            )
        out.append(f'    mfwp:planOrdinal "{index}"^^xsd:integer .')
        out.append("")

        for arg_index, argument in enumerate(arguments):
            out.extend(
                [
                    f"<{step_iri}/binding/{arg_index}> a mfwp:ParameterBinding ;",
                    f'    mfwp:bindingIndex "{arg_index}"^^xsd:integer ;',
                    f"    mfwp:parameter <{base_iri}/{name}-p{arg_index}> ;",
                    f"    mfwp:boundObject <{base_iri}/object/{argument}> .",
                    "",
                ]
            )

    return "\n".join(out)
