from autofde_lab.ptd_exp.falsifiers import falsifiers


def test_falsifiers():
    assert "knowledge_did_not_depreciate" in falsifiers(1, 2, True, 0.2, False)
