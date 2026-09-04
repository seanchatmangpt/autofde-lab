#!/usr/bin/env python3
"""
compare.py — WS7 Typed Prediction Comparator (stdlib only).

diff(predicted, observed, schema, prior=None) -> ComparisonResult (a plain dict)

Field-level classes (one per schema field, deterministic precedence):
  NOT_APPLICABLE       schema.fields[f].applicable_when not satisfied by observed
  UNOBSERVABLE         schema.fields[f].observable == false
  MISSING_PREDICTION   field absent from predicted (observed present or not)
  MISSING_OBSERVATION  field in predicted, absent from observed
  TYPE_ERROR           predicted or observed value violates schema.fields[f].type
  MATCH / MISMATCH     typed equality of predicted vs observed

Transition-level classes (one per schema transition + one per invariant):
  EXPECTED_TRANSITION_HAPPENED    prior[f]==from, predicted[f]==to, observed[f]==to
  EXPECTED_TRANSITION_ABSENT      prior[f]==from, predicted[f]==to, observed[f]!=to
  UNEXPECTED_TRANSITION_HAPPENED  prior[f]==from, predicted[f]!=to, observed[f]==to
  EXPECTED_INVARIANT_VIOLATED     predicted[f]==value (or prior[f]==value) and observed[f]!=value
  (transitions that neither were expected nor happened are recorded as NO_TRANSITION
   so the transition list is total over the schema; NO_TRANSITION never affects verdict)

Overall verdict:
  INVALID    any TYPE_ERROR
  REFUTED    any MISMATCH / EXPECTED_TRANSITION_ABSENT / UNEXPECTED_TRANSITION_HAPPENED /
             EXPECTED_INVARIANT_VIOLATED
  PARTIAL    no refutation but at least one MISSING_*, or an UNOBSERVABLE / NOT_APPLICABLE
             field that carried a prediction (unpredicted ones never weaken the verdict)
  CONFIRMED  everything else

Serialization: canonical(result) = json.dumps(sort_keys=True, separators=(",",":"))
over the pure-data core; digest = sha256(canonical). Both are stable across runs
and machines (no timestamps inside the core).

CLI:
  python3 compare.py <schema.json> <predicted.json> <observed.json> [<prior.json>]
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

FIELD_CLASSES = (
    "MATCH", "MISMATCH", "UNOBSERVABLE", "NOT_APPLICABLE",
    "TYPE_ERROR", "MISSING_PREDICTION", "MISSING_OBSERVATION",
)
TRANSITION_CLASSES = (
    "EXPECTED_TRANSITION_HAPPENED", "EXPECTED_TRANSITION_ABSENT",
    "UNEXPECTED_TRANSITION_HAPPENED", "EXPECTED_INVARIANT_VIOLATED",
    "NO_TRANSITION",
)
VERDICTS = ("CONFIRMED", "PARTIAL", "REFUTED", "INVALID")

_MISSING = object()


def _type_ok(value: Any, t: str) -> bool:
    if t == "boolean":
        return isinstance(value, bool)
    if t == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "string":
        return isinstance(value, str)
    raise ValueError(f"schema type {t!r} unsupported")


def _repr(value: Any) -> str:
    """Typed scalar rendered as a string so OCEL rows stay primitive."""
    if value is _MISSING:
        return "<missing>"
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def canonical(core: dict[str, Any]) -> str:
    return json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(core: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(core).encode("utf-8")).hexdigest()


def schema_digest(schema: dict[str, Any]) -> str:
    return digest(schema)


def _classify_field(name: str, spec: dict[str, Any], predicted: dict, observed: dict) -> dict[str, Any]:
    p = predicted.get(name, _MISSING)
    o = observed.get(name, _MISSING)
    row = {"field": name, "type": spec["type"], "predicted": _repr(p), "observed": _repr(o)}

    cond = spec.get("applicable_when")
    if cond is not None and any(observed.get(k, _MISSING) != v for k, v in cond.items()):
        row["class"] = "NOT_APPLICABLE"
        row["detail"] = "applicable_when " + canonical(cond) + " not met in observed"
        return row
    if not spec.get("observable", True):
        row["class"] = "UNOBSERVABLE"
        row["detail"] = "schema marks field unobservable"
        return row
    if p is _MISSING:
        row["class"] = "MISSING_PREDICTION"
        row["detail"] = "no prediction for field"
        return row
    if o is _MISSING:
        row["class"] = "MISSING_OBSERVATION"
        row["detail"] = "predicted but not observed"
        return row
    bad = []
    if not _type_ok(p, spec["type"]):
        bad.append("predicted")
    if not _type_ok(o, spec["type"]):
        bad.append("observed")
    if bad:
        row["class"] = "TYPE_ERROR"
        row["detail"] = ",".join(bad) + " not of type " + spec["type"]
        return row
    if p == o and type(p) is type(o):
        row["class"] = "MATCH"
        row["detail"] = ""
    else:
        row["class"] = "MISMATCH"
        row["detail"] = "predicted " + _repr(p) + " observed " + _repr(o)
    return row


def _classify_transitions(schema: dict, predicted: dict, observed: dict, prior: dict) -> list[dict]:
    rows: list[dict] = []
    for t in schema.get("transitions", []):
        f = t["field"]
        pr, p, o = prior.get(f, _MISSING), predicted.get(f, _MISSING), observed.get(f, _MISSING)
        armed = pr == t["from"]
        expected = armed and p == t["to"]
        happened = armed and o == t["to"]
        if expected and happened:
            cls = "EXPECTED_TRANSITION_HAPPENED"
        elif expected and not happened:
            cls = "EXPECTED_TRANSITION_ABSENT"
        elif (not expected) and happened:
            cls = "UNEXPECTED_TRANSITION_HAPPENED"
        else:
            cls = "NO_TRANSITION"
        rows.append({
            "kind": "transition", "name": t["name"], "field": f,
            "from": _repr(t["from"]), "to": _repr(t["to"]),
            "prior": _repr(pr), "predicted": _repr(p), "observed": _repr(o), "class": cls,
        })
    for inv in schema.get("invariants", []):
        f = inv["field"]
        p, o, pr = predicted.get(f, _MISSING), observed.get(f, _MISSING), prior.get(f, _MISSING)
        asserted = p == inv["value"] or (p is _MISSING and pr == inv["value"])
        violated = asserted and o is not _MISSING and o != inv["value"]
        rows.append({
            "kind": "invariant", "name": inv["name"], "field": f,
            "value": _repr(inv["value"]), "prior": _repr(pr),
            "predicted": _repr(p), "observed": _repr(o),
            "class": "EXPECTED_INVARIANT_VIOLATED" if violated else "NO_TRANSITION",
        })
    return rows


def _verdict(fields: list[dict], transitions: list[dict]) -> str:
    fc = [r["class"] for r in fields]
    tc = [r["class"] for r in transitions]
    if "TYPE_ERROR" in fc:
        return "INVALID"
    if "MISMATCH" in fc or any(c in tc for c in (
        "EXPECTED_TRANSITION_ABSENT", "UNEXPECTED_TRANSITION_HAPPENED", "EXPECTED_INVARIANT_VIOLATED")):
        return "REFUTED"
    for r in fields:
        if r["class"] in ("MISSING_PREDICTION", "MISSING_OBSERVATION"):
            return "PARTIAL"
        # UNOBSERVABLE / NOT_APPLICABLE only weaken the verdict when something was predicted there.
        if r["class"] in ("UNOBSERVABLE", "NOT_APPLICABLE") and r["predicted"] != "<missing>":
            return "PARTIAL"
    return "CONFIRMED"


def diff(predicted: dict, observed: dict, schema: dict, prior: dict | None = None) -> dict[str, Any]:
    if not isinstance(predicted, dict) or not isinstance(observed, dict):
        raise TypeError("predicted and observed must be dict world states")
    prior = prior or {}
    fields = [_classify_field(n, s, predicted, observed) for n, s in sorted(schema["fields"].items())]
    # Predicted keys outside the schema are TYPE_ERRORs: an untyped prediction is not comparable.
    for extra in sorted(set(predicted) - set(schema["fields"])):
        fields.append({"field": extra, "type": "<undeclared>", "predicted": _repr(predicted[extra]),
                       "observed": _repr(observed.get(extra, _MISSING)), "class": "TYPE_ERROR",
                       "detail": "field not declared in schema"})
    transitions = _classify_transitions(schema, predicted, observed, prior)
    counts = {c: sum(1 for r in fields if r["class"] == c) for c in FIELD_CLASSES}
    counts.update({c: sum(1 for r in transitions if r["class"] == c) for c in TRANSITION_CLASSES})
    core = {
        "schema_id": schema.get("schema_id", ""),
        "schema_digest": schema_digest(schema),
        "fields": fields,
        "transitions": transitions,
        "counts": counts,
        "verdict": _verdict(fields, transitions),
    }
    core["canonical"] = canonical({k: v for k, v in core.items()})
    core["digest"] = hashlib.sha256(core["canonical"].encode("utf-8")).hexdigest()
    return core


def to_ocel_attrs(result: dict[str, Any]) -> dict[str, Any]:
    """Typed attribute map for the PredictionCompared event type in tools/ocel_v2/emitter.py."""
    c = result["counts"]
    return {
        "verdict": result["verdict"],
        "digest": result["digest"],
        "schema_digest": result["schema_digest"],
        "n_match": c["MATCH"],
        "n_mismatch": c["MISMATCH"],
        "n_unobservable": c["UNOBSERVABLE"],
        "n_not_applicable": c["NOT_APPLICABLE"],
        "n_type_error": c["TYPE_ERROR"],
        "n_missing_prediction": c["MISSING_PREDICTION"],
        "n_missing_observation": c["MISSING_OBSERVATION"],
        "n_expected_transition_happened": c["EXPECTED_TRANSITION_HAPPENED"],
        "n_expected_transition_absent": c["EXPECTED_TRANSITION_ABSENT"],
        "n_unexpected_transition_happened": c["UNEXPECTED_TRANSITION_HAPPENED"],
        "n_expected_invariant_violated": c["EXPECTED_INVARIANT_VIOLATED"],
        "field_classes_json": result["fields"],
        "transition_classes_json": result["transitions"],
        "delta_json": {"verdict": result["verdict"], "digest": result["digest"], "counts": c},
    }


def _load(p: str) -> Any:
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main(argv: list[str]) -> int:
    if len(argv) not in (4, 5):
        print(__doc__)
        return 2
    schema, predicted, observed = _load(argv[1]), _load(argv[2]), _load(argv[3])
    prior = _load(argv[4]) if len(argv) == 5 else None
    res = diff(predicted, observed, schema, prior)
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0 if res["verdict"] in ("CONFIRMED", "PARTIAL") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
