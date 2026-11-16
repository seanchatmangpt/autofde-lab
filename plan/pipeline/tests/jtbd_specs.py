"""JTBD conformance specs as pure data builders over real pm4pytest classes.

Evidence: /Users/sac/tony.txt line numbers (see docs/JTBD.md). A JTBD whose activities the
store cannot express is UNSUPPORTED[<missing capability>] and carries no path.
"""
import ast
import inspect
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from enterprise_pipeline import store  # noqa: E402
from pm4pytest.conformance import ConformanceSpec  # noqa: E402
from pm4pytest.ocpq import OCPQ  # noqa: E402
from pm4pytest.temporal import TemporalSLA  # noqa: E402


def envelopes(path=HERE / "jtbd_envelopes.toml") -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def store_kinds() -> set:
    """Kind alphabet introspected from store.check (comparisons against `kind`) + OBSERVATIONS."""
    tree = ast.parse(inspect.getsource(store.check))
    kinds = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Compare) and isinstance(n.left, ast.Name) and n.left.id == "kind":
            for c in n.comparators:
                for s in ast.walk(c):
                    if isinstance(s, ast.Constant) and isinstance(s.value, str):
                        kinds.add(s.value)
    return kinds | set(store.OBSERVATIONS)


def store_alphabet() -> set:
    """Kinds plus `media:<type>` for every media_artifact subtype of the domain."""
    return store_kinds() | {f"media:{t}" for t in store.subtypes("media_artifact")}


def _fsm(paths):
    allowed = {}
    for p in paths:
        for a, b in zip(p, p[1:]):
            allowed.setdefault(a, [])
            if b not in allowed[a]:
                allowed[a].append(b)
    return allowed


def _compressor_paths():
    tag = "media:model_tag_photo"
    pre = ["work_order", "plan_dispatched", "dispatch", "checkin"]
    post = ["checkout", "plan_closed", "ledger_settled"]
    return [pre + ["media:before_media", tag, "media:after_media"] + post,
            pre + [tag, "media:before_media", "media:after_media"] + post]


def _compressor_builders():
    env = envelopes()["compressor_model_tag"]
    paths = _compressor_paths()
    conf = ConformanceSpec.from_fsm(paths, min_fitness=env["min_fitness"])
    conf.allowed_transitions = _fsm(paths)
    q = (OCPQ().require_activity("media:model_tag_photo")
         .require_object_type("work_order", "media_artifact")
         .traverse("work_order", "media_artifact")
         .require_cardinality("work_order", "media_artifact", env["media_min"], env["media_max"])
         .require_balanced_ratio("checkout", "media:model_tag_photo", env["model_tag_per_checkout"]))
    sla = TemporalSLA()
    for src, tgt, sec in env["sla"]:
        sla.require_max_latency(src, tgt, sec)
    return {"valid_paths": paths, "conformance": conf, "ocpq": q, "sla": sla}


def build(jtbd_id: str) -> dict:
    spec = SPECS[jtbd_id]
    if not spec["status"] == "SUPPORTED":
        raise LookupError(f"{jtbd_id} is {spec['status']}")
    return spec["builder"]()


def _unsupported(label, lines, missing, expressible, mutation):
    return {"label": label, "evidence": lines, "status": f"UNSUPPORTED[{missing}]",
            "reason": missing, "expressible_kinds": expressible, "anti_vacuity": mutation}


SPECS = {
    "J1_out_of_territory_flag": _unsupported(
        "primary out-of-territory work order flagged", [273, 274],
        "no territory-flag event or predicate: site.territory_client is stored but no store "
        "event records a flag or the sender, and no sales-rep notification kind exists",
        ["site", "client", "work_order"],
        "withhold the (absent) territory_flag event for an out-of-territory work_order"),
    "J2_reactive_hire_recruiter_call": _unsupported(
        "reactive hire -> paid -> recruiter call", [534, 537],
        "no recruiter_call event kind (provider, dispatch and ledger_settled exist, "
        "but the post-payment call is not expressible)",
        ["provider", "dispatch", "ledger_settled"],
        "withhold the (absent) recruiter_call event after ledger_settled"),
    "J3_escalation_ban_vs_site_exclusion": _unsupported(
        "escalation -> ban or site exclusion", [549, 566, 567],
        "no escalation ticket event; provider_blacklist and provider_filter(exc) exist "
        "but the escalation->ban/exclusion discrimination is not expressible",
        ["provider_blacklist", "provider_filter"],
        "withhold the (absent) escalation event preceding provider_blacklist"),
    "J4_dual_clock_margin_check": _unsupported(
        "margin check at judgment time (cost vs charge/NTE); transcript has no 'dual clock'",
        [395, 432, 442],
        "no margin predicate or event; rates and nte_cents are stored but no check "
        "compares them at decision time",
        ["client_rate", "provider_rate_approved", "proposal_quote"],
        "withhold the (absent) margin_checked event before dispatch"),
    "J5_compressor_model_tag_qa": {
        "label": "compressor work evidenced by a model-tag photo before QA closes",
        "evidence": [475, 476],
        "status": "SUPPORTED",
        "builder": _compressor_builders,
        "anti_vacuity": "media:model_tag_photo",
    },
}
