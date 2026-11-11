"""L4 Chicago tests: PPDDL LLG encoding and contract of unsupported-enum branches.

Real plado tasks and real encoders; no mocks.
"""

import os

import numpy as np
import pytest

pytest.importorskip("plado")

from autofde_lab.hub.domain.plado import (  # noqa: E402
    ActionEncoding,
    PladoPddlDomain,
    PladoPPddlDomain,
    StateEncoding,
)
from autofde_lab.hub.domain.plado.llg_encoder import (  # noqa: E402
    EdgeLabel,
    IndexFunctionType,
    LLGEncoder,
)

HERE = os.path.dirname(os.path.abspath(__file__))
TIRE = (
    f"{HERE}/pddl_domains/tireworld/domain.pddl",
    f"{HERE}/pddl_domains/tireworld/p01.pddl",
)
BLOCKS = (
    f"{HERE}/pddl_domains/blocks/domain.pddl",
    f"{HERE}/pddl_domains/blocks/probBLOCKS-3-0.pddl",
)

KWARGS = [
    dict(encode_actions=True, simplify_encoding=False),
    dict(encode_actions=False, simplify_encoding=True),
]


def _tire_domain(**kw):
    return PladoPPddlDomain(
        domain_path=TIRE[0],
        problem_path=TIRE[1],
        state_encoding=StateEncoding.GYM_GRAPH_LLG,
        action_encoding=ActionEncoding.GYM_MULTIDISCRETE,
        llg_encoder_kwargs=kw,
    )


@pytest.mark.parametrize("kw", KWARGS)
def test_ppddl_llg_encodes_and_decodes_state(kw):
    d = _tire_domain(**kw)
    s = d.reset()
    plado_state = d._translate_state_to_plado(s)
    assert len(plado_state.atoms[0]) > 0 or any(len(a) for a in plado_state.atoms)
    # re-encode the decoded state: round trip is stable
    again = d._llg_encoder.encode(plado_state)
    assert np.array_equal(again.nodes, s.nodes)
    assert np.array_equal(again.edge_links, s.edge_links)


@pytest.mark.parametrize("kw", KWARGS)
def test_ppddl_llg_step_returns_decodable_graph(kw):
    d = _tire_domain(**kw)
    d.reset()
    a = d.get_applicable_actions().sample()
    o = d.step(a)
    assert d._translate_state_to_plado(o.observation) is not None


def _effect_edges(encoder):
    return sum(1 for lab in encoder._edge_labels if lab == EdgeLabel.EFFECT)


def test_ppddl_action_subgraph_encodes_all_outcome_effects():
    """Probabilistic move-car has 2 outcomes; every outcome's effect edges are present."""
    full = _tire_domain(encode_actions=True, simplify_encoding=False)._llg_encoder
    state_only = _tire_domain(
        encode_actions=False, simplify_encoding=False
    )._llg_encoder
    assert _effect_edges(state_only) == 0
    # move-car (3 + 2 atomic effects over both outcomes), loadtire add, loadtire del,
    # changetire (del + add) = 9 atomic effects, each an undirected edge stored twice
    assert _effect_edges(full) >= 2 * 9


def test_conditional_effects_still_refused(tmp_path):
    """Contract: conditional effects remain outside the encoder's hypotheses."""
    dom = tmp_path / "domain.pddl"
    prob = tmp_path / "problem.pddl"
    dom.write_text(
        "(define (domain cond) (:requirements :strips :conditional-effects)"
        " (:predicates (p) (q) (r))"
        " (:action a :parameters () :precondition (p)"
        "  :effect (when (q) (r))))"
    )
    prob.write_text(
        "(define (problem c1) (:domain cond) (:init (p) (q)) (:goal (r)))"
    )
    task = PladoPddlDomain(domain_path=str(dom), problem_path=str(prob)).task
    with pytest.raises(AssertionError, match="conditional effects"):
        LLGEncoder(task=task, encode_actions=True, simplify_encoding=False)


def test_unsupported_index_function_raises_not_implemented():
    """Contract: only ONEHOT is implemented; RANDSPHERE is a typed NotImplementedError."""
    enc = LLGEncoder(task=PladoPddlDomain(domain_path=BLOCKS[0], problem_path=BLOCKS[1]).task)
    enc.index_function_type = IndexFunctionType.RANDSPHERE
    with pytest.raises(NotImplementedError):
        enc.index_function(0)
    with pytest.raises(NotImplementedError):
        enc.index_function_inverse(np.zeros((enc.index_function_dim,)))
