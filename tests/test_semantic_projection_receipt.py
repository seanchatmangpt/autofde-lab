from autofde_lab.semantic_projection_receipt import receipt,replay
def test_receipt_is_order_independent():
    a=receipt("owner/repo@immutable",{"b","a"})
    b=receipt("owner/repo@immutable",{"a","b"})
    assert a==b and replay("owner/repo@immutable",{"a","b"},a)
def test_semantic_change_changes_receipt():
    assert receipt("owner/repo@immutable",{"a"}) != receipt("owner/repo@immutable",{"b"})
