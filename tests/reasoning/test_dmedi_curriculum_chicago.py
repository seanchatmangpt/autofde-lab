"""Real Chicago-style tests for the DMEDI curriculum module directory.

No mocks: every module is really imported, every PLANNED stub is really
called to confirm it really raises NotImplementedError, every IMPLEMENTED
pointer is really checked against the real function it re-exports.
"""

from __future__ import annotations

import importlib

import pytest

from autofde_lab.reasoning.dmedi_curriculum import DMEDI_CURRICULUM, implemented_count, module_count


def test_module_count_matches_real_curriculum_dict():
    assert module_count() == 51
    assert sum(len(v) for v in DMEDI_CURRICULUM.values()) == 51


def test_implemented_count_matches_real_status_values():
    real_implemented = [
        (phase, topic, name)
        for phase, topics in DMEDI_CURRICULUM.items()
        for topic, name, status in topics
        if status == "IMPLEMENTED"
    ]
    assert implemented_count() == len(real_implemented) == 3


def test_every_module_file_really_imports_and_exposes_real_standing():
    """Real import of all 51 modules -- not a subset, not a sample."""
    for phase, topics in DMEDI_CURRICULUM.items():
        for topic, module_name, status in topics:
            mod = importlib.import_module(f"autofde_lab.reasoning.dmedi_curriculum.{module_name}")
            assert mod.MODULE_STANDING == status
            assert mod.DMEDI_PHASE == phase
            assert mod.CURRICULUM_TOPIC == topic


def test_every_planned_module_really_refuses_via_not_implemented_error():
    """Real call to every PLANNED module's plan_* function -- confirms none
    of the 48 stubs silently returns a fabricated result."""
    planned = [
        (module_name, f"plan_{module_name}")
        for topics in DMEDI_CURRICULUM.values()
        for _topic, module_name, status in topics
        if status == "PLANNED"
    ]
    assert len(planned) == 48
    for module_name, func_name in planned:
        mod = importlib.import_module(f"autofde_lab.reasoning.dmedi_curriculum.{module_name}")
        fn = getattr(mod, func_name)
        with pytest.raises(NotImplementedError):
            fn()


def test_triz_pointer_really_re_exports_the_real_laboratory_function():
    from autofde_lab.reasoning.dmedi_curriculum import triz_new_product_design
    from autofde_lab.reasoning.laboratory import classify_triz_contradiction

    assert triz_new_product_design.classify_triz_contradiction is classify_triz_contradiction


def test_doe_pointer_really_re_exports_the_real_laboratory_function():
    from autofde_lab.reasoning.dmedi_curriculum import intro_to_doe
    from autofde_lab.reasoning.laboratory import generate_doe_candidates

    assert intro_to_doe.generate_doe_candidates is generate_doe_candidates
