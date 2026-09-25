# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""RECONSTRUCTED ALOOP NDJSON fixture corpus for the metrics calculator.

``python benchmarks/aloop/fixtures/generate_fixtures.py`` regenerates every
file in this directory byte for byte (and ``SOURCES.json``). The fixtures are
RECONSTRUCTED: synthetic by construction, a falsifier corpus that lets the
calculator run today, never evidence that any real system is autonomous.

Contents
--------
``positive-60.ocel.ndjson``       closed loop, 60 iterations; the crash window
                                  at iteration 40 fires and is machine-reconciled
                                  (CRR=1 witnessed); provider extinction at 70
                                  does NOT fire here.
``human-after-epoch-60.ocel.ndjson``
                                  negative control: a planted post-epoch human
                                  edge must classify ASSISTED.
``fixed-task-cron-30.ocel.ndjson``
                                  negative control: severed recurrence
                                  (cron-shaped work orders) must fail
                                  ALOOP-001 with AUTOMATION_NOT_AUTONOMY.
``provider-renamed-20.ocel.ndjson``
                                  the 20-iteration loop with provider
                                  ``claude`` renamed to ``ollama``: the PDR
                                  counterpart of ``synth.build_positive(20)``
                                  (regenerate that on the fly to score the
                                  pair -- semantic signature must be equal,
                                  PDR=0; only names/capacity may differ).
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _rename_provider(doc: dict, old: str, new: str) -> dict:
    doc = copy.deepcopy(doc)
    for obj in doc["objects"]:
        if obj["id"] == old:
            obj["id"] = new
        for attr in obj.get("attributes", []):
            if attr.get("value") == old:
                attr["value"] = new
    for ev in doc["events"]:
        for rel in ev.get("relationships", []):
            if rel.get("objectId") == old:
                rel["objectId"] = new
    return doc


def build_all(out: Path) -> dict:
    # imports deferred so the script bootstraps its own src path
    if str(REPO_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "src"))
    from autofde_lab.aloop.metrics import load_profile, to_ndjson
    from autofde_lab.aloop.synth import (
        build_fixed_task_cron,
        build_positive,
        m_human_after_epoch,
    )

    profile = load_profile()
    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict] = {}

    def emit(name: str, document: dict, note: str) -> None:
        data = to_ndjson(document)
        (out / name).write_bytes(data)
        files[name] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "note": note,
        }

    emit(
        "positive-60.ocel.ndjson",
        build_positive(iterations=60),
        "closed loop, crash window at 40 machine-reconciled; RECONSTRUCTED",
    )
    human_doc = build_positive(iterations=60)
    m_human_after_epoch(human_doc)
    emit(
        "human-after-epoch-60.ocel.ndjson",
        human_doc,
        "negative control: planted post-epoch human edge -> ASSISTED; RECONSTRUCTED",
    )
    emit(
        "fixed-task-cron-30.ocel.ndjson",
        build_fixed_task_cron(runs=30),
        "negative control: severed recurrence -> AUTOMATION_NOT_AUTONOMY; RECONSTRUCTED",
    )
    emit(
        "provider-renamed-20.ocel.ndjson",
        _rename_provider(build_positive(iterations=20), "prov-claude", "prov-ollama"),
        "PDR counterpart of synth.build_positive(iterations=20) with the "
        "execution provider renamed; semantic signature must be equal; RECONSTRUCTED",
    )
    sources = {
        "status": "RECONSTRUCTED",
        "note": (
            "synthetic falsifier corpus for the ALOOP metrics calculator; "
            "regenerate byte-for-byte with generate_fixtures.py; not evidence "
            "about any real system"
        ),
        "generator": "python benchmarks/aloop/fixtures/generate_fixtures.py",
        "profile_sha": json.dumps(profile["profile"], sort_keys=True),
        "files": files,
    }
    (out / "SOURCES.json").write_text(json.dumps(sources, indent=2, sort_keys=True) + "\n")
    return sources


if __name__ == "__main__":
    print(json.dumps(build_all(Path(__file__).resolve().parent), indent=2, sort_keys=True))
