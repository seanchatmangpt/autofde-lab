# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ALOOP portfolio metrics calculator (mission lane 6, ALOOP-ZCODE-DOGFOOD-001).

Consumes OCEL 2.0 episode logs in either serialization and computes the
ALOOP metric set over a portfolio of logs plus a mutant corpus:

    HIR  post-epoch human causal interventions per episode      (invariant 0)
    ALD  longest consecutive autonomous loop depth
    LCR  objectives autonomously closed / admitted receipts
    RR   injected failures correctly recovered|replanned|refused
    UAR  unreceipted actuations                                  (invariant 0)
    PSR  provider-loss episodes completed without human help
    CRR  crash-window reconciliation success rate
    RPR  cold replay success rate (same bytes -> same sealed verdict)
    MKR  autonomy mutants killed / executed                      (invariant 1)
    DCR  duplicate consequence-key rate                          (invariant 0)
    OCR  orphan consequence rate (no producer or no consumer)    (invariant 0)
    PDR  provider-dependent semantic divergence rate             (invariant 0)

Per-episode HIR/ALD/LCR/RR/UAR/PSR and the duplicate/orphan *receipt* counts
come from the ALOOP-001 court (:mod:`autofde_lab.aloop.court`); this module
aggregates them and adds the crash-window, consequence, replay, mutation-kill
and provider-divergence passes. It never re-judges autonomy: the court's
verdict is the only classification, and every rate here is derived from the
same admitted log bytes the court consumed.

Serializations accepted by :func:`load_document`:

* OCEL 2.0 JSON document (what the court reads);
* OCEL 2.0 NDJSON (``.ndjson``/``.jsonl``), one record per line -- either a
  whole document per line, or ``{"kind": "object", "object": ...}`` /
  ``{"kind": "event", "event": ...}`` records, or bare event records
  (``{"id", "type", "time", "relationships", ...}``). This is the emission
  format other ALOOP lanes use; object/event type vocabularies are filled
  from the ALOOP profile when the stream does not carry them.
"""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from autofde_lab.aloop.court import (
    EXIT_QUALIFIED,
    _sha256,
    evaluate_document,
    load_profile,
)

#: causal qualifiers whose target is *caused by* the source event
_CAUSAL = ("input", "cause")
#: acts that never count as machine recovery
_HUMAN_ACT = "human.intervene"
#: ratio metrics that carry a Wilson 95% interval in the scoreboard
_RATIO_METRICS = ("HIR", "LCR", "RR", "UAR", "PSR", "CRR", "RPR", "MKR", "DCR", "OCR", "PDR")

Z95 = 1.959963984540054


# ── ingestion ───────────────────────────────────────────────────────────────


def _record(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line:
        return None
    rec = json.loads(line)
    if not isinstance(rec, dict):
        raise ValueError(f"ndjson record is not an object: {line[:80]!r}")
    return rec


def _merge_line(doc: dict[str, Any], rec: Mapping[str, Any]) -> None:
    kind = rec.get("kind")
    if kind == "object" or (kind is None and "object" in rec and "event" not in rec):
        doc["objects"].append(dict(rec["object"]))
    elif kind == "event" or (kind is None and "event" in rec):
        doc["events"].append(dict(rec["event"]))
    elif "events" in rec or "objects" in rec:
        doc["objects"].extend(rec.get("objects", []))
        doc["events"].extend(rec.get("events", []))
    elif "time" in rec:
        doc["events"].append(dict(rec))
    else:
        doc["objects"].append(dict(rec))


def load_document(path: Path | str) -> tuple[dict[str, Any], str, bytes]:
    """Load ``path`` as an OCEL 2.0 document.

    Returns ``(document, format, raw_bytes)`` where format is
    ``"ocel2-json"`` or ``"ocel2-ndjson"``. The raw bytes are the exact log
    identity: every downstream digest is taken over them, never over a
    re-serialization.
    """
    path = Path(path)
    raw = path.read_bytes()
    profile = load_profile()
    suffix = path.suffix.lower()
    if suffix in (".ndjson", ".jsonl"):
        doc: dict[str, Any] = {"objects": [], "events": []}
        for line in raw.decode("utf-8").splitlines():
            rec = _record(line)
            if rec is not None:
                _merge_line(doc, rec)
        # OCEL 2.0 wants type *objects*; fill from the profile vocabulary
        doc["objectTypes"] = doc.get("objectTypes") or [
            {"name": t, "attributes": []} for t in profile["objectTypes"]
        ]
        doc["eventTypes"] = doc.get("eventTypes") or [
            {"name": t, "attributes": []} for t in profile["eventTypes"]
        ]
        return doc, "ocel2-ndjson", raw
    document = json.loads(raw)
    return document, "ocel2-json", raw


def to_ndjson(document: Mapping[str, Any]) -> bytes:
    """Serialize an OCEL 2.0 document as ALOOP NDJSON (objects, then events)."""
    out: list[str] = []
    for obj in document.get("objects", []):
        out.append(json.dumps({"kind": "object", "object": obj}, sort_keys=True))
    for ev in document.get("events", []):
        out.append(json.dumps({"kind": "event", "event": ev}, sort_keys=True))
    return ("\n".join(out) + "\n").encode("utf-8")


# ── Wilson interval ─────────────────────────────────────────────────────────


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    """Wilson score interval at level ``z`` for ``k`` successes in ``n`` trials."""
    if n <= 0:
        return None
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = p + z2 / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return (max(0.0, (centre - margin) / denom), min(1.0, (centre + margin) / denom))


def _ratio(num: int, den: int) -> float | None:
    return None if den == 0 else num / den


# ── graph-lite passes (crash windows, consequence orphans) ──────────────────


def _human_events(doc: Mapping[str, Any]) -> set[str]:
    """Events caused by, or actuated by, a Human (never machine recovery)."""
    otype = {o["id"]: o.get("type", "") for o in doc.get("objects", [])}
    human: set[str] = set()
    for ev in doc.get("events", []):
        if ev.get("type") == _HUMAN_ACT:
            human.add(ev["id"])
            continue
        for rel in ev.get("relationships", []):
            if rel.get("qualifier") == "originAuthority" and otype.get(rel.get("objectId")) == "Human":
                human.add(ev["id"])
                break
    return human


def _causal_reach(doc: Mapping[str, Any], start_event: str) -> set[str]:
    """Event ids reachable from ``start_event`` over event-object causal edges.

    Causality in the ALOOP profile runs through objects: ``e1 --output--> o
    <--input/cause-- e2`` means e1 causes e2 even when no direct event edge
    exists. Both node kinds are therefore walked.
    """
    actuations = set(load_profile()["actuations"])
    adj: dict[str, set[str]] = {}
    for ev in doc.get("events", []):
        eid = f"e:{ev['id']}"
        for rel in ev.get("relationships", []):
            q, oid = rel.get("qualifier"), rel.get("objectId")
            if not oid:
                continue
            if q == "output" or (q == "consequence" and ev.get("type") in actuations):
                adj.setdefault(eid, set()).add(f"o:{oid}")
            elif q in _CAUSAL:
                adj.setdefault(f"o:{oid}", set()).add(eid)
    seen: set[str] = set()
    stack = [f"e:{start_event}"]
    while stack:
        for nxt in adj.get(stack.pop(), ()):  # deterministic enough for set membership
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return {node.split(":", 1)[1] for node in seen if node.startswith("e:")}


def crash_reconciliation(doc: Mapping[str, Any], recovery_acts: Iterable[str]) -> tuple[int, int]:
    """Count ``execution.crash`` windows and machine-reconciled ones.

    A crash window is reconciled when some non-human event reachable from the
    crash over causal edges is a recovery activity (reconcile / replan /
    provider.replace / goal.blocked per the ALOOP profile).
    """
    recovery = set(recovery_acts)
    human = _human_events(doc)
    acts = {ev["id"]: ev.get("type", "") for ev in doc.get("events", [])}
    crashes = [e for e, a in acts.items() if a == "execution.crash"]
    reconciled = 0
    for c in crashes:
        if any(acts[d] in recovery for d in _causal_reach(doc, c) if d not in human):
            reconciled += 1
    return reconciled, len(crashes)


def consequence_orphans(doc: Mapping[str, Any], actuation_acts: Iterable[str]) -> tuple[int, int, int]:
    """Count (orphans, total, duplicate_keys) over Consequence objects.

    A consequence is orphan when no actuation produces it or no
    ``receipt.persist`` consumes it. ``duplicate_keys`` counts consequence
    *keys* produced by more than one actuation (the court's DCR evidence).
    """
    acts = set(actuation_acts)
    otype = {o["id"]: o.get("type", "") for o in doc.get("objects", [])}
    key_of = {}
    for o in doc.get("objects", []):
        if o.get("type") == "Consequence":
            for attr in o.get("attributes", []):
                if attr.get("name") == "key":
                    key_of[o["id"]] = attr.get("value")
    producers: dict[str, set[str]] = {}
    consumers: dict[str, set[str]] = {}
    key_producers: dict[Any, set[str]] = {}
    for ev in doc.get("events", []):
        a = ev.get("type", "")
        for rel in ev.get("relationships", []):
            if rel.get("qualifier") == "consequence":
                cid = rel.get("objectId")
                if a in acts:
                    producers.setdefault(cid, set()).add(ev["id"])
                    key = key_of.get(cid)
                    if key is not None:
                        key_producers.setdefault(key, set()).add(ev["id"])
                elif a == "receipt.persist":
                    consumers.setdefault(cid, set()).add(ev["id"])
    total = sum(1 for o in doc.get("objects", []) if o.get("type") == "Consequence")
    orphans = sum(
        1
        for o in doc.get("objects", [])
        if o.get("type") == "Consequence"
        and (not producers.get(o["id"]) or not consumers.get(o["id"]))
    )
    duplicates = sum(1 for ps in key_producers.values() if len(ps) > 1)
    return orphans, total, duplicates


def authority_kinds(doc: Mapping[str, Any]) -> list[str]:
    """Sorted kinds of Authority objects cited as originAuthority (any epoch)."""
    kind = {}
    for o in doc.get("objects", []):
        if o.get("type") == "Authority":
            for attr in o.get("attributes", []):
                if attr.get("name") == "kind":
                    kind[o["id"]] = attr.get("value")
    otype = {o["id"]: o.get("type", "") for o in doc.get("objects", [])}
    used: set[str] = set()
    for ev in doc.get("events", []):
        for rel in ev.get("relationships", []):
            if rel.get("qualifier") == "originAuthority" and otype.get(rel.get("objectId")) == "Authority":
                k = kind.get(rel["objectId"])
                if k is not None:
                    used.add(k)
    return sorted(used)


# ── scoring ─────────────────────────────────────────────────────────────────


def score_log(path: Path | str, *, cold_replay: bool = True) -> dict[str, Any]:
    """Score one log: court verdict + aggregated portfolio metrics + RPR."""
    document, fmt, raw = load_document(path)
    digest = _sha256(raw)
    profile = load_profile()
    code, receipt = evaluate_document(document, log_sha256=digest, log_locator=str(path))
    episodes = receipt.get("episodes", [])
    counts = {
        "receipts": sum(ep["metrics"]["receipts"] for ep in episodes),
        "failures": sum(ep["metrics"]["failures"] for ep in episodes),
        "provider_unavailable": sum(ep["metrics"]["provider_unavailable"] for ep in episodes),
        "actuations": sum(ep["metrics"]["actuations"] for ep in episodes),
        "unreceipted_actuations": sum(ep["metrics"]["unreceipted_actuations"] for ep in episodes),
        "closed_loop_cycles": sum(ep["metrics"]["closed_loop_cycles"] for ep in episodes),
    }
    closing = sum(
        (ep["metrics"]["LCR"] or 0) * ep["metrics"]["receipts"] for ep in episodes
    )
    recovered = sum((ep["metrics"]["RR"] or 0) * ep["metrics"]["failures"] for ep in episodes)
    substituted = sum((ep["metrics"]["PSR"] or 0) * ep["metrics"]["provider_unavailable"] for ep in episodes)
    reconciled, crashes = crash_reconciliation(document, profile["recoveryActivities"])
    orphans, total_csq, duplicate_keys = consequence_orphans(document, profile["actuations"])
    rpr: float | None = None
    if cold_replay:
        code2, receipt2 = evaluate_document(
            json.loads(raw) if fmt == "ocel2-json" else load_document(path)[0],
            log_sha256=digest,
            log_locator=str(path),
        )
        rpr = 1.0 if (code2, receipt2.get("receipt_digest")) == (code, receipt.get("receipt_digest")) else 0.0
    metrics = {
        "HIR": max((ep["metrics"]["HIR"] or 0.0) for ep in episodes) if episodes else 0.0,
        "ALD": max((ep["metrics"]["ALD"] for ep in episodes), default=0),
        "LCR": _ratio(closing, counts["receipts"]),
        "RR": _ratio(recovered, counts["failures"]),
        "UAR": _ratio(counts["unreceipted_actuations"], counts["actuations"]) or 0.0,
        "PSR": _ratio(substituted, counts["provider_unavailable"]),
        "CRR": _ratio(reconciled, crashes),
        "OCR": _ratio(orphans, total_csq) or 0.0,
        "DCR": _ratio(duplicate_keys, max(total_csq, 1)) if total_csq else 0.0,
        "RPR": rpr,
        "crash_windows": crashes,
        "reconciled_crash_windows": reconciled,
        "consequence_orphans": orphans,
        "consequences": total_csq,
        "duplicate_consequence_keys": duplicate_keys,
        "authority_kinds": authority_kinds(document),
        "counts": counts,
    }
    return {
        "log": str(path),
        "format": fmt,
        "sha256": digest,
        "bytes": len(raw),
        "exit": code,
        "verdict": receipt.get("verdict"),
        "standing": receipt.get("standing"),
        "episodes": [
            {
                "episode": ep["episode"],
                "class": ep["class"],
                "metrics": ep["metrics"],
                "reason_codes": [r.get("code") for r in ep.get("reasons", [])],
            }
            for ep in episodes
        ],
        "unmet": receipt.get("unmet", []),
        "refusals": receipt.get("refusals", []),
        "metrics": metrics,
        "receipt_digest": receipt.get("receipt_digest"),
    }


def semantic_signature(score: Mapping[str, Any]) -> dict[str, Any]:
    """Provider-invariant semantic fields of a scored log.

    Per ALOOP-004 (provider extinction): WorkOrder identity/authority,
    acceptance structure and receipt schema must not change when the
    execution provider changes; only capacity/latency/cost/capabilities may.
    """
    return {
        "receipt_schema": "autofde-lab/aloop-court-receipt/v1",
        "verdict": score.get("verdict"),
        "authority_kinds": score["metrics"]["authority_kinds"],
        "episodes": [
            {
                "class": ep["class"],
                "workorders": ep["metrics"]["workorders"],
                "self_generated_workorders": ep["metrics"]["self_generated_workorders"],
                "receipts": ep["metrics"]["receipts"],
                "closed_loop_cycles": ep["metrics"]["closed_loop_cycles"],
                "ALD": ep["metrics"]["ALD"],
            }
            for ep in score.get("episodes", [])
        ],
    }


def _leaves(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _leaves(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _leaves(v, f"{prefix}[{i}]")
    else:
        yield prefix, value


def semantic_divergence(sig_a: Mapping[str, Any], sig_b: Mapping[str, Any]) -> float | None:
    """PDR between two signatures: diverged leaf fields / compared leaf fields."""
    la = dict(_leaves(sig_a))
    lb = dict(_leaves(sig_b))
    keys = set(la) | set(lb)
    if not keys:
        return None
    diverged = sum(1 for k in keys if la.get(k, "__absent__") != lb.get(k, "__absent__"))
    return diverged / len(keys)


# ── corpus (mutation battery) ───────────────────────────────────────────────


def score_corpus(corpus_dir: Path | str | None = None, *, workdir: Path | str | None = None) -> dict[str, Any]:
    """Score a mutant corpus against its MANIFEST.json expectations.

    ``corpus_dir`` must contain ``MANIFEST.json`` (as written by
    :func:`autofde_lab.aloop.synth.write_all`). When ``None`` the corpus is
    regenerated deterministically into ``workdir`` (or a temp dir) exactly as
    the committed test suite does -- the mutants are never committed.
    A mutant is *killed* when exit code, episode class and refusal code all
    equal the manifest expectation; MKR = killed / executed.
    """
    tmp = None
    if corpus_dir is None:
        tmp = tempfile.TemporaryDirectory(prefix="aloop-corpus-")
        root = Path(tmp.name)
        from autofde_lab.aloop.synth import write_all

        write_all(root / "corpus")
        corpus_dir = root / "corpus"
    else:
        corpus_dir = Path(corpus_dir)
    try:
        manifest = json.loads((corpus_dir / "MANIFEST.json").read_text())
        files: dict[str, Any] = {}
        killed = 0
        executed = 0
        for rel, expect_spec in sorted(manifest["files"].items()):
            path = corpus_dir / rel
            expect = expect_spec["expect"]
            score = score_log(path)
            got_class = score["episodes"][0]["class"] if score["episodes"] else None
            codes: set[str | None] = set()
            for src in (score["refusals"], score["unmet"]):
                codes.update(r.get("code") for r in src)
            for ep in score["episodes"]:
                codes.update(ep["reason_codes"])
            # a mutant is killed when the exit status matches AND the court
            # names the expected class (or refuses outright) AND names the
            # expected typed code anywhere in the sealed receipt
            hit = score["exit"] == expect["exit"] and (
                expect["class"] is None or got_class == expect["class"]
            ) and (
                expect["code"] is None or expect["code"] in codes
            )
            executed += 1
            killed += int(hit)
            files[rel] = {
                "expect": expect,
                "exit": score["exit"],
                "class": got_class,
                "codes": sorted(c for c in codes if c),
                "killed": hit,
            }
        controls = {
            "human_edge_is_ASSISTED": files.get("mutants/human_after_epoch.ocel.json", {}).get("class") == "ASSISTED",
            "severed_recurrence_fails_ALOOP_001": (
                "AUTOMATION_NOT_AUTONOMY"
                in files.get("mutants/fixed_task_cron.ocel.json", {}).get("codes", [])
            ),
            "short_loop_insufficient_depth": (
                "INSUFFICIENT_LOOP_DEPTH"
                in files.get("mutants/short_loop.ocel.json", {}).get("codes", [])
            ),
        }
        return {
            "corpus": str(corpus_dir),
            "regenerated": tmp is not None,
            "files": files,
            "MKR": {"killed": killed, "executed": executed, "value": _ratio(killed, executed)},
            "negative_controls": controls,
        }
    finally:
        if tmp is not None:
            tmp.cleanup()


# ── scoreboard ──────────────────────────────────────────────────────────────


def scoreboard(
    log_scores: list[Mapping[str, Any]],
    *,
    corpus: Mapping[str, Any] | None = None,
    pdr_pairs: Iterable[tuple[Mapping[str, Any], Mapping[str, Any], str]] = (),
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the machine-readable scoreboard over a portfolio of logs.

    ``pdr_pairs`` yields ``(score_a, score_b, label)`` signature comparisons;
    PDR is the mean divergence over them (0.0 when none are given).
    """
    metrics: dict[str, Any] = {}
    for name in ("HIR", "ALD"):
        vals = [s["metrics"][name] for s in log_scores]
        metrics[name] = max(vals) if vals else (0.0 if name == "HIR" else 0)

    # numerators are pooled from the per-log ratios and their denominators
    derivations = {
        "LCR": lambda s: ((s["metrics"]["LCR"] or 0) * s["metrics"]["counts"]["receipts"],
                          s["metrics"]["counts"]["receipts"]),
        "RR": lambda s: ((s["metrics"]["RR"] or 0) * s["metrics"]["counts"]["failures"],
                         s["metrics"]["counts"]["failures"]),
        "UAR": lambda s: (s["metrics"]["counts"]["unreceipted_actuations"],
                          s["metrics"]["counts"]["actuations"]),
        "PSR": lambda s: ((s["metrics"]["PSR"] or 0) * s["metrics"]["counts"]["provider_unavailable"],
                          s["metrics"]["counts"]["provider_unavailable"]),
        "CRR": lambda s: (s["metrics"]["reconciled_crash_windows"], s["metrics"]["crash_windows"]),
        "OCR": lambda s: (s["metrics"]["consequence_orphans"], s["metrics"]["consequences"]),
    }
    for name, fn in derivations.items():
        k = sum(fn(s)[0] for s in log_scores)
        n = sum(fn(s)[1] for s in log_scores)
        v = _ratio(int(k), int(n))
        metrics[name] = 0.0 if (v is None and name in ("UAR", "OCR")) else v
        metrics[f"{name}_wilson95"] = wilson(int(k), int(n))

    dcr = [s["metrics"]["DCR"] or 0.0 for s in log_scores]
    metrics["DCR"] = max(dcr) if dcr else 0.0
    rpr_k = sum(1 for s in log_scores if s["metrics"]["RPR"] == 1.0)
    rpr_n = sum(1 for s in log_scores if s["metrics"]["RPR"] is not None)
    metrics["RPR"] = _ratio(rpr_k, rpr_n)
    metrics["RPR_wilson95"] = wilson(rpr_k, rpr_n)

    pdr_vals = []
    pdr_detail = []
    for a, b, label in pdr_pairs:
        d = semantic_divergence(semantic_signature(a), semantic_signature(b))
        pdr_vals.append(d or 0.0)
        pdr_detail.append({"pair": label, "PDR": d})
    metrics["PDR"] = sum(pdr_vals) / len(pdr_vals) if pdr_vals else 0.0
    metrics["PDR_pairs"] = pdr_detail

    mkr = (corpus or {}).get("MKR") or {}
    metrics["MKR"] = mkr.get("value")
    metrics["MKR_wilson95"] = (
        wilson(mkr["killed"], mkr["executed"]) if mkr.get("executed") else None
    )

    controls = (corpus or {}).get("negative_controls") or {}
    invariants = {
        "UAR_zero": metrics["UAR"] == 0.0,
        "DCR_zero": metrics["DCR"] == 0.0,
        "OCR_zero": metrics["OCR"] == 0.0,
        "PDR_zero": metrics["PDR"] == 0.0,
        "MKR_full": metrics["MKR"] == 1.0,
        "RPR_full": metrics["RPR"] == 1.0,
    }
    return {
        "schema": "autofde-lab/aloop-scoreboard/v1",
        "provenance": provenance or {},
        "logs": [s["log"] for s in log_scores],
        "log_results": list(log_scores),
        "corpus": {
            k: (corpus or {}).get(k)
            for k in ("corpus", "regenerated", "MKR", "negative_controls")
            if corpus and corpus.get(k) is not None
        },
        "metrics": metrics,
        "invariants": invariants,
        "negative_controls": controls,
        "standing": (
            "ALIVE"
            if all(invariants.values()) and all(controls.values()) and controls
            else "PARTIAL_ALIVE"
            if log_scores
            else "UNKNOWN"
        ),
        "standing_note": (
            "scoreboard over the named synthetic logs only; OCEL is a flight "
            "recorder, not proof that any real loop is autonomous"
        ),
    }
