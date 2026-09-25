# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Deterministic synthetic ALOOP-001 fixtures: one closed loop and its mutants.

``python -m autofde_lab.aloop.synth OUT_DIR`` writes ``positive.ocel.json``,
``mutants/<name>.ocel.json`` and ``MANIFEST.json`` (expected verdict and
sha256 per file). Only ``positive.ocel.json`` and ``MANIFEST.json`` are
committed (the mutants would breach the repo's 500 KB large-file gate
many times over); the test suite regenerates the whole corpus as real
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


# ── repair round 1: adversarial-court attacks A1..A4, A6 as committed mutants ──


def m_receipt_reuses_old_consequence(doc):
    """A4: one DO receipted 100 times -- later iterations drop their actuations."""
    drop = set()
    for i in range(1, POSITIVE_ITERATIONS):
        drop |= {f"e-act-{i}", f"e-commit-{i}"}
        rcpt = _event(doc, f"e-rcpt-{i}")
        rcpt["relationships"] = [
            r
            for r in rcpt["relationships"]
            if r["qualifier"] not in ("consequence", "subject")
        ] + [
            {"objectId": "sub-1", "qualifier": "subject"},
            {"objectId": "csq-0", "qualifier": "consequence"},
        ]
        run = f"run-{i}b" if i == CRASH_AT else f"run-{i}"
        verify = _event(doc, f"e-verify-{i}")
        verify["relationships"] = [
            {"objectId": run, "qualifier": "input"} if r["qualifier"] == "input" else r
            for r in verify["relationships"]
        ]
    doc["events"] = [e for e in doc["events"] if e["id"] not in drop]


def m_o2o_hidden_human_plan(doc):
    """A2: every next-action consumes a Plan the log itself says derivedFrom a Human."""
    for i in range(POSITIVE_ITERATIONS):
        doc["objects"].append(
            {
                "id": f"hplan-{i}",
                "type": "Plan",
                "attributes": [],
                "relationships": [
                    {"objectId": "hum-operator", "qualifier": "derivedFrom"}
                ],
            }
        )
        _event(doc, f"e-wo-{i}")["relationships"].append(
            {"objectId": f"hplan-{i}", "qualifier": "cause"}
        )


def m_exogenous_unattributed_cause(doc):
    """A3: every next-action consumes an input with no producer in the log."""
    for i in range(POSITIVE_ITERATIONS):
        doc["objects"].append(
            {
                "id": f"instr-{i}",
                "type": "Evidence",
                "attributes": [
                    {
                        "name": "locator",
                        "value": "slack://operator/msg",
                        "time": "1970-01-01T00:00:00.000000000Z",
                    }
                ],
                "relationships": [],
            }
        )
        _event(doc, f"e-wo-{i}")["relationships"].append(
            {"objectId": f"instr-{i}", "qualifier": "cause"}
        )


def m_timestamp_only_loop(doc):
    """A6: reobserve[n+1] is caused by an exogenous tick, not by receipt[n]."""
    for i in range(1, POSITIVE_ITERATIONS):
        doc["objects"].append(
            {
                "id": f"tick-{i}",
                "type": "Evidence",
                "attributes": [],
                "relationships": [],
            }
        )
        ro = _event(doc, f"e-reobserve-{i}")
        ro["relationships"] = [
            {"objectId": f"tick-{i}", "qualifier": "cause"}
            if r["qualifier"] == "cause"
            else r
            for r in ro["relationships"]
        ]


# ── repair round 2: adversarial-court attacks B1, B2, B3b as committed mutants ──

_EPOCH_ATTR_TIME = "1970-01-01T00:00:00.000000000Z"


def m_human_evidence_side_channel(doc):
    """B1: a post-epoch human act links a hint under a non-producing qualifier."""
    for i in range(1, POSITIVE_ITERATIONS):
        doc["objects"] += [
            {
                "id": f"hint-{i}",
                "type": "Evidence",
                "attributes": [
                    {
                        "name": "locator",
                        "value": "operator says: do X next",
                        "time": _EPOCH_ATTR_TIME,
                    }
                ],
                "relationships": [],
            },
            {
                "id": f"hack-{i}",
                "type": "Evidence",
                "attributes": [],
                "relationships": [],
            },
        ]
        _insert_before(
            doc,
            f"e-reobserve-{i}",
            {
                "id": f"h-post-{i}",
                "type": "human.intervene",
                "time": _time_before(doc, f"e-reobserve-{i}"),
                "attributes": [
                    {"name": "basis", "value": "operator chose the next action"}
                ],
                "relationships": [
                    {"objectId": "ep-1", "qualifier": "episode"},
                    {"objectId": "hum-operator", "qualifier": "originAuthority"},
                    {"objectId": f"hack-{i}", "qualifier": "output"},
                    {"objectId": f"hint-{i}", "qualifier": "evidence"},
                ],
            },
        )
        _event(doc, f"e-reobserve-{i}")["relationships"].append(
            {"objectId": f"hint-{i}", "qualifier": "input"}
        )


def m_receipt_subject_is_repository(doc):
    """B2: receipts bind the Repository instead of an exact Subject sha."""
    for i in range(POSITIVE_ITERATIONS):
        for r in _event(doc, f"e-rcpt-{i}")["relationships"]:
            if r["qualifier"] == "subject":
                r["objectId"] = "repo-1"


def m_uncaused_unauthorized_commit(doc):
    """B3b: a commit with no input, no cause, no WorkOrder upstream, receipted."""
    for i in range(POSITIVE_ITERATIONS):
        doc["objects"] += [
            {
                "id": f"rogue-csq-{i}",
                "type": "Consequence",
                "attributes": [
                    {"name": "key", "value": f"rogue:{i}", "time": _EPOCH_ATTR_TIME}
                ],
                "relationships": [],
            },
            {
                "id": f"rogue-out-{i}",
                "type": "Evidence",
                "attributes": [],
                "relationships": [],
            },
        ]
        _insert_before(
            doc,
            f"e-rcpt-{i}",
            {
                "id": f"e-rogue-{i}",
                "type": "commit",
                "time": _time_before(doc, f"e-rcpt-{i}"),
                "attributes": [],
                "relationships": [
                    {"objectId": "ep-1", "qualifier": "episode"},
                    {"objectId": "repo-1", "qualifier": "subject"},
                    {"objectId": f"rogue-csq-{i}", "qualifier": "consequence"},
                    {"objectId": f"rogue-out-{i}", "qualifier": "output"},
                ],
            },
        )
        _event(doc, f"e-rcpt-{i}")["relationships"] += [
            {"objectId": f"rogue-csq-{i}", "qualifier": "consequence"},
            {"objectId": f"rogue-out-{i}", "qualifier": "input"},
        ]


def _human_event(eid: str, time: str, episode: str, human: str, rels) -> dict[str, Any]:
    return {
        "id": eid,
        "type": "human.intervene",
        "time": time,
        "attributes": [{"name": "basis", "value": "operator picks the next action"}],
        "relationships": [
            {"objectId": episode, "qualifier": "episode"},
            {"objectId": human, "qualifier": "originAuthority"},
            *({"objectId": o, "qualifier": q} for q, o in rels),
        ],
    }


def m_preepoch_laundered_human_script(doc):
    """C1 (r2 adversarial): a pre-epoch human scripts every next action as Plans;
    one pre-epoch machine hop copies them into Evidence each iteration consumes."""
    from autofde_lab.ocel.model import format_ns, parse_ns

    for i in range(POSITIVE_ITERATIONS):
        doc["objects"] += [
            {
                "id": f"script-{i}",
                "type": "Plan",
                "attributes": [],
                "relationships": [],
            },
            {
                "id": f"step-{i}",
                "type": "Evidence",
                "attributes": [],
                "relationships": [],
            },
        ]
    _insert_before(
        doc,
        "e-start",
        _human_event(
            "h-script",
            _time_before(doc, "e-start"),
            "ep-1",
            "hum-operator",
            [("output", f"script-{i}") for i in range(POSITIVE_ITERATIONS)],
        ),
    )
    start = parse_ns(_event(doc, "e-start")["time"])
    _insert_before(
        doc,
        "e-start",
        {
            "id": "e-launder",
            "type": "candidate.construct",
            "time": format_ns(start - SECOND // 4),
            "attributes": [],
            "relationships": [
                {"objectId": "ep-1", "qualifier": "episode"},
                *(
                    {"objectId": f"script-{i}", "qualifier": "cause"}
                    for i in range(POSITIVE_ITERATIONS)
                ),
                *(
                    {"objectId": f"step-{i}", "qualifier": "output"}
                    for i in range(POSITIVE_ITERATIONS)
                ),
            ],
        },
    )
    for i in range(POSITIVE_ITERATIONS):
        _event(doc, f"e-cand-{i}")["relationships"].append(
            {"objectId": f"step-{i}", "qualifier": "cause"}
        )


def _add_foreign_episode(doc) -> None:
    """Append a renamed 3-iteration positive episode ``x-ep-1`` starting after ep-1 ends."""
    from autofde_lab.ocel.model import format_ns, parse_ns

    mini = build_positive(3)
    for o in mini["objects"]:
        o["id"] = "x-" + o["id"]
        for a in o.get("attributes", []):
            if a["name"] == "grantedBy":
                a["value"] = "x-" + a["value"]
    last = parse_ns(_event(doc, f"e-rcpt-{POSITIVE_ITERATIONS - 1}")["time"])
    shift = last - T0 + 10 * SECOND
    for e in mini["events"]:
        e["id"] = "x-" + e["id"]
        e["time"] = format_ns(parse_ns(e["time"]) + shift)
        for r in e["relationships"]:
            r["objectId"] = "x-" + r["objectId"]
    doc["objects"] += mini["objects"]
    doc["events"] += mini["events"]


def _foreign_human_goals(doc) -> None:
    """Human acts tagged x-ep-1 (pre-epoch for x-ep-1, post-epoch for ep-1) author
    one 'next action' Objective per ep-1 iteration."""
    _add_foreign_episode(doc)
    for i in range(1, POSITIVE_ITERATIONS):
        doc["objects"].append(
            {
                "id": f"x-goal-{i}",
                "type": "Objective",
                "attributes": [],
                "relationships": [],
            }
        )
        _insert_before(
            doc,
            f"e-cand-{i}",
            _human_event(
                f"x-h-{i}",
                _time_before(doc, f"e-cand-{i}"),
                "x-ep-1",
                "x-hum-operator",
                [("output", f"x-goal-{i}")],
            ),
        )


def m_cross_episode_human_next_action(doc):
    """C2 (r2 adversarial): ep-1's next actions consume Objectives authored by
    human acts of another episode, judged against that episode's later epoch."""
    _foreign_human_goals(doc)
    for i in range(1, POSITIVE_ITERATIONS):
        _event(doc, f"e-cand-{i}")["relationships"].append(
            {"objectId": f"x-goal-{i}", "qualifier": "cause"}
        )


def m_cross_episode_o2o_human_objective(doc):
    """C2' (r3): the same foreign-episode human goals reached over O2O instead of E2O."""
    _foreign_human_goals(doc)
    for i in range(1, POSITIVE_ITERATIONS):
        (gap,) = [o for o in doc["objects"] if o["id"] == f"gap-{i}"]
        gap.setdefault("relationships", []).append(
            {"objectId": f"x-goal-{i}", "qualifier": "derivedFrom"}
        )


# ── repair round 4: B4 stale reobserve, C9 post-epoch authority laundering ──


def m_stale_reobserve_older_observation(doc):
    """B4 (r1 adversarial): each next action also reads the previous iteration's
    observation, older than receipt[n]; every receipt->reobserve edge still exists."""
    for i in range(1, POSITIVE_ITERATIONS):
        prev = "ev-obs-0" if i == 1 else f"ev-obs-{i - 1}"
        _event(doc, f"e-gap-{i}")["relationships"].append(
            {"objectId": prev, "qualifier": "cause"}
        )


def m_stale_reobserve_old_subject(doc):
    """B4: reobserve[n+1] is caused by receipt[n] but observes the Subject that
    iteration n's commit already superseded."""
    for i in range(1, POSITIVE_ITERATIONS):
        _event(doc, f"e-reobserve-{i}")["relationships"].append(
            {"objectId": f"sub-{i - 1}", "qualifier": "input"}
        )


def m_postepoch_human_amends_authority(doc):
    """C9 (r2 adversarial): a post-epoch human act re-touches the granted policy;
    every later work order keeps citing it as originAuthority."""
    doc["objects"].append(
        {"id": "hmemo", "type": "Evidence", "attributes": [], "relationships": []}
    )
    _insert_before(
        doc,
        "e-wo-50",
        _human_event(
            "h-auth",
            _time_before(doc, "e-wo-50"),
            "ep-1",
            "hum-operator",
            [("input", "auth-policy"), ("output", "hmemo")],
        ),
    )


def m_postepoch_human_o2o_authority(doc):
    """C9 over O2O: the post-epoch human act links only a memo that supersedes
    the granted policy; work orders cite the policy."""
    doc["objects"].append(
        {
            "id": "hmemo",
            "type": "Evidence",
            "attributes": [],
            "relationships": [{"objectId": "auth-policy", "qualifier": "supersedes"}],
        }
    )
    _insert_before(
        doc,
        "e-wo-50",
        _human_event(
            "h-auth",
            _time_before(doc, "e-wo-50"),
            "ep-1",
            "hum-operator",
            [("output", "hmemo")],
        ),
    )


def m_postepoch_unenveloped_authority_grant(doc):
    """C9: after t0 a machine event outputs a new Authority from the Objective
    alone, without consuming the pre-declared envelope Authority; later work
    orders consume it as a cause."""
    doc["objects"] += [
        {
            "id": "auth-late",
            "type": "Authority",
            "attributes": [
                {"name": "kind", "value": "grant", "time": _EPOCH_ATTR_TIME},
                {"name": "grantedBy", "value": "unknown", "time": _EPOCH_ATTR_TIME},
            ],
            "relationships": [],
        },
    ]
    _insert_before(
        doc,
        "e-wo-50",
        {
            "id": "e-late-grant",
            "type": "reconcile",
            "time": _time_before(doc, "e-wo-50"),
            "attributes": [],
            "relationships": [
                {"objectId": "ep-1", "qualifier": "episode"},
                {"objectId": "obj-1", "qualifier": "input"},
                {"objectId": "auth-late", "qualifier": "output"},
            ],
        },
    )
    for i in range(50, POSITIVE_ITERATIONS):
        _event(doc, f"e-wo-{i}")["relationships"].append(
            {"objectId": "auth-late", "qualifier": "cause"}
        )


# ── repair round 5: B4' stale state beyond the reobserve, C9 unbounded O2O ──


def m_stale_reobserve_reads_older_observation(doc):
    """B4' (finish adversarial F2): reobserve[n+1] consumes receipt[n] AND the
    observation of iteration n, older than receipt[n]. The segment ascent
    stopped at the reobserve, so its own inputs were never inspected."""
    for i in range(1, POSITIVE_ITERATIONS):
        prev = "ev-obs-0" if i == 1 else f"ev-obs-{i - 1}"
        _event(doc, f"e-reobserve-{i}")["relationships"].append(
            {"objectId": prev, "qualifier": "cause"}
        )


def m_stale_reobserve_via_machine_copy(doc):
    """B4' (finish adversarial F14): a machine ``reconcile`` after receipt[n]
    copies the observation of iteration n; reobserve[n+1] consumes the copy."""
    for i in range(1, POSITIVE_ITERATIONS):
        prev = "ev-obs-0" if i == 1 else f"ev-obs-{i - 1}"
        doc["objects"].append(
            {"id": f"cp-{i}", "type": "Evidence", "attributes": [], "relationships": []}
        )
        _insert_before(
            doc,
            f"e-reobserve-{i}",
            {
                "id": f"e-cp-{i}",
                "type": "reconcile",
                "time": _time_before(doc, f"e-reobserve-{i}"),
                "attributes": [],
                "relationships": [
                    {"objectId": "ep-1", "qualifier": "episode"},
                    {"objectId": prev, "qualifier": "input"},
                    {"objectId": f"cp-{i}", "qualifier": "output"},
                ],
            },
        )
        _event(doc, f"e-reobserve-{i}")["relationships"].append(
            {"objectId": f"cp-{i}", "qualifier": "cause"}
        )


def m_stale_decision_old_verify_evidence(doc):
    """B4' (finish adversarial F1b): gap.detect[n] decides only from the verify
    evidence of iteration n-2 (a Subject superseded twice); the fresh reobserve
    output is attached to plan.select as a decorative input."""
    for i in range(2, POSITIVE_ITERATIONS):
        gap = _event(doc, f"e-gap-{i}")
        gap["relationships"] = [
            r for r in gap["relationships"] if r["objectId"] != f"ev-obs-{i}"
        ] + [{"objectId": f"ver-{i - 2}", "qualifier": "cause"}]
        _event(doc, f"e-plan-{i}")["relationships"].append(
            {"objectId": f"ev-obs-{i}", "qualifier": "input"}
        )


def m_stale_reobserve_reads_old_verify_evidence(doc):
    """B4' (finish adversarial F2b): reobserve[n+1] also reads the verify
    evidence of iteration n-1, i.e. state of an already superseded Subject."""
    for i in range(2, POSITIVE_ITERATIONS):
        _event(doc, f"e-reobserve-{i}")["relationships"].append(
            {"objectId": f"ver-{i - 2}", "qualifier": "input"}
        )


def m_preepoch_machine_script(doc):
    """B4' (finish adversarial F4): a pre-epoch machine event precomputes every
    iteration's Plan; each work order cites its scripted Plan next to the
    genuine reobserve chain, so the next action is not derived from receipt[n]."""
    doc["objects"] += [
        {"id": f"pre-plan-{i}", "type": "Plan", "attributes": [], "relationships": []}
        for i in range(POSITIVE_ITERATIONS)
    ]
    _insert_before(
        doc,
        "e-start",
        {
            "id": "e-prescript",
            "type": "candidate.construct",
            "time": _time_before(doc, "e-start"),
            "attributes": [],
            "relationships": [
                {"objectId": "ep-1", "qualifier": "episode"},
                {"objectId": "obj-1", "qualifier": "cause"},
            ]
            + [
                {"objectId": f"pre-plan-{i}", "qualifier": "output"}
                for i in range(POSITIVE_ITERATIONS)
            ],
        },
    )
    for i in range(POSITIVE_ITERATIONS):
        _event(doc, f"e-wo-{i}")["relationships"].append(
            {"objectId": f"pre-plan-{i}", "qualifier": "cause"}
        )


def m_postepoch_human_two_hop_o2o_authority(doc):
    """C9' (finish adversarial F5): after t0 a human outputs a memo that is
    partOf a bundle which supersedes the granted policy (two O2O hops); work
    orders keep citing the policy. r4 followed O2O exactly one hop."""
    doc["objects"] += [
        {
            "id": "hmemo",
            "type": "Evidence",
            "attributes": [],
            "relationships": [{"objectId": "bundle", "qualifier": "partOf"}],
        },
        {
            "id": "bundle",
            "type": "Evidence",
            "attributes": [],
            "relationships": [{"objectId": "auth-policy", "qualifier": "supersedes"}],
        },
    ]
    _insert_before(
        doc,
        "e-wo-50",
        _human_event(
            "h-auth",
            _time_before(doc, "e-wo-50"),
            "ep-1",
            "hum-operator",
            [("output", "hmemo")],
        ),
    )


# ── repair round 6: B4'' Objective/Authority exempt by provenance, not type ──


def _objective_script(doc, actor: str, before: str, name: str) -> None:
    """One event mints a per-iteration ``Objective`` ``step-i`` for every iteration.

    A machine actor derives it from the pre-declared objective; a human actor
    authors it directly. Either way ``episode.start`` never binds it."""
    doc["objects"] += [
        {"id": f"step-{i}", "type": "Objective", "attributes": [], "relationships": []}
        for i in range(POSITIVE_ITERATIONS)
    ]
    rels = [{"objectId": "ep-1", "qualifier": "episode"}]
    rels.append(
        {"objectId": "hum-operator", "qualifier": "originAuthority"}
        if actor == "human.intervene"
        else {"objectId": "obj-1", "qualifier": "cause"}
    )
    rels += [
        {"objectId": f"step-{i}", "qualifier": "output"}
        for i in range(POSITIVE_ITERATIONS)
    ]
    _insert_before(
        doc,
        before,
        {
            "id": name,
            "type": actor,
            "time": _time_before(doc, before),
            "attributes": [],
            "relationships": rels,
        },
    )


def _decide_from_script(doc, first: int) -> None:
    """gap.detect[i] decides only from ``step-i``; the fresh reobserve output is
    attached to plan.select as a decorative input."""
    for i in range(first, POSITIVE_ITERATIONS):
        gap = _event(doc, f"e-gap-{i}")
        gap["relationships"] = [
            r for r in gap["relationships"] if r["objectId"] != f"ev-obs-{i}"
        ] + [{"objectId": f"step-{i}", "qualifier": "cause"}]
        _event(doc, f"e-plan-{i}")["relationships"].append(
            {"objectId": f"ev-obs-{i}", "qualifier": "input"}
        )


def m_preepoch_machine_objective_script_decorative(doc):
    """B4'' (finish adversarial r1 G1): F1b with the stale per-iteration state
    typed ``Objective``: a pre-epoch machine event mints step-0..100 and each
    gap.detect decides only from its step. r5 exempted the type and qualified."""
    _objective_script(doc, "candidate.construct", "e-start", "e-prescript")
    _decide_from_script(doc, 0)


def m_preepoch_machine_objective_script(doc):
    """B4'' (finish adversarial r1 G3): F4 (``preepoch_machine_script``) with
    the script typed ``Objective``; every work order cites its scripted step
    next to the genuine reobserve chain. r5 qualified it."""
    _objective_script(doc, "candidate.construct", "e-start", "e-prescript")
    for i in range(POSITIVE_ITERATIONS):
        _event(doc, f"e-wo-{i}")["relationships"].append(
            {"objectId": f"step-{i}", "qualifier": "cause"}
        )


def m_postepoch_machine_objective_script(doc):
    """B4'' (finish adversarial r1 G4): after t0, before reobserve-1, a machine
    event (no human) mints an ``Objective`` per iteration; gap.detect[i] decides
    from step-i, state older than receipt[i-1]. r5 qualified it."""
    _objective_script(doc, "candidate.construct", "e-reobserve-1", "e-midscript")
    _decide_from_script(doc, 1)


def m_preepoch_human_objective_script_decorative(doc):
    """B4'' (finish adversarial r1 G2): a pre-epoch human mints a per-iteration
    ``Objective`` script that episode.start never binds; each gap.detect decides
    only from its step. Not the pre-declared envelope, so it is stale state."""
    _objective_script(doc, "human.intervene", "e-start", "e-prescript")
    _decide_from_script(doc, 0)


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
    "receipt_reuses_old_consequence": (
        m_receipt_reuses_old_consequence,
        {"exit": 3, "class": "FAILED", "code": "CONSEQUENCE_RECEIPTED_TWICE"},
    ),
    "o2o_hidden_human_plan": (
        m_o2o_hidden_human_plan,
        {"exit": 3, "class": "ASSISTED", "code": "HUMAN_CAUSALITY_AFTER_EPOCH"},
    ),
    "exogenous_unattributed_cause": (
        m_exogenous_unattributed_cause,
        {"exit": 3, "class": "FAILED", "code": "UNATTRIBUTED_EXOGENOUS_CAUSE"},
    ),
    "timestamp_only_loop": (
        m_timestamp_only_loop,
        {"exit": 3, "class": "FAILED", "code": "AUTOMATION_NOT_AUTONOMY"},
    ),
    "human_evidence_side_channel": (
        m_human_evidence_side_channel,
        {"exit": 3, "class": "ASSISTED", "code": "HUMAN_CAUSALITY_AFTER_EPOCH"},
    ),
    "receipt_subject_is_repository": (
        m_receipt_subject_is_repository,
        {"exit": 2, "class": None, "code": "PROFILE_QUALIFIER_TARGET_TYPE"},
    ),
    "uncaused_unauthorized_commit": (
        m_uncaused_unauthorized_commit,
        {"exit": 3, "class": "FAILED", "code": "UNAUTHORIZED_ACTUATION"},
    ),
    "preepoch_laundered_human_script": (
        m_preepoch_laundered_human_script,
        {"exit": 3, "class": "ASSISTED", "code": "HUMAN_CAUSALITY_AFTER_EPOCH"},
    ),
    "cross_episode_human_next_action": (
        m_cross_episode_human_next_action,
        {"exit": 2, "class": None, "code": "CROSS_EPISODE_CAUSALITY"},
    ),
    "cross_episode_o2o_human_objective": (
        m_cross_episode_o2o_human_objective,
        {"exit": 3, "class": "ASSISTED", "code": "HUMAN_CAUSALITY_AFTER_EPOCH"},
    ),
    "stale_reobserve_older_observation": (
        m_stale_reobserve_older_observation,
        {"exit": 3, "class": "FAILED", "code": "STALE_REOBSERVE"},
    ),
    "stale_reobserve_old_subject": (
        m_stale_reobserve_old_subject,
        {"exit": 3, "class": "FAILED", "code": "STALE_REOBSERVE"},
    ),
    "postepoch_human_amends_authority": (
        m_postepoch_human_amends_authority,
        {"exit": 3, "class": "ASSISTED", "code": "HUMAN_CAUSALITY_AFTER_EPOCH"},
    ),
    "postepoch_human_o2o_authority": (
        m_postepoch_human_o2o_authority,
        {"exit": 3, "class": "ASSISTED", "code": "HUMAN_CAUSALITY_AFTER_EPOCH"},
    ),
    "postepoch_unenveloped_authority_grant": (
        m_postepoch_unenveloped_authority_grant,
        {"exit": 3, "class": "ASSISTED", "code": "HUMAN_CAUSALITY_AFTER_EPOCH"},
    ),
    "stale_reobserve_reads_older_observation": (
        m_stale_reobserve_reads_older_observation,
        {"exit": 3, "class": "FAILED", "code": "STALE_REOBSERVE"},
    ),
    "stale_reobserve_via_machine_copy": (
        m_stale_reobserve_via_machine_copy,
        {"exit": 3, "class": "FAILED", "code": "STALE_REOBSERVE"},
    ),
    "stale_decision_old_verify_evidence": (
        m_stale_decision_old_verify_evidence,
        {"exit": 3, "class": "FAILED", "code": "STALE_REOBSERVE"},
    ),
    "stale_reobserve_reads_old_verify_evidence": (
        m_stale_reobserve_reads_old_verify_evidence,
        {"exit": 3, "class": "FAILED", "code": "STALE_REOBSERVE"},
    ),
    "preepoch_machine_script": (
        m_preepoch_machine_script,
        {"exit": 3, "class": "FAILED", "code": "STALE_REOBSERVE"},
    ),
    "postepoch_human_two_hop_o2o_authority": (
        m_postepoch_human_two_hop_o2o_authority,
        {"exit": 3, "class": "ASSISTED", "code": "HUMAN_CAUSALITY_AFTER_EPOCH"},
    ),
    "preepoch_machine_objective_script_decorative": (
        m_preepoch_machine_objective_script_decorative,
        {"exit": 3, "class": "FAILED", "code": "STALE_REOBSERVE"},
    ),
    "preepoch_machine_objective_script": (
        m_preepoch_machine_objective_script,
        {"exit": 3, "class": "FAILED", "code": "STALE_REOBSERVE"},
    ),
    "postepoch_machine_objective_script": (
        m_postepoch_machine_objective_script,
        {"exit": 3, "class": "FAILED", "code": "STALE_REOBSERVE"},
    ),
    "preepoch_human_objective_script_decorative": (
        m_preepoch_human_objective_script_decorative,
        {"exit": 3, "class": "FAILED", "code": "STALE_REOBSERVE"},
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


def build_vacuous_loop(iterations: int = POSITIVE_ITERATIONS) -> dict[str, Any]:
    """A1: observe -> workorder -> receipt (no consequence) -> reobserve, never DO."""
    profile = load_profile()
    b = Builder(profile["objectTypes"], profile["eventTypes"])
    t = T0
    ep = b.obj("ep-v", "Episode")
    hum = b.obj("hum-v", "Human", role="operator")
    b.obj("obj-v", "Objective")
    b.obj("auth-v", "Authority", kind="policy", grantedBy="hum-v")
    b.obj("sub-v", "Subject", sha=_sha("vacuous-subject"), repository="repo-v")
    E = lambda *rels: [("episode", ep), *rels]  # noqa: E731
    t += SECOND
    b.event(
        "v-pre",
        "human.intervene",
        t,
        E(("originAuthority", hum), ("output", "obj-v"), ("output", "auth-v")),
    )
    t += SECOND
    b.event(
        "v-start",
        "episode.start",
        t,
        E(("subject", "sub-v"), ("input", "obj-v"), ("input", "auth-v")),
    )
    for i in range(iterations):
        b.obj(f"v-ev-{i}", "Evidence")
        t += SECOND
        if i == 0:
            b.event(
                "v-observe-0", "observe", t, E(("input", "obj-v"), ("output", "v-ev-0"))
            )
        else:
            b.event(
                f"v-reobserve-{i}",
                "reobserve",
                t,
                E(("cause", f"v-rcpt-{i - 1}"), ("output", f"v-ev-{i}")),
            )
        b.obj(f"v-wo-{i}", "WorkOrder")
        t += SECOND
        b.event(
            f"v-issue-{i}",
            "workorder.issue",
            t,
            E(
                ("cause", f"v-ev-{i}"),
                ("output", f"v-wo-{i}"),
                ("originAuthority", "auth-v"),
            ),
        )
        b.obj(f"v-rcpt-{i}", "Receipt", digest=_sha(f"v-rcpt-{i}"))
        t += SECOND
        b.event(
            f"v-receipt-{i}",
            "receipt.persist",
            t,
            E(("input", f"v-wo-{i}"), ("output", f"v-rcpt-{i}"), ("subject", "sub-v")),
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
        "vacuous_no_actuation": (
            build_vacuous_loop(),
            {"exit": 3, "class": "FAILED", "code": "NO_ACTUATION"},
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
