from plankinds import registry, run_kind


def _rows(kind):
    return run_kind(registry()[kind])


def test_k14_autofde():
    rows = _rows("K14")
    assert rows and all(r["status"] == "SKIP" or r["ok"] for r in rows), rows
    assert len(rows) >= 5


def test_k15_gymact():
    rows = _rows("K15")
    assert rows and all(r["status"] == "SKIP" or r["ok"] for r in rows), rows
    assert len(rows) >= 5


def test_k16_llm():
    rows = _rows("K16")
    assert rows
    for r in rows:
        assert r["status"] == "SKIP" or r["ok"], r
        assert r["status"] != "UNSUPPORTED"


def test_unsupported_rows_in_matrix():
    for k in ("K14", "K15"):
        mod = registry()[k]
        assert {"SAT/SMT", "behavior trees", "executable state machine", "replanning",
                "preference planning", "fast-downward", "VAL"} <= set(mod.UNSUPPORTED_KINDS)
