import pytest

from autofde_lab.powl.algebra import PartialOrder
from autofde_lab.sregym_sota.models import (
    MitigationProcessProposal,
    MitigationStep,
    ObservationProcessProposal,
    ObservationStep,
)
from autofde_lab.sregym_sota.powl_process import (
    McpActivityDriver,
    ProcessAdmissionError,
    compile_mitigation_process,
    compile_observation_process,
    kubectl_command_is_read_only,
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


@pytest.mark.parametrize(
    "command",
    [
        "kubectl get pods -A -o json",
        "kubectl logs pod-a -n ns",
        "kubectl auth can-i patch deployments -n ns",
        "kubectl rollout status deployment/app -n ns",
        "kubectl api-resources -o wide",
    ],
)
def test_kubectl_observation_classifier_admits_only_read_semantics(command: str) -> None:
    assert kubectl_command_is_read_only(command)


@pytest.mark.parametrize(
    "command",
    [
        "kubectl patch deployment app -p {}",
        "kubectl delete pod app-1",
        "kubectl annotate pod app-1 x=y",
        "kubectl exec app-1 -- rm -rf /tmp/x",
        "kubectl scale deployment app --replicas=0",
    ],
)
def test_kubectl_mutations_cannot_be_relabelled_as_reads(command: str) -> None:
    assert not kubectl_command_is_read_only(command)
    driver = McpActivityDriver(
        broker=object(),
        allowed_capabilities={("kubectl", "exec_kubectl_cmd_safely")},
        allow_do=True,
    )
    assert (
        driver._authority_refusal(
            surface="kubectl",
            tool="exec_kubectl_cmd_safely",
            arguments={"cmd": command},
            consequence="READ",
        )
        == "MUTATION_MISLABELED_AS_OBSERVATION"
    )


def test_submit_mcp_is_reserved_from_llm_manufactured_processes() -> None:
    driver = McpActivityDriver(
        broker=object(),
        allowed_capabilities={("submit", "submit")},
        allow_do=True,
    )
    assert (
        driver._authority_refusal(
            surface="submit",
            tool="submit",
            arguments={"ans": "anything"},
            consequence="DO",
        )
        == "CONTROL_SURFACE_RESERVED"
    )
