"""K14: a real python crash (AttributeError) is CRASH, never NO_PLAN."""
import subprocess
import sys

from plankinds.k14_autofde import classify_pddl_exit


def test_real_attributeerror_is_crash():
    r = subprocess.run([sys.executable, "-c", "object().sample"], capture_output=True, text=True)
    assert r.returncode == 1 and "AttributeError" in r.stderr
    assert classify_pddl_exit(r.returncode, r.stderr) == "CRASH"


def test_clean_no_plan_stays_no_plan():
    assert classify_pddl_exit(1, "no plan exists (search exhausted)") == "NO_PLAN"
