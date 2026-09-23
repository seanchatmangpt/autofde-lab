# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""AFDE-2606 local closure follow-up: Law 6 ACROSS process boundaries.

``docs/jira/v26.9.16/AFDE-2606-recursive-projection-closure.md``'s "Local
closure work (this session)" section closed Law 6 ("identical admitted
input + profile produces identical projection identity") only *in-process*:
two ``solve_to_plan_file()`` calls sharing one interpreter
(``tests/fabric/test_afde_2606_projection_candidate_only_closure.py::
TestLaw6IdenticalInputProducesIdenticalProjectionIdentity``). That document
names the precise, un-ruled-out gap this file closes:

    "this closure work does *not* establish law 6 across process boundaries
    (a second, independent Python interpreter/subprocess invocation) --
    both in-process calls share one Astar solver import, one PDDL parser
    import, and one interpreter-level hash-seed, so a source of
    nondeterminism that only appears across a fresh process (e.g.
    PYTHONHASHSEED variation feeding into any unordered-collection
    iteration inside the C++ backend) is UNKNOWN, not ruled out by this
    pass."

This file runs the real ``python -m autofde_lab.fabric.pddl_engine`` CLI
entry point (the same ~/mfw ``classical`` external-engine contract
``tests/ecosystem/test_chatman_chain_chicago.py::run_engine`` drives) TWICE,
as two genuinely separate ``subprocess.run`` invocations -- fresh
interpreter each time, no shared Python object, no shared module cache,
no shared ``Astar``/PDDL-parser import -- and asserts the two real output
files are byte-identical (and, independently, hash-identical via a real
``hashlib.sha256`` digest of each file).

One of the two tests below goes further than "two subprocesses" alone:
it deliberately sets a *different* ``PYTHONHASHSEED`` per subprocess, which
is exactly the named candidate source of cross-process nondeterminism
above. A subprocess launched without an explicit ``PYTHONHASHSEED`` already
gets CPython's own per-process random hash seed by default (hash
randomization has been on by default since Python 3.3) -- so even the
"natural" two-subprocess test is not sharing a hash seed by accident.
Pinning two *different* explicit seeds makes that specific candidate
nondeterminism source a real, run falsifier rather than an accidental
non-observation.

Real collaborators throughout, per this repo's ``testing-chicago-style.md``:
a real PDDL domain/problem pair (``tests/domains/python/pddl_domains/blocks``,
the same fixture the sibling AFDE-2606 test and the ecosystem crown test
use), a real OS-level subprocess running the real
``autofde_lab.fabric.pddl_engine`` CLI entry point end to end (real
``Astar.solve()`` inside that subprocess, real ``project_plan_to_powl()``
projection inside that subprocess). No ``unittest.mock``/``Mock``/
``MagicMock``/``patch``/``monkeypatch`` anywhere in this file -- verified by
a real grep over this file as part of the session's completion evidence,
not asserted once and assumed to hold.

This file does NOT patch, modify, or otherwise touch ``fabric/pddl_engine.py``
or ``fabric/powl.py`` -- both stay exactly as committed.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PDDL_FIXTURES = REPO_ROOT / "tests" / "domains" / "python" / "pddl_domains"
BLOCKS_DOMAIN = PDDL_FIXTURES / "blocks" / "domain.pddl"
BLOCKS_PROBLEM = PDDL_FIXTURES / "blocks" / "probBLOCKS-3-0.pddl"

#: Identical to tests/ecosystem/test_chatman_chain_chicago.py's own ENGINE
#: invocation -- the real ~/mfw classical external-engine contract
#: (argv <domain> <problem> <plan-out> [<powl-out>]).
ENGINE = [sys.executable, "-m", "autofde_lab.fabric.pddl_engine"]

EXIT_PLAN_FOUND = 0


def _sha256_hexdigest(path: Path) -> str:
    """Real sha256 over the real file bytes -- an independent hash check,

    separate from (not a substitute for) the byte-identical text comparison
    the tests below also perform.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_engine_in_fresh_subprocess(
    plan_path: Path,
    powl_path: Path,
    *,
    pythonhashseed: "str | None" = None,
) -> subprocess.CompletedProcess:
    """Run the real engine CLI as one genuinely separate OS process.

    ``subprocess.run`` spawns a brand-new interpreter: no shared
    ``sys.modules``, no shared ``Astar``/PDDL-parser import, no shared
    Python-level state at all with any other call in this test file --
    only the identical on-disk domain/problem fixtures and (for the
    hash-seed test) the identical repository checkout are common between
    runs.
    """
    env = dict(os.environ)
    if pythonhashseed is not None:
        env["PYTHONHASHSEED"] = pythonhashseed
    return subprocess.run(
        ENGINE
        + [str(BLOCKS_DOMAIN), str(BLOCKS_PROBLEM), str(plan_path), str(powl_path)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        timeout=300,
    )


class TestLaw6CrossProcessDeterminism:
    """A2A-2606 Law 6, checked across a real process boundary.

    Complements (does not replace)
    ``test_afde_2606_projection_candidate_only_closure.py``'s in-process
    Law 6 test -- that test rules out a source of nondeterminism *within*
    one interpreter; this class rules out a source of nondeterminism that
    can only appear *between* interpreters.
    """

    def test_two_fresh_subprocesses_default_env_produce_byte_identical_output(
        self, tmp_path
    ):
        """Two default-environment subprocesses, same real input.

        Neither invocation pins ``PYTHONHASHSEED`` explicitly, so each gets
        CPython's own independently-randomized per-process hash seed (the
        default since Python 3.3) -- this is the most literal reading of
        "two genuinely separate Python subprocesses, fresh interpreter each
        time, no shared state."
        """
        run_a = tmp_path / "run_a"
        run_b = tmp_path / "run_b"
        run_a.mkdir()
        run_b.mkdir()

        plan_a, powl_a = run_a / "d.plan", run_a / "d.powl.ttl"
        plan_b, powl_b = run_b / "d.plan", run_b / "d.powl.ttl"

        result_a = _run_engine_in_fresh_subprocess(plan_a, powl_a)
        result_b = _run_engine_in_fresh_subprocess(plan_b, powl_b)

        assert result_a.returncode == EXIT_PLAN_FOUND, (
            f"run_a failed: exit={result_a.returncode} "
            f"stdout={result_a.stdout!r} stderr={result_a.stderr!r}"
        )
        assert result_b.returncode == EXIT_PLAN_FOUND, (
            f"run_b failed: exit={result_b.returncode} "
            f"stdout={result_b.stdout!r} stderr={result_b.stderr!r}"
        )

        plan_text_a = plan_a.read_text(encoding="utf-8")
        plan_text_b = plan_b.read_text(encoding="utf-8")
        assert plan_text_a == plan_text_b, (
            "identical real domain+problem input, run in two genuinely "
            "separate default-environment subprocesses, produced two "
            f"different plan files:\nrun_a:\n{plan_text_a}\n"
            f"run_b:\n{plan_text_b}"
        )

        powl_text_a = powl_a.read_text(encoding="utf-8")
        powl_text_b = powl_b.read_text(encoding="utf-8")
        assert powl_text_a == powl_text_b, (
            "identical real domain+problem input, run in two genuinely "
            "separate default-environment subprocesses, produced two "
            f"different POWL projections:\nrun_a:\n{powl_text_a}\n"
            f"run_b:\n{powl_text_b}"
        )

        # Hash-identical, as an independent check on top of (not a
        # substitute for) the byte-identical text comparison above.
        assert _sha256_hexdigest(plan_a) == _sha256_hexdigest(plan_b), (
            "plan files are byte-identical by text comparison but their "
            "real sha256 digests differ -- this should be unreachable and "
            "would indicate a bug in this test's own comparison, not the "
            "engine"
        )
        assert _sha256_hexdigest(powl_a) == _sha256_hexdigest(powl_b), (
            "POWL files are byte-identical by text comparison but their "
            "real sha256 digests differ -- this should be unreachable and "
            "would indicate a bug in this test's own comparison, not the "
            "engine"
        )

    def test_two_fresh_subprocesses_different_hash_seeds_produce_byte_identical_output(
        self, tmp_path
    ):
        """Deliberately mismatched PYTHONHASHSEED across the two subprocesses.

        This targets the exact candidate nondeterminism source the parent
        ticket named as ``UNKNOWN``: "PYTHONHASHSEED variation feeding into
        any unordered-collection iteration inside the C++ backend." Forcing
        two different, explicit hash seeds is a stronger falsifier than
        merely spawning two processes and hoping their default-randomized
        seeds happen to differ.
        """
        run_a = tmp_path / "run_a"
        run_b = tmp_path / "run_b"
        run_a.mkdir()
        run_b.mkdir()

        plan_a, powl_a = run_a / "d.plan", run_a / "d.powl.ttl"
        plan_b, powl_b = run_b / "d.plan", run_b / "d.powl.ttl"

        result_a = _run_engine_in_fresh_subprocess(plan_a, powl_a, pythonhashseed="0")
        result_b = _run_engine_in_fresh_subprocess(
            plan_b, powl_b, pythonhashseed="424242"
        )

        assert result_a.returncode == EXIT_PLAN_FOUND, (
            f"run_a (PYTHONHASHSEED=0) failed: exit={result_a.returncode} "
            f"stdout={result_a.stdout!r} stderr={result_a.stderr!r}"
        )
        assert result_b.returncode == EXIT_PLAN_FOUND, (
            f"run_b (PYTHONHASHSEED=424242) failed: exit={result_b.returncode} "
            f"stdout={result_b.stdout!r} stderr={result_b.stderr!r}"
        )

        plan_text_a = plan_a.read_text(encoding="utf-8")
        plan_text_b = plan_b.read_text(encoding="utf-8")
        assert plan_text_a == plan_text_b, (
            "identical real domain+problem input, run under two different "
            "explicit PYTHONHASHSEED values (0 vs 424242) in two genuinely "
            "separate subprocesses, produced two different plan files -- "
            f"projection identity depends on hash-seed ordering:\n"
            f"run_a (seed=0):\n{plan_text_a}\n"
            f"run_b (seed=424242):\n{plan_text_b}"
        )

        powl_text_a = powl_a.read_text(encoding="utf-8")
        powl_text_b = powl_b.read_text(encoding="utf-8")
        assert powl_text_a == powl_text_b, (
            "identical real domain+problem input, run under two different "
            "explicit PYTHONHASHSEED values (0 vs 424242) in two genuinely "
            "separate subprocesses, produced two different POWL "
            f"projections -- projection identity depends on hash-seed "
            f"ordering:\nrun_a (seed=0):\n{powl_text_a}\n"
            f"run_b (seed=424242):\n{powl_text_b}"
        )

        assert _sha256_hexdigest(plan_a) == _sha256_hexdigest(plan_b), (
            "plan files are byte-identical by text comparison but their "
            "real sha256 digests differ -- this should be unreachable and "
            "would indicate a bug in this test's own comparison, not the "
            "engine"
        )
        assert _sha256_hexdigest(powl_a) == _sha256_hexdigest(powl_b), (
            "POWL files are byte-identical by text comparison but their "
            "real sha256 digests differ -- this should be unreachable and "
            "would indicate a bug in this test's own comparison, not the "
            "engine"
        )
