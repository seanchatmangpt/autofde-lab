# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Auto-Dev HDDL Domain and State Extractor for Closed-Loop Software Engineering.

Maps software repository states (derived via pystackt / git into OCEL 2.0)
into ground world facts W and compound tasks tau for FOND x HDDL product planning.
"""

from __future__ import annotations

from autofde_lab.ocel.log import OcelLog
from autofde_lab.planning.fond_hddl_product import (
    HDDLDomain,
    Method,
    Outcome,
    PrimitiveAction,
    ProductState,
    Task,
)

__all__ = [
    "build_autodev_hddl_domain",
    "extract_initial_product_state",
]


def build_autodev_hddl_domain() -> HDDLDomain:
    """Construct the canonical Auto-Dev HDDL domain for autonomous software development.

    Tasks:
    - Compound:
      - 'deliver_feature': Root compound task for implementing and verifying a feature.
      - 'repair_defect': Root compound task for fixing an observed failure.
      - 'verify_cycle': Subtask handling test execution and receipt issuance.
    - Primitive Actions:
      - 'inspect_code': Inspect codebase / tests (pre: repo_clean; add: inspected).
      - 'write_failing_test': Write new reproduction/unit test (pre: inspected; add: test_written, test_failing).
      - 'apply_patch': Modify source code (pre: inspected; add: code_modified, delete: repo_clean).
      - 'run_tests': Nondeterministic test execution (pre: code_modified | test_written; outcomes: tests_pass, tests_fail).
      - 'commit_receipt': Issue signed execution receipt (pre: tests_pass; add: cycle_receipted).
    """
    tasks = {
        # Compound tasks
        "deliver_feature": Task(name="deliver_feature", primitive=False),
        "repair_defect": Task(name="repair_defect", primitive=False),
        "verify_cycle": Task(name="verify_cycle", primitive=False),
        # Primitive tasks
        "inspect_code": Task(name="inspect_code", primitive=True),
        "write_failing_test": Task(name="write_failing_test", primitive=True),
        "apply_patch": Task(name="apply_patch", primitive=True),
        "run_tests": Task(name="run_tests", primitive=True),
        "commit_receipt": Task(name="commit_receipt", primitive=True),
    }

    methods = {
        "deliver_feature": (
            Method(
                name="tdd_delivery",
                task="deliver_feature",
                preconditions=frozenset({"repo_clean"}),
                subtasks=(
                    "inspect_code",
                    "write_failing_test",
                    "apply_patch",
                    "verify_cycle",
                ),
            ),
        ),
        "repair_defect": (
            Method(
                name="direct_patch_repair",
                task="repair_defect",
                preconditions=frozenset({"test_failing"}),
                subtasks=(
                    "inspect_code",
                    "apply_patch",
                    "verify_cycle",
                ),
            ),
        ),
        "verify_cycle": (
            Method(
                name="test_and_receipt",
                task="verify_cycle",
                preconditions=frozenset({"code_modified"}),
                subtasks=(
                    "run_tests",
                    "commit_receipt",
                ),
            ),
        ),
    }

    actions = {
        "inspect_code": PrimitiveAction(
            name="inspect_code",
            preconditions=frozenset(),
            outcomes=frozenset({Outcome(add=frozenset({"inspected"}))}),
        ),
        "write_failing_test": PrimitiveAction(
            name="write_failing_test",
            preconditions=frozenset({"inspected"}),
            outcomes=frozenset(
                {
                    Outcome(
                        add=frozenset({"test_written", "test_failing"}),
                    )
                }
            ),
        ),
        "apply_patch": PrimitiveAction(
            name="apply_patch",
            preconditions=frozenset({"inspected"}),
            outcomes=frozenset(
                {
                    Outcome(
                        add=frozenset({"code_modified"}),
                        delete=frozenset({"repo_clean"}),
                    )
                }
            ),
        ),
        "run_tests": PrimitiveAction(
            name="run_tests",
            preconditions=frozenset({"code_modified"}),
            outcomes=frozenset(
                {
                    Outcome(
                        add=frozenset({"tests_pass"}),
                        delete=frozenset({"test_failing"}),
                    ),
                    Outcome(
                        add=frozenset({"tests_fail", "test_failing"}),
                    ),
                }
            ),
        ),
        "commit_receipt": PrimitiveAction(
            name="commit_receipt",
            preconditions=frozenset({"tests_pass"}),
            outcomes=frozenset(
                {
                    Outcome(
                        add=frozenset({"cycle_receipted", "repo_clean"}),
                        delete=frozenset({"code_modified"}),
                    )
                }
            ),
        ),
    }

    return HDDLDomain(tasks=tasks, methods=methods, actions=actions)


def extract_initial_product_state(
    ocel_log: OcelLog,
    goal_task: str = "deliver_feature",
) -> ProductState:
    """Extract initial ProductState (W, tau) from an OCEL 2.0 repository log.

    Derives initial world facts from events:
    - If recent ci_verification was failed -> 'test_failing'
    - Otherwise -> 'repo_clean'
    """
    facts: set[str] = set()

    # Inspect activities in the repository event log
    activities = [e.activity for e in ocel_log.events]
    if any("fail" in a.lower() for a in activities):
        facts.add("test_failing")
    else:
        facts.add("repo_clean")

    return ProductState(
        world=frozenset(facts),
        tau=(goal_task,),
    )
