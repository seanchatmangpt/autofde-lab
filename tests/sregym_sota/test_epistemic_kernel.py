from autofde_lab.sregym_sota.epistemic import (
    EpistemicRoute,
    compute_hypothesis_records,
    discrimination_frontier,
    route_epistemic_state,
)
from autofde_lab.sregym_sota.models import EvidenceLinkProposal, HypothesisProposal


def _h(i: int) -> HypothesisProposal:
    return HypothesisProposal(
        id=f"H{i}",
        claim=f"cause {i}",
        mechanism=f"mechanism {i}",
        predictions=[f"prediction {i}"],
        falsifiers=[f"falsifier {i}"],
    )


def _support(i: int) -> EvidenceLinkProposal:
    return EvidenceLinkProposal(
        hypothesis_id=f"H{i}", fact_id=f"fact:{i}", relation="SUPPORTS"
    )


def _refute(i: int) -> EvidenceLinkProposal:
    return EvidenceLinkProposal(
        hypothesis_id=f"H{i}", fact_id=f"fact:r{i}", relation="REFUTES"
    )


def _admitted(*links: EvidenceLinkProposal) -> set[str]:
    return {link.fact_id for link in links}


def test_exactly_one_supported_and_no_unknown_is_terminal() -> None:
    links = [_support(1), _refute(2)]
    records = compute_hypothesis_records([_h(1), _h(2)], links, _admitted(*links))
    assert route_epistemic_state(records) is EpistemicRoute.DIAGNOSIS_READY


def test_four_supported_is_not_terminal_and_all_are_on_discrimination_frontier() -> None:
    hypotheses = [_h(i) for i in range(1, 5)]
    links = [_support(i) for i in range(1, 5)]
    records = compute_hypothesis_records(hypotheses, links, _admitted(*links))
    assert route_epistemic_state(records) is EpistemicRoute.DISCRIMINATE
    assert [h.id for h in discrimination_frontier(records)] == ["H1", "H2", "H3", "H4"]


def test_unknown_survivor_forces_discrimination() -> None:
    links = [_support(1)]
    records = compute_hypothesis_records([_h(1), _h(2)], links, _admitted(*links))
    assert route_epistemic_state(records) is EpistemicRoute.DISCRIMINATE


def test_all_refuted_forces_rehypothesis_instead_of_fake_diagnosis() -> None:
    links = [_refute(1), _refute(2)]
    records = compute_hypothesis_records([_h(1), _h(2)], links, _admitted(*links))
    assert route_epistemic_state(records) is EpistemicRoute.REHYPOTHESIZE


def test_conflicting_evidence_is_unknown_not_supported() -> None:
    links = [_support(1), _refute(1)]
    records = compute_hypothesis_records([_h(1)], links, _admitted(*links))
    assert records[0].state == "UNKNOWN"
    assert route_epistemic_state(records) is EpistemicRoute.DISCRIMINATE


def test_fabricated_fact_id_is_epistemically_inert() -> None:
    fabricated = _support(1)
    records = compute_hypothesis_records([_h(1)], [fabricated], set())
    assert records[0].state == "UNKNOWN"
    assert records[0].supporting_fact_ids == []
    assert route_epistemic_state(records) is EpistemicRoute.DISCRIMINATE


def test_real_admitted_fact_id_can_support() -> None:
    real = _support(1)
    records = compute_hypothesis_records([_h(1)], [real], {real.fact_id})
    assert records[0].state == "SUPPORTED"
    assert records[0].supporting_fact_ids == [real.fact_id]
    assert route_epistemic_state(records) is EpistemicRoute.DIAGNOSIS_READY
