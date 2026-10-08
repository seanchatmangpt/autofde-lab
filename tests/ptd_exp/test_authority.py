from autofde_lab.ptd_exp.authority import *


def test_authority():
    admit_authority(AuthorityBoundary("s", "a"), "s", {"a"})
