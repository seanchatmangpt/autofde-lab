"""K7: exact settlement ledger (python3 -m ledger settle). settlement=PLAN, typed refusal=REFUSED."""
from __future__ import annotations

import json
import sys
import subprocess
from pathlib import Path

from . import Case, Outcome
from .k01_aries import draw_world

KIND = "K7"
TITLE = "exact ledger settle"
ROOT = Path(__file__).resolve().parents[3]

SPECS = [
    ("ok", "PLAN", None),
    ("nte_cap", "REFUSED", "NteCapError"),
    ("margin_guard", "REFUSED", "MarginGuardError"),
    ("override_receipt_accepted", "PLAN", None),
    ("change_order_accepted", "PLAN", None),
]


def probe():
    return None


def cases():
    return [Case(i, e, {"refusal": r}) for i, e, r in SPECS]


def build_input(case_id: str) -> dict:
    w = draw_world(case_id)
    mins, cr, pr = w["quoted"], w["cli_rate"], w["prov_rate"]
    ar = (mins * cr + 59) // 60
    inp = {"clock_minutes": 0, "terms_days": w["terms"], "external_minutes": mins,
           "internal_minutes": mins, "client_rate_cents_per_hour": cr,
           "provider_rate_cents_per_hour": pr, "nte_limit_cents": ar * 5}
    if case_id == "nte_cap":
        inp["nte_limit_cents"] = ar - 1
    elif case_id in ("margin_guard", "override_receipt_accepted"):
        inp["provider_rate_cents_per_hour"] = cr
        if case_id == "override_receipt_accepted":
            inp["override_receipt"] = {"id": w["con"], "reason": w["lic"]}
    elif case_id == "change_order_accepted":
        inp["nte_limit_cents"] = ar - 1
        inp["change_order"] = {"approved": True, "new_nte_limit_cents": ar}
    return inp


def run(case) -> Outcome:
    inp = build_input(case.id)
    r = subprocess.run([sys.executable, "-m", "ledger", "settle"], input=json.dumps(inp), cwd=ROOT,
                       capture_output=True, text=True, timeout=60)
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return Outcome("UNSUPPORTED", f"rc={r.returncode} unparseable: {r.stdout!r} {r.stderr!r}")
    if r.returncode == 0:
        return Outcome("PLAN", f"rc=0 ar={d['ar_cents']} ap={d['ap_cents']} override={d['override_used']}")
    return Outcome("REFUSED", f"rc={r.returncode} {d.get('refused')}")
