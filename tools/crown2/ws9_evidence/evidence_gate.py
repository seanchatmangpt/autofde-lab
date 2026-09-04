#!/usr/bin/env python3
"""
evidence_gate.py <refs.json> [--ocel <log.ocel.json>] [--json]

refs.json is either:
  {"refs": [ {identity, durable_path, sha256, parser, receipt_path?}, ... ]}
or a claim:
  {"claim_id": "...", "text": "...", "refs": [ ... ]}

Resolves every ref against the real filesystem. Prints one line per ref plus
a verdict line. Exit 0 only if every ref RESOLVED (i.e. standing may be issued).

--ocel <log>: append EvidenceArtifact objects and EvidenceResolved /
EvidenceRefused events to an existing OCEL v2 log via tools/ocel_v2/emitter.py
(the log must already be init'ed). Object/event ids are derived from the ref
identity + sha256 so re-running against the same log is a hard error, not a
silent duplicate — append-only stays honest.
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "ocel_v2")))

from evidence import Claim, EvidenceRef, standing  # noqa: E402


def _emit_ocel(log_path: str, st) -> None:
    import emitter  # tools/ocel_v2/emitter.py

    by_identity = {r.identity: r for r in st.resolutions}
    for res in st.resolutions:
        ref = by_identity[res.identity]
        oid = f"evidence:{res.identity}"
        emitter.add_object(log_path, "EvidenceArtifact", oid, {
            "identity": res.identity,
            "durable_path": next((c.detail.get("path", "") for c in res.checks if c.check == "DurabilityCheck"), ""),
            "sha256": next((c.detail.get("expected", "") for c in res.checks if c.check == "DigestCheck"), ""),
            "parser": next((c.detail.get("parser", "") for c in res.checks if c.check == "ReplayCheck"), ""),
        })
        if res.resolved:
            emitter.add_event(log_path, "EvidenceResolved", f"evres:{res.identity}",
                              {"identity": res.identity}, [oid])
        else:
            failed = next(c for c in res.checks if not c.ok)
            emitter.add_event(log_path, "EvidenceRefused", f"evref:{res.identity}",
                              {"identity": res.identity, "check": failed.check, "reason": failed.reason}, [oid])


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    flags = [a for a in argv[1:] if a.startswith("--")]
    if len(args) < 1:
        print(__doc__)
        return 2
    refs_path = args[0]
    ocel_path = args[1] if "--ocel" in flags and len(args) > 1 else None
    as_json = "--json" in flags

    with open(refs_path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    if "claim_id" in doc:
        claim = Claim.from_dict(doc)
    else:
        claim = Claim("gate", "", tuple(EvidenceRef.from_dict(r) for r in doc.get("refs", [])))

    st = standing(claim)

    if as_json:
        print(json.dumps(st.to_dict(), indent=2))
    else:
        for res in st.resolutions:
            last = res.checks[-1] if res.checks else None
            extra = f"  ({last.check}: {last.reason})" if last and not last.ok else ""
            print(f"{res.status:<55} {res.identity}{extra}")
        print(f"VERDICT claim={claim.claim_id} issued={st.issued} status={st.status}")

    if ocel_path:
        _emit_ocel(ocel_path, st)
        print(f"ocel: appended {len(st.resolutions)} EvidenceArtifact object(s) + event(s) to {ocel_path}")

    return 0 if st.issued else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
