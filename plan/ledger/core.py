from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping

MINUTES_PER_DAY = 1440


class LedgerError(ValueError):
    pass


class MarginGuardError(LedgerError):
    pass


class NteCapError(LedgerError):
    pass


def _int(name: str, v: Any, minimum: int = 0) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise LedgerError(f"{name} must be an integer, got {v!r}")
    if v < minimum:
        raise LedgerError(f"{name} must be >= {minimum}")
    return v


def cents_for(minutes: int, rate_cents_per_hour: int) -> int:
    """ceil(minutes * rate / 60) in pure integer arithmetic."""
    _int("minutes", minutes)
    _int("rate_cents_per_hour", rate_cents_per_hour)
    return (minutes * rate_cents_per_hour + 59) // 60


def due_timestamp(clock_minutes: int, terms_days: int) -> int:
    """PDDL: clock + terms_days * 1440 (minutes)."""
    return _int("clock", clock_minutes) + _int("terms_days", terms_days) * MINUTES_PER_DAY


def margin_bp(ar: int, ap: int) -> int:
    """Gross margin in basis points, floor((AR-AP)*10000/AR). AR must be > 0."""
    if ar < 0:
        raise LedgerError("AR must be non-negative")
    if ar == 0:
        return 0  # no revenue: margin defined as 0 bp (only reachable via override)
    return ((ar - ap) * 10000) // ar


@dataclass(frozen=True)
class Posting:
    txn: str
    account: str
    amount: int  # cents; debit +, credit -


def post_ar(external_minutes: int, client_rate: int, txn: str = "AR") -> tuple[int, list[Posting]]:
    """AR derives ONLY from external client duration x client labor rate."""
    amt = cents_for(external_minutes, client_rate)
    return amt, [Posting(txn, "accounts_receivable", amt), Posting(txn, "service_revenue", -amt)]


def post_ap(internal_minutes: int, provider_rate: int, txn: str = "AP") -> tuple[int, list[Posting]]:
    """AP derives ONLY from internal actual duration x provider agreed rate."""
    amt = cents_for(internal_minutes, provider_rate)
    return amt, [Posting(txn, "cost_of_services", amt), Posting(txn, "accounts_payable", -amt)]


@dataclass(frozen=True)
class Settlement:
    ar_cents: int
    ap_cents: int
    margin_cents: int
    margin_bp: int
    due_timestamp: int
    postings: tuple[Posting, ...]
    override_used: bool

    def as_dict(self) -> dict:
        return {
            "ar_cents": self.ar_cents, "ap_cents": self.ap_cents,
            "margin_cents": self.margin_cents, "margin_bp": self.margin_bp,
            "due_timestamp": self.due_timestamp, "override_used": self.override_used,
            "postings": [p.__dict__ for p in self.postings],
        }


def _valid_receipt(r: Any) -> bool:
    return isinstance(r, Mapping) and bool(r.get("id")) and bool(r.get("reason"))


def _legs(visit: Mapping[str, Any]):
    """Yield per-visit legs; a `visits` list aggregates AR/AP over every visit."""
    legs = visit.get("visits")
    if legs is None:
        return [visit]
    if not isinstance(legs, (list, tuple)) or not legs:
        raise LedgerError("visits must be a non-empty list")
    return [{**{k: visit.get(k) for k in ("client_rate_cents_per_hour", "provider_rate_cents_per_hour")}, **lg}
            for lg in legs]


def settle(visit: Mapping[str, Any]) -> Settlement:
    ar, ap, ar_p, ap_p = 0, 0, [], []
    for i, lg in enumerate(_legs(visit)):
        a, pa = post_ar(_int("external_minutes", lg.get("external_minutes")),
                        _int("client_rate_cents_per_hour", lg.get("client_rate_cents_per_hour")))
        b, pb = post_ap(_int("internal_minutes", lg.get("internal_minutes")),
                        _int("provider_rate_cents_per_hour", lg.get("provider_rate_cents_per_hour")))
        ar += a; ap += b; ar_p += pa; ap_p += pb
    due = due_timestamp(visit.get("clock_minutes"), visit.get("terms_days"))

    nte = _int("nte_limit_cents", visit.get("nte_limit_cents"))
    if ar > nte:
        co = visit.get("change_order")
        if not (isinstance(co, Mapping) and co.get("approved") is True
                and isinstance(co.get("new_nte_limit_cents"), int)
                and not isinstance(co.get("new_nte_limit_cents"), bool)
                and co["new_nte_limit_cents"] >= ar):
            raise NteCapError(f"AR {ar} exceeds NTE {nte} without approved change order")

    override = False
    if ar <= ap:
        if not _valid_receipt(visit.get("override_receipt")):
            raise MarginGuardError(f"AR {ar} <= AP {ap}: refused without override receipt")
        override = True

    postings = tuple(ar_p + ap_p)
    for txn in {p.txn for p in postings}:
        assert sum(p.amount for p in postings if p.txn == txn) == 0
    return Settlement(ar, ap, ar - ap, margin_bp(ar, ap), due, postings, override)
