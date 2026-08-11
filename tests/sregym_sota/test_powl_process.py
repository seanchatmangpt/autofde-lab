import pytest

from autofde_lab.powl.algebra import PartialOrder
from autofde_lab.sregym_sota.models import (
    MitigationProcessProposal,
    MitigationStep,
    ObservationProcessProposal,
    ObservationStep,
)
from autofde_lab.sregym_sota.powl_process import (
    ProcessAdmissionError,
    compile_mitigation_process,
    compile_observation_process,
)


def test_discrimination_compiles_to_real_powl_partial_order() -> None:
    process = ObservationProcessProposal(
        steps=[
            ObservationStep(
                id="a", surface="kubectl", tool="read", arguments={"x": 1}
            ),
            ObservationStep(
                id="b", surface="prometheus", tool="query", after=["a"]
            ),
        ]
    )
    model = compile_observation_process(process)
    assert isinstance(model, PartialOrder)
    assert len(model.children) == 2
    assert len(model.order) == 1


def test_single_read_is_still_a_valid_powl_process() -> None:
    model = compile_observation_process(
        ObservationProcessProposal(
            steps=[ObservationStep(id="a", surface="kubectl", tool="read")]
        )
    )
    assert isinstance(model, PartialOrder)
    assert len(model.children) == 2


def test_mitigation_requires_reversibility_and_verification() -> None:
    unsafe = MitigationProcessProposal(
        id="m1",
        reversible=False,
        steps=[
            MitigationStep(id="do", consequence="DO", surface="kubectl", tool="exec"),
            MitigationStep(
                id="verify",
                consequence="VERIFY",
                surface="kubectl",
                tool="exec",
                after=["do"],
            ),
        ],
    )
    with pytest.raises(ProcessAdmissionError):
        compile_mitigation_process(unsafe)


def test_reversible_mitigation_with_verify_compiles() -> None:
    process = MitigationProcessProposal(
        id="m1",
        reversible=True,
        risk=0.1,
        steps=[
            MitigationStep(id="do", consequence="DO", surface="kubectl", tool="exec"),
            MitigationStep(
                id="verify",
                consequence="VERIFY",
                surface="kubectl",
                tool="exec",
                after=["do"],
            ),
        ],
    )
    assert isinstance(compile_mitigation_process(process), PartialOrder)
