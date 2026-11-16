"""Dual-ledger (AR/AP) fixed-point settlement. Integer cents only; no floats.

Rounding rule (documented, tested): durations are integer minutes, rates are
integer cents/hour; cents = ceil(minutes * rate / 60), computed in integers as
(minutes * rate + 59) // 60. For whole-hour inputs this equals PDDL
(* hours rate).
"""
from .core import (  # noqa: F401
    LedgerError, MarginGuardError, NteCapError, Posting, Settlement,
    cents_for, due_timestamp, margin_bp, post_ar, post_ap, settle,
)
