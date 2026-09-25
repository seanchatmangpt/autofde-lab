# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Deterministic synthetic ALOOP-001 fixtures: one closed loop and its mutants.

``python -m autofde_lab.aloop.synth OUT_DIR`` writes ``positive.ocel.json``,
``mutants/<name>.ocel.json`` and ``MANIFEST.json`` (expected verdict and
sha256 per file). Only ``positive.ocel.json`` and ``MANIFEST.json`` are
committed (the mutants would breach the repo's 500 KB large-file gate
fourteen times over); the test suite regenerates the whole corpus as real
files on disk, requires every file's sha256 to equal the committed manifest
and the positive log to equal the committed bytes, then runs the court over
those files.

The positive log is synthetic by construction -- it is a falsifier corpus for
the court, not evidence that any real system is autonomous.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

from autofde_lab.aloop.court import load_profile
from autofde_lab.aloop.ocel_builder import Builder, dump

T0 = 1_790_000_000_000_000_000  # fixed epoch for synthetic time; never wall-clock
SECOND = 1_000_000_000
POSITIVE_ITERATIONS = 101
CRASH_AT = 40
EXTINCTION_AT = 70


def _sha(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


def build_positive(iterations: int = POSITIVE_ITERATIONS) -> dict[str, Any]:
    profile = load_profile()
    b = Builder(profile["objectTypes"], profile["eventTypes"])
    clock = [T0]

    def tick() -> int:
        clock[0] += SECOND
        return clock[0]

    ep = b.obj("ep-1", "Episode")
    hum = b.obj("hum-operator", "Human", role="operator")
    b.obj("obj-1", "Objective")
    b.obj("auth-policy", "Authority", kind="policy", grantedBy="hum-operator")
    b.obj("repo-1", "Repository")
    b.obj("prov-claude", "Provider", name="claude")
    b.obj("prov-zcode", "Provider", name="zcode")
    b.obj("sub-0", "Subject", sha=_sha("subject-0"), repository="repo-1")

    E = lambda *rels: [("episode", ep), *rels]  # noqa: E731

    # Before t0: the human supplies goal + policy authority. Recorded, allowed.
    b.event(
        "h-pre",
        "human.intervene",
        tick(),
        E(("originAuthority", hum), ("output", "obj-1"), ("output", "auth-policy")),
        basis="objective and policy grant before the autonomy epoch",
    )
    b.event(
        "e-start",
        "episode.start",
        tick(),
        E(("subject", "sub-0"), ("input", "obj-1"), ("input", "auth-policy")),
    )
    provider = "prov-claude"
    for i in range(iterations):
        ev = b.obj(f"ev-obs-{i}", "Evidence")
        if i == 0:
            b.event(
                "e-observe-0", "observe", tick(), E(("input", "obj-1"), ("output", ev))
            )
        else:
            b.event(
                f"e-reobserve-{i}",
                "reobserve",
                tick(),
                E(("cause", f"rcpt-{i - 1}"), ("output", ev)),
            )
        b.obj(f"gap-{i}", "Evidence")
        b.event(
            f"e-gap-{i}", "gap.detect", tick(), E(("cause", ev), ("output", f"gap-{i}"))
        )
        b.obj(f"cand-{i}", "Plan")
        b.event(
            f"e-cand-{i}",
            "candidate.construct",
            tick(),
            E(("cause", f"gap-{i}"), ("output", f"cand-{i}")),
        )
        b.obj(f"adm-{i}", "Plan")
        b.event(
            f"e-admit-{i}",
            "candidate.admit",
            tick(),
            E(("input", f"cand-{i}"), ("output", f"adm-{i}")),
        )
        b.obj(f"plan-{i}", "Plan")
        b.event(
            f"e-plan-{i}",
            "plan.select",
            tick(),
            E(("input", f"adm-{i}"), ("output", f"plan-{i}")),
        )
        b.obj(f"wo-{i}", "WorkOrder")
        b.event(
            f"e-wo-{i}",
            "workorder.issue",
            tick(),
            E(
                ("cause", f"plan-{i}"),
                ("output", f"wo-{i}"),
                ("originAuthority", "auth-policy"),
            ),
        )
        b.obj(f"sel-{i}", "Evidence")
        b.event(
            f"e-psel-{i}",
            "provider.select",
            tick(),
            E(("input", f"wo-{i}"), ("provider", provider), ("output", f"sel-{i}")),
        )
        run_input = f"sel-{i}"
        if i == EXTINCTION_AT:
            b.obj(
                f"fail-{i}",
                "Failure",
                code="PROVIDER_UNAVAILABLE",
                broken_term="R_not_fed_back",
            )
            b.event(
                f"e-unavail-{i}",
                "provider.unavailable",
                tick(),
                E(
                    ("input", f"sel-{i}"),
                    ("provider", provider),
                    ("output", f"fail-{i}"),
                ),
            )
            b.event(
                f"e-replace-{i}",
                "provider.replace",
                tick(),
                E(
                    ("cause", f"fail-{i}"),
                    ("input", f"fail-{i}"),
                    ("output", "prov-zcode"),
                ),
            )
            provider = "prov-zcode"
            run_input = "prov-zcode"
        b.obj(f"run-{i}", "WorkerRun", run_id=f"run-{i}")
        b.event(
            f"e-exec-{i}",
            "execution.start",
            tick(),
            E(("input", run_input), ("provider", provider), ("output", f"run-{i}")),
        )
        run = f"run-{i}"
        if i == CRASH_AT:
            b.obj(
                f"crash-{i}",
                "Failure",
                code="WORKER_CRASH",
                broken_term="R_missing_consequence",
            )
            b.event(
                f"e-crash-{i}",
                "execution.crash",
                tick(),
                E(("input", run), ("output", f"crash-{i}")),
            )
            b.obj(f"replan-{i}", "Plan")
            b.event(
                f"e-replan-{i}",
                "replan",
                tick(),
                E(("cause", f"crash-{i}"), ("output", f"replan-{i}")),
            )
            b.obj(f"run-{i}b", "WorkerRun", run_id=f"run-{i}b")
            b.event(
                f"e-exec-{i}b",
                "execution.start",
                tick(),
                E(
                    ("input", f"replan-{i}"),
                    ("provider", provider),
                    ("output", f"run-{i}b"),
                ),
            )
            run = f"run-{i}b"
        b.obj(f"csq-{i}", "Consequence", key=f"change:{i}")
        b.event(
            f"e-act-{i}",
            "actuate",
            tick(),
            E(("input", run), ("consequence", f"csq-{i}")),
            basis="synthetic",
        )
        b.obj(f"csq-commit-{i}", "Consequence", key=f"commit:{i}")
        b.obj(
            f"sub-{i + 1}", "Subject", sha=_sha(f"subject-{i + 1}"), repository="repo-1"
        )
        b.event(
            f"e-commit-{i}",
            "commit",
            tick(),
            E(
                ("input", f"csq-{i}"),
                ("subject", f"sub-{i}"),
                ("consequence", f"csq-commit-{i}"),
                ("output", f"sub-{i + 1}"),
            ),
            basis="synthetic",
        )
        b.obj(f"ver-{i}", "Evidence")
        b.event(
            f"e-verify-{i}",
            "verify",
            tick(),
            E(("input", f"sub-{i + 1}"), ("output", f"ver-{i}")),
        )
        b.obj(f"fal-{i}", "Evidence")
        b.event(
            f"e-fals-{i}",
            "falsifier.run",
            tick(),
            E(("input", f"ver-{i}"), ("output", f"fal-{i}")),
        )
        b.obj(f"rcpt-{i}", "Receipt", digest=_sha(f"rcpt-{i}"))
        b.event(
            f"e-rcpt-{i}",
            "receipt.persist",
            tick(),
            E(
                ("input", f"fal-{i}"),
                ("output", f"rcpt-{i}"),
                ("subject", f"sub-{i + 1}"),
                ("consequence", f"csq-{i}"),
                ("consequence", f"csq-commit-{i}"),
            ),
        )
    last = iterations - 1
    b.obj("ev-final", "Evidence")
    b.event(
        "e-reobserve-final",
        "reobserve",
        tick(),
        E(("cause", f"rcpt-{last}"), ("output", "ev-final")),
    )
    b.event("e-satisfied", "goal.satisfied", tick(), E(("cause", "ev-final")))
    b.event("e-terminal", "episode.terminal", tick(), E(("cause", "ev-final")))
    return b.document()


# ── mutants ─────────────────────────────────────────────────────────────────


def _event(doc: dict[str, Any], eid: str) -> dict[str, Any]:
    (event,) = [e for e in doc["events"] if e["id"] == eid]
    return event


def _object(doc: dict[str, Any], oid: str) -> dict[str, Any]:
    (obj,) = [o for o in doc["objects"] if o["id"] == oid]
    return obj


def _insert_before(doc: dict[str, Any], eid: str, event: dict[str, Any]) -> None:
    idx = next(i for i, e in enumerate(doc["events"]) if e["id"] == eid)
    doc["events"].insert(idx, event)


def _time_before(doc: dict[str, Any], eid: str) -> str:
    from autofde_lab.ocel.model import format_ns, parse_ns

    return format_ns(parse_ns(_event(doc, eid)["time"]) - SECOND // 2)


def m_human_after_epoch(doc):
    doc["objects"].append(
        {"id": "hprose-50", "type": "Evidence", "attributes": [], "relationships": []}
    )
    _insert_before(
        doc,
        "e-wo-50",
        {
            "id": "h-post-50",
            "type": "human.intervene",
            "time": _time_before(doc, "e-wo-50"),
            "attributes": [
                {"name": "basis", "value": "operator nudged the next work order"}
            ],
            "relationships": [
                {"objectId": "ep-1", "qualifier": "episode"},
                {"objectId": "hum-operator", "qualifier": "originAuthority"},
                {"objectId": "hprose-50", "qualifier": "output"},
            ],
        },
    )
    _event(doc, "e-wo-50")["relationships"].append(
        {"objectId": "hprose-50", "qualifier": "cause"}
    )


def m_actuate_without_receipt(doc):
    rels = _event(doc, "e-rcpt-60")["relationships"]
    rels[:] = [r for r in rels if r["objectId"] != "csq-60"]


def m_duplicate_consequence(doc):
    for a in _object(doc, "csq-61")["attributes"]:
        if a["name"] == "key":
            a["value"] = "change:60"


def m_forged_origin_authority(doc):
    doc["objects"].append(
        {
            "id": "auth-forged",
            "type": "Authority",
            "attributes": [
                {
                    "name": "kind",
                    "value": "lease",
                    "time": "1970-01-01T00:00:00.000000000Z",
                },
                {
                    "name": "grantedBy",
                    "value": "self",
                    "time": "1970-01-01T00:00:00.000000000Z",
                },
            ],
            "relationships": [],
        }
    )
    for r in _event(doc, "e-wo-30")["relationships"]:
        if r["qualifier"] == "originAuthority":
            r["objectId"] = "auth-forged"


def m_missing_origin_authority(doc):
    rels = _event(doc, "e-wo-31")["relationships"]
    rels[:] = [r for r in rels if r["qualifier"] != "originAuthority"]


def m_human_prose_cause(doc):
    doc["objects"].append(
        {
            "id": "prose-20",
            "type": "Evidence",
            "attributes": [
                {
                    "name": "origin",
                    "value": "human",
                    "time": "1970-01-01T00:00:00.000000000Z",
                },
                {
                    "name": "locator",
                    "value": "chat:please do X next",
                    "time": "1970-01-01T00:00:00.000000000Z",
                },
            ],
            "relationships": [],
        }
    )
    for r in _event(doc, "e-wo-20")["relationships"]:
        if r["qualifier"] == "cause":
            r["objectId"] = "prose-20"


def m_provider_replaced_by_human(doc):
    ev = _event(doc, f"e-replace-{EXTINCTION_AT}")
    ev["type"] = "human.intervene"
    ev["attributes"] = [
        {"name": "basis", "value": "operator swapped the provider by hand"}
    ]
    ev["relationships"] = [
        {"objectId": "ep-1", "qualifier": "episode"},
        {"objectId": "hum-operator", "qualifier": "originAuthority"},
        {"objectId": f"fail-{EXTINCTION_AT}", "qualifier": "input"},
        {"objectId": "prov-zcode", "qualifier": "output"},
    ]


def m_stale_subject(doc):
    for r in _event(doc, "e-rcpt-80")["relationships"]:
        if r["qualifier"] == "subject":
            r["objectId"] = "sub-80"


def m_malformed_qualifier(doc):
    for r in _event(doc, "e-gap-5")["relationships"]:
        if r["qualifier"] == "cause":
            r["qualifier"] = "caused_by"


def m_cause_from_future(doc):
    for r in _event(doc, "e-wo-10")["relationships"]:
        if r["qualifier"] == "cause":
            r["objectId"] = "plan-11"


def m_orphan_receipt(doc):
    doc["objects"].append(
        {
            "id": "csq-ghost",
            "type": "Consequence",
            "attributes": [
                {
                    "name": "key",
                    "value": "ghost",
                    "time": "1970-01-01T00:00:00.000000000Z",
                }
            ],
            "relationships": [],
        }
    )
    _event(doc, "e-rcpt-90")["relationships"].append(
        {"objectId": "csq-ghost", "qualifier": "consequence"}
    )


def m_schema_violation(doc):
    del _event(doc, "e-verify-3")["time"]


MUTANTS: dict[str, tuple[Callable[[dict[str, Any]], None], dict[str, Any]]] = {
    "human_after_epoch": (
        m_human_after_epoch,
        {"exit": 3, "class": "ASSISTED", "code": "HUMAN_CAUSALITY_AFTER_EPOCH"},
    ),
    "actuate_without_receipt": (
        m_actuate_without_receipt,
        {"exit": 3, "class": "FAILED", "code": "UNRECEIPTED_ACTUATION"},
    ),
    "duplicate_consequence": (
        m_duplicate_consequence,
        {"exit": 3, "class": "FAILED", "code": "DUPLICATE_CONSEQUENCE"},
    ),
    "forged_origin_authority": (
        m_forged_origin_authority,
        {"exit": 2, "class": None, "code": "FORGED_ORIGIN_AUTHORITY"},
    ),
    "missing_origin_authority": (
        m_missing_origin_authority,
        {"exit": 2, "class": None, "code": "PROFILE_QUALIFIER_CARDINALITY"},
    ),
    "human_prose_cause": (
        m_human_prose_cause,
        {"exit": 3, "class": "ASSISTED", "code": "HUMAN_CAUSALITY_AFTER_EPOCH"},
    ),
    "provider_replaced_by_human": (
        m_provider_replaced_by_human,
        {"exit": 3, "class": "FAILED", "code": "PROVIDER_SUBSTITUTION_FAILED"},
    ),
    "stale_subject": (
        m_stale_subject,
        {"exit": 3, "class": "FAILED", "code": "STALE_SUBJECT"},
    ),
    "malformed_qualifier": (
        m_malformed_qualifier,
        {"exit": 2, "class": None, "code": "PROFILE_UNKNOWN_QUALIFIER"},
    ),
    "cause_from_future": (
        m_cause_from_future,
        {"exit": 2, "class": None, "code": "CAUSALITY_VIOLATION"},
    ),
    "orphan_receipt": (
        m_orphan_receipt,
        {"exit": 3, "class": "FAILED", "code": "ORPHAN_RECEIPT"},
    ),
    "schema_violation": (
        m_schema_violation,
        {"exit": 2, "class": None, "code": "OCEL2_SCHEMA_VIOLATION"},
    ),
}


def build_fixed_task_cron(runs: int = 104) -> dict[str, Any]:
    """Automation, not autonomy: a cron fires the same task; receipts feed nothing."""
    profile = load_profile()
    b = Builder(profile["objectTypes"], profile["eventTypes"])
    t = T0
    ep = b.obj("ep-cron", "Episode")
    b.obj("auth-cron", "Authority", kind="lease", grantedBy="scheduler")
    b.obj("sub-c0", "Subject", sha=_sha("cron-subject"), repository="repo-cron")
    E = lambda *rels: [("episode", ep), *rels]  # noqa: E731
    t += SECOND
    b.event(
        "c-start", "episode.start", t, E(("subject", "sub-c0"), ("input", "auth-cron"))
    )
    for i in range(runs):
        b.obj(f"c-obs-{i}", "Evidence")
        t += SECOND
        b.event(f"c-observe-{i}", "observe", t, E(("output", f"c-obs-{i}")))
        b.obj(f"c-wo-{i}", "WorkOrder")
        t += SECOND
        b.event(
            f"c-issue-{i}",
            "workorder.issue",
            t,
            E(
                ("cause", f"c-obs-{i}"),
                ("output", f"c-wo-{i}"),
                ("originAuthority", "auth-cron"),
            ),
        )
        b.obj(f"c-csq-{i}", "Consequence", key=f"cron:{i}")
        t += SECOND
        b.event(
            f"c-act-{i}",
            "actuate",
            t,
            E(("input", f"c-wo-{i}"), ("consequence", f"c-csq-{i}")),
        )
        b.obj(f"c-rcpt-{i}", "Receipt", digest=_sha(f"c-rcpt-{i}"))
        t += SECOND
        b.event(
            f"c-receipt-{i}",
            "receipt.persist",
            t,
            E(
                ("output", f"c-rcpt-{i}"),
                ("subject", "sub-c0"),
                ("consequence", f"c-csq-{i}"),
            ),
        )
    return b.document()


def build_short_loop() -> dict[str, Any]:
    return build_positive(iterations=20)


def write_all(out: Path) -> dict[str, Any]:
    out = Path(out)
    manifest: dict[str, Any] = {
        "generator": "python -m autofde_lab.aloop.synth <out>",
        "note": "synthetic falsifier corpus for ALOOP-001; not evidence about any real system",
        "files": {},
    }
    positive = build_positive()
    manifest["files"]["positive.ocel.json"] = {
        "expect": {"exit": 0, "class": "AUTONOMOUS", "code": None},
        "sha256": hashlib.sha256(
            dump(positive, out / "positive.ocel.json")
        ).hexdigest(),
    }
    extra = {
        "fixed_task_cron": (
            build_fixed_task_cron(),
            {"exit": 3, "class": "FAILED", "code": "AUTOMATION_NOT_AUTONOMY"},
        ),
        "short_loop": (
            build_short_loop(),
            {"exit": 3, "class": "AUTONOMOUS", "code": "INSUFFICIENT_LOOP_DEPTH"},
        ),
    }
    for name, (mutate, expect) in MUTANTS.items():
        doc = copy.deepcopy(positive)
        mutate(doc)
        extra[name] = (doc, expect)
    for name, (doc, expect) in sorted(extra.items()):
        rel = f"mutants/{name}.ocel.json"
        manifest["files"][rel] = {
            "expect": expect,
            "sha256": hashlib.sha256(dump(doc, out / rel)).hexdigest(),
        }
    (out / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


if __name__ == "__main__":
    write_all(Path(sys.argv[1]))
