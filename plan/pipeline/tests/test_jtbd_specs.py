import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jtbd_specs as J  # noqa: E402
import pytest  # noqa: E402
from pm4pytest.conformance import ConformanceSpec  # noqa: E402
from pm4pytest.ocpq import OCPQ  # noqa: E402
from pm4pytest.temporal import TemporalSLA  # noqa: E402

SUPPORTED = [k for k, v in J.SPECS.items() if v["status"] == "SUPPORTED"]
UNSUPPORTED = [k for k, v in J.SPECS.items() if v["status"].startswith("UNSUPPORTED[")]


def test_registry_covers_five_and_status_vocabulary():
    assert len(J.SPECS) == 5
    assert set(SUPPORTED) | set(UNSUPPORTED) == set(J.SPECS)


@pytest.mark.parametrize("k", SUPPORTED)
def test_supported_builds_real_classes(k):
    b = J.build(k)
    assert isinstance(b["conformance"], ConformanceSpec) and b["conformance"].net
    assert b["conformance"].allowed_transitions
    assert isinstance(b["ocpq"], OCPQ) and isinstance(b["sla"], TemporalSLA)


@pytest.mark.parametrize("k", SUPPORTED)
def test_supported_activities_in_store_alphabet(k):
    alpha = J.store_alphabet()
    for path in J.build(k)["valid_paths"]:
        assert set(path) <= alpha, set(path) - alpha


@pytest.mark.parametrize("k", UNSUPPORTED)
def test_unsupported_has_reason_and_no_path(k):
    s = J.SPECS[k]
    assert s["reason"].strip() and s["status"] == f"UNSUPPORTED[{s['reason']}]"
    assert "builder" not in s and "valid_paths" not in s
    with pytest.raises(LookupError):
        J.build(k)


@pytest.mark.parametrize("k", SUPPORTED)
def test_anti_vacuity_withholding_event_breaks_conformance(k):
    b = J.build(k)
    spec, withheld = b["conformance"], J.SPECS[k]["anti_vacuity"]
    good = b["valid_paths"][0]
    t0 = datetime(2026, 10, 4, 10, 0, 0)
    ev = lambda p: [{"concept:name": a, "time:timestamp": t0 + timedelta(minutes=i)}
                    for i, a in enumerate(p)]
    assert spec.evaluate(ev(good)).success
    assert not spec.evaluate(ev([a for a in good if a != withheld])).success


def test_alphabet_is_introspected_not_empty():
    a = J.store_alphabet()
    assert {"work_order", "dispatch", "media:model_tag_photo", "ledger_settled"} <= a
    assert "recruiter_call" not in a
