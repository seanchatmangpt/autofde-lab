# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Deterministic converter: chatman root-crown receipt chain -> ALOOP OCEL 2.0.

Input: the committed crown runs under
``git:seanchatmangpt/chatman-ecosystem@c599667a84ec79d832bb779bce1730b33b43fdd4:
release/v26.9.25/hardening/receipts/run-<id>/{crown-receipt,observations,
tag-decision}.json`` (copied byte for byte into the test fixtures, sha256 in
``SOURCES.json``).

Conversion rules -- each emitted event cites the field it is derived from; the
converter never invents a causal edge the inputs do not evidence:

* one Episode for the whole chain; ``episode.start`` at run 1's
  ``observed_at``, subject = run 1 ``crown_sha``, granted authority = the
  receipt's ``observation_authority``;
* run 1 ``observe``; run n>1 ``reobserve`` with ``cause`` = receipt[n-1]
  **only if** ``previous_receipt_digest`` equals receipt[n-1]'s
  ``receipt_digest`` (the evidenced feedback edge);
* non-machine observations carried in ``observations.local_worktrees`` become
  exogenous Evidence with ``origin`` = their ``authority`` (not produced by
  any loop event);
* ``verify`` (crown terms), ``gap.detect`` (typed ``remaining`` items as
  Failure objects), ``receipt.persist`` (crown receipt), ``verify`` (tag
  decision);
* a ``crown_sha`` change between runs is an evidenced consequence: emitted as
  ``commit`` with no cause (none is evidenced) and no receipt (none is in the
  admitted input set);
* ``tag.sha`` null -> set between runs is an evidenced consequence: emitted as
  ``actuate``; the tag decision's own ``authority`` text states tagging
  requires the release-crown environment approval, so the actuation's cause is
  a recorded ``human.intervene`` (human events are recorded, never hidden);
* times that the inputs only bound (commit, approval, tag) are placed at the
  midpoint of the evidenced interval and carry the bounds in ``basis``;
* no ``workorder.issue`` is emitted: none of the inputs names a WorkOrder.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from autofde_lab.aloop.court import load_profile
from autofde_lab.aloop.ocel_builder import Builder, dump
from autofde_lab.ocel.model import format_ns, parse_ns

RUN_IDS = ("36160116076", "36161744816", "36161856985")
SOURCE_COMMIT = "c599667a84ec79d832bb779bce1730b33b43fdd4"
SOURCE_REPO = "seanchatmangpt/chatman-ecosystem"
ROOT_REPO = "seanchatmangpt/chatman-ecosystem"


def locator(run_id: str, name: str) -> str:
    return (
        f"git:{SOURCE_REPO}@{SOURCE_COMMIT}:"
        f"release/v26.9.25/hardening/receipts/run-{run_id}/{name}"
    )


def _load(fixture_dir: Path, run_id: str, name: str) -> tuple[dict[str, Any], str]:
    raw = (fixture_dir / f"run-{run_id}" / name).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def convert(fixture_dir: Path) -> dict[str, Any]:
    profile = load_profile()
    b = Builder(profile["objectTypes"], profile["eventTypes"])
    runs = []
    for rid in RUN_IDS:
        crown, crown_sha256 = _load(fixture_dir, rid, "crown-receipt.json")
        obs, obs_sha256 = _load(fixture_dir, rid, "observations.json")
        tag, tag_sha256 = _load(fixture_dir, rid, "tag-decision.json")
        runs.append((rid, crown, crown_sha256, obs, obs_sha256, tag, tag_sha256))

    ep = b.obj("ep-chatman-root-crown-v26.9.25", "Episode")
    E = lambda *rels: [("episode", ep), *rels]  # noqa: E731
    b.obj("repo-chatman-ecosystem", "Repository")
    first = runs[0][1]

    def subject(sha: str) -> str:
        return b.obj(f"sub-{sha}", "Subject", sha=sha, repository=ROOT_REPO)

    auth = b.obj(
        "auth-observation",
        "Authority",
        kind="observation",
        grantedBy=first["observation_authority"],
    )
    b.obj("prov-github-actions", "Provider", name="github-actions")
    t_start = parse_ns(runs[0][3]["observed_at"])
    b.event(
        "start",
        "episode.start",
        t_start,
        E(("subject", subject(first["crown_sha"])), ("input", auth)),
    )

    prev = None
    for idx, (rid, crown, crown_sha256, obs, obs_sha256, tag, tag_sha256) in enumerate(
        runs
    ):
        t_obs = parse_ns(obs["observed_at"])
        t_eval = parse_ns(crown["evaluated_at"])
        if prev is not None:
            p_rid, p_crown, p_tag, p_obs = prev
            t_prev = parse_ns(p_crown["evaluated_at"])
            mid = (t_prev + t_obs) // 2
            bounds = f"({p_crown['evaluated_at']}, {obs['observed_at']})"
            if p_crown["crown_sha"] != crown["crown_sha"]:
                old, new = p_crown["crown_sha"], crown["crown_sha"]
                csq = b.obj(
                    f"csq-commit-{new}", "Consequence", key=f"commit:{ROOT_REPO}@{new}"
                )
                b.event(
                    f"commit-{new[:12]}",
                    "commit",
                    mid,
                    E(
                        ("subject", subject(old)),
                        ("consequence", csq),
                        ("output", subject(new)),
                    ),
                    basis=(
                        f"inferred: crown_sha {old} (run {p_rid}) -> {new} (run {rid}); "
                        f"time bounded {bounds}; no cause and no actuation receipt in the "
                        "admitted input set"
                    ),
                )
            p_tag_sha = p_obs["tag"]["sha"]
            tag_sha = obs["tag"]["sha"]
            if p_tag_sha is None and tag_sha is not None:
                hum = b.obj(
                    "hum-release-crown-reviewer",
                    "Human",
                    role="release-crown environment reviewer",
                )
                approval = b.obj(
                    "ev-release-crown-approval",
                    "Evidence",
                    origin="human",
                    locator=locator(rid, "tag-decision.json"),
                )
                b.event(
                    "human-release-crown-approval",
                    "human.intervene",
                    mid - 1,
                    E(("originAuthority", hum), ("output", approval)),
                    basis=(
                        f"tag-decision.authority={p_tag['authority']!r}; tag {obs['tag']['name']} "
                        f"sha null (run {p_rid}) -> {tag_sha} (run {rid}); time bounded {bounds}"
                    ),
                )
                csq_tag = b.obj(
                    f"csq-tag-{obs['tag']['name']}",
                    "Consequence",
                    key=f"tag:{ROOT_REPO}:{obs['tag']['name']}->{tag_sha}",
                )
                b.event(
                    f"actuate-tag-{obs['tag']['name']}",
                    "actuate",
                    mid,
                    E(
                        ("input", approval),
                        ("consequence", csq_tag),
                        ("subject", subject(tag_sha)),
                    ),
                    basis=f"observed tag creation; time bounded {bounds}; no actuation receipt in the admitted input set",
                )
        ev_obs = b.obj(
            f"ev-observations-{rid}",
            "Evidence",
            origin=obs["authority"],
            locator=locator(rid, "observations.json"),
            sha256=obs_sha256,
        )
        rels = [("output", ev_obs)]
        lw = obs.get("local_worktrees")
        if isinstance(lw, dict) and lw.get("sha256"):
            ext = b.obj(
                f"ev-local-worktrees-{lw['sha256'][:16]}",
                "Evidence",
                origin=str(lw.get("authority")),
                sha256=str(lw["sha256"]),
            )
            rels.append(("input", ext))
        if prev is None:
            b.event(f"observe-{rid}", "observe", t_obs, E(*rels))
        else:
            p_rid, p_crown, _, _ = prev
            if crown["previous_receipt_digest"] == p_crown["receipt_digest"]:
                rels.append(("cause", f"rcpt-{p_rid}"))
                b.event(f"reobserve-{rid}", "reobserve", t_obs, E(*rels))
            else:
                b.event(f"observe-{rid}", "observe", t_obs, E(*rels))
        b.obj(f"run-{rid}", "WorkerRun", run_id=rid)
        verdict = b.obj(
            f"ev-crown-terms-{rid}", "Evidence", origin="machine", sha256=crown_sha256
        )
        b.event(
            f"verify-crown-{rid}",
            "verify",
            t_eval,
            E(
                ("input", ev_obs),
                ("output", verdict),
                ("provider", "prov-github-actions"),
            ),
        )
        remaining = crown.get("remaining") or []
        if remaining:
            outs = []
            for item in remaining:
                outs.append(
                    (
                        "output",
                        b.obj(
                            f"fail-{rid}-{item['id']}",
                            "Failure",
                            code=str(item["code"]),
                            broken_term=str(item["broken_term"]),
                        ),
                    )
                )
            b.event(f"gap-{rid}", "gap.detect", t_eval, E(("cause", verdict), *outs))
        rcpt = b.obj(
            f"rcpt-{rid}",
            "Receipt",
            digest=crown["receipt_digest"],
            locator=locator(rid, "crown-receipt.json"),
        )
        b.event(
            f"receipt-{rid}",
            "receipt.persist",
            t_eval,
            E(
                ("input", verdict),
                ("output", rcpt),
                ("subject", subject(crown["crown_sha"])),
            ),
        )
        decision = b.obj(
            f"ev-tag-decision-{rid}",
            "Evidence",
            origin="machine",
            locator=locator(rid, "tag-decision.json"),
            sha256=tag_sha256,
        )
        b.event(
            f"verify-tag-{rid}",
            "verify",
            t_eval,
            E(("input", rcpt), ("output", decision)),
        )
        prev = (rid, crown, tag, obs)

    rid, crown, _, obs, _, tag, _ = runs[-1]
    if (
        crown["standing"] == "ALIVE"
        and tag["decision"] == "LEGAL"
        and obs["tag"]["sha"] == crown["crown_sha"]
    ):
        t_end = parse_ns(crown["evaluated_at"])
        b.event(
            "goal-satisfied",
            "goal.satisfied",
            t_end,
            E(("cause", f"ev-tag-decision-{rid}")),
        )
        b.event(
            "episode-terminal",
            "episode.terminal",
            t_end,
            E(("cause", f"ev-tag-decision-{rid}")),
        )
    doc = b.document()
    doc["events"].sort(
        key=lambda e: parse_ns(e["time"])
    )  # stable: preserves emit order on ties
    assert all(format_ns(parse_ns(e["time"])) == e["time"] for e in doc["events"])
    return doc


def main(argv: list[str]) -> int:
    fixture_dir, out = Path(argv[0]), Path(argv[1])
    dump(convert(fixture_dir), out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
