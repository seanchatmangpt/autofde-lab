"""G3 Chicago tests: typed UnsupportedEncodingError on unsupported plado encodings.

Real plado domains and encoders; invalid enum values are injected as plain attributes.
"""

import os

import pytest

pytest.importorskip("plado")

from autofde_lab.hub.domain.plado import (  # noqa: E402
    PladoPddlDomain,
    PladoTransformedObservablePddlDomain,
)
from autofde_lab.hub.domain.plado.llg_encoder import (  # noqa: E402
    Constant,
    BinaryOperation,
    LLGEncoder,
    NodeLabel,
    EdgeLabel,
    UnsupportedEncodingError,
)

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCKS = (
    f"{HERE}/pddl_domains/blocks/domain.pddl",
    f"{HERE}/pddl_domains/blocks/probBLOCKS-3-0.pddl",
)


def _dom():
    return PladoPddlDomain(domain_path=BLOCKS[0], problem_path=BLOCKS[1])


def _enc():
    return LLGEncoder(task=_dom().task)


def test_error_is_typed_and_a_not_implemented_error():
    e = UnsupportedEncodingError("state encoding", "x")
    assert isinstance(e, NotImplementedError)
    assert e.what == "state encoding" and e.value == "x"
    assert "state encoding" in str(e) and "'x'" in str(e)


@pytest.mark.parametrize(
    "method,attr,args",
    [
        ("_init_state_encoding", "state_encoding", ()),
        ("_translate_state_from_plado", "state_encoding", ("S",)),
        ("_translate_state_to_plado", "state_encoding", ("S",)),
        ("_transform_state_to_hashable", "state_encoding", ("S",)),
        ("_get_observation_space_", "state_encoding", ()),
        ("_init_action_encoding", "action_encoding", ()),
        ("_translate_action_from_plado", "action_encoding", ("A",)),
        ("_translate_action_to_plado", "action_encoding", ("A",)),
        ("_get_action_space_", "action_encoding", ()),
        ("get_action_components_node_flag_indices", "state_encoding", ()),
    ],
)
def test_base_domain_unsupported_encoding(method, attr, args):
    d = _dom()
    setattr(d, attr, "bogus")
    if method == "get_action_components_node_flag_indices":
        d.action_encoding = "bogus"
        d.state_encoding = "bogus"
    with pytest.raises(UnsupportedEncodingError) as ei:
        getattr(d, method)(*args)
    assert "bogus" in str(ei.value)


def test_transformed_observable_unsupported_obs_encoding():
    d = PladoTransformedObservablePddlDomain(
        domain_path=BLOCKS[0], problem_path=BLOCKS[1]
    )
    d.obs_encoding = "bogus"
    for call in (
        d._init_obs_encoding,
        d._get_observation_space_,
        lambda: d._get_observation(None),
    ):
        with pytest.raises(UnsupportedEncodingError):
            call()


def test_llg_index_function_unsupported_type():
    enc = _enc()
    enc.index_function_type = "bogus"
    with pytest.raises(UnsupportedEncodingError):
        enc.index_function(0)
    with pytest.raises(UnsupportedEncodingError):
        enc.index_function_inverse(None)


class _Power(BinaryOperation):
    OP = "^"


def _numeric(enc, expr):
    return enc._encode_numeric_expression(
        expr=expr, edge_label=EdgeLabel.PRE, variable_nodes=[], grounded=True
    )


def test_llg_unsupported_numeric_binary_operator_and_expression():
    enc = _enc()
    with pytest.raises(UnsupportedEncodingError, match="_Power"):
        _numeric(enc, _Power(Constant(1.0), Constant(2.0)))
    with pytest.raises(UnsupportedEncodingError, match="object"):
        _numeric(enc, object())


def test_llg_unsupported_atomic_effect_type():
    class _Odd(LLGEncoder):
        def _iter_atomic_outcomes(self, effect):
            class _Item:
                effect = object()

                class condition:
                    negated_atoms = atoms = constraints = ()

            yield _Item()

    with pytest.raises(UnsupportedEncodingError, match="object"):
        _Odd(task=_dom().task, encode_actions=True, simplify_encoding=False)


def test_supported_numeric_constant_still_encodes():
    enc = _enc()
    node = _numeric(enc, Constant(3.0))
    assert enc._map_node2value[node] == 3.0
    assert NodeLabel.PLUS is not None
