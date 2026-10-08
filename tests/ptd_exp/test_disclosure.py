from autofde_lab.ptd_exp.disclosure import *


def test_disclosure():
    assert (
        frontier([Disclosure("buyer", 1, 0.1), Disclosure("attacker", 0.5, 0.9)])[
            0
        ].name
        == "buyer"
    )
