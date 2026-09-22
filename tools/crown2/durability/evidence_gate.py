#!/usr/bin/env python3
"""Crown-2 evidence durability gate.

An evidence reference is RESOLVED only if every check below passes, in order.
The first failing check names the refusal:

    identity  -> path is absolute, exists, is a regular file, non-empty
    durable   -> path is not under a scratch root (/tmp, /private/tmp,
                 /var/folders, $TMPDIR, the Claude scratchpad root)
    sha256    -> recomputed digest of the bytes on disk == expected digest
    parser    -> the declared parser accepts the bytes
                 json      : json.loads succeeds and yields an object/array
                 ocel      : json + tools/ocel_v2/validate.py reports 0/0/0
                 sha256    : text is "<64 hex>  <name>" (sha256sum format)
                 text      : bytes decode as UTF-8
                 markdown  : UTF-8 and first non-blank line starts with "# "

Any failure => "REFUSED[EVIDENCE_ARTIFACT_UNRESOLVABLE:<check>]".

This is the rule that stops "prior run not located on disk" (crown-run-v2)
from ever being cited as evidence again: a reference without a resolvable
durable artifact has no standing.

Library:
    resolve(ref) -> dict          ref = {"path", "sha256", "parser", ["name"]}
    gate_bundle(refs) -> dict     all refs; standing only if all RESOLVED
    sha256_file(path) -> str
    canonical_json(obj) -> bytes

CLI:
    python3 evidence_gate.py <path> [--sha256 HEX] [--parser json|ocel|...]
    python3 evidence_gate.py --refs refs.json      (list of ref dicts)
Exit 0 iff RESOLVED (or all RESOLVED for --refs).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_OCEL_V2 = os.path.normpath(os.path.join(_HERE, "..", "..", "ocel_v2"))

RESOLVED = "RESOLVED"
CHECK_ORDER = ("identity", "durable", "sha256", "parser")
_SHA_LINE = re.compile(r"^([0-9a-f]{64})\s+\*?\S.*$")


def refused(check: str) -> str:
    return f"REFUSED[EVIDENCE_ARTIFACT_UNRESOLVABLE:{check}]"


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scratch_roots() -> list[str]:
    roots = ["/tmp", "/private/tmp", "/var/folders", "/private/var/folders"]
    for env in ("TMPDIR", "TMP", "TEMP"):
        v = os.environ.get(env)
        if v:
            roots.append(v)
            roots.append(os.path.realpath(v))
    # Claude Code scratchpad convention: /private/tmp/claude-<uid>/... already
    # covered by /private/tmp; also cover ~/.cache/tmp style TMPDIRs above.
    return sorted({os.path.normpath(r).rstrip("/") or "/" for r in roots})


def _under(path: str, root: str) -> bool:
    p = os.path.normpath(path)
    r = os.path.normpath(root)
    return p == r or p.startswith(r + os.sep)


def is_durable_path(path: str) -> tuple[bool, str | None]:
    real = os.path.realpath(path)
    for root in scratch_roots():
        if _under(path, root) or _under(real, root):
            return False, root
    return True, None


def _parse(parser: str, data: bytes) -> tuple[bool, str]:
    try:
        if parser == "json":
            obj = json.loads(data.decode("utf-8"))
            return isinstance(obj, (dict, list)), "json:" + type(obj).__name__
        if parser == "ocel":
            sys.path.insert(0, _OCEL_V2)
            import validate as ocel_validate  # tools/ocel_v2/validate.py

            obj = json.loads(data.decode("utf-8"))
            if not isinstance(obj, dict):
                return False, "ocel:not-an-object"
            counts = ocel_validate.validate(obj)
            ok = all(v == 0 for v in counts.values())
            return ok, "ocel:" + json.dumps(counts, sort_keys=True)
        if parser == "sha256":
            text = data.decode("utf-8").strip()
            return bool(_SHA_LINE.match(text)), "sha256:" + text[:64]
        if parser == "text":
            data.decode("utf-8")
            return True, "text:utf-8"
        if parser == "markdown":
            text = data.decode("utf-8")
            first = next((ln for ln in text.splitlines() if ln.strip()), "")
            return first.startswith("# "), "markdown:" + first[:40]
        return False, f"unknown-parser:{parser}"
    except Exception as exc:  # noqa: BLE001 - parser failure is the finding
        return False, f"{parser}:{type(exc).__name__}:{exc}"[:200]


def resolve(ref: dict[str, Any]) -> dict[str, Any]:
    """Resolve one evidence reference. Never raises; returns a receipt."""
    path = str(ref.get("path", ""))
    expected = ref.get("sha256")
    parser = str(ref.get("parser", "text"))
    out: dict[str, Any] = {
        "name": ref.get("name") or os.path.basename(path),
        "path": path,
        "parser": parser,
        "expected_sha256": expected,
        "checks": {},
        "status": None,
    }

    def fail(check: str, detail: str) -> dict[str, Any]:
        out["checks"][check] = {"ok": False, "detail": detail}
        out["status"] = refused(check)
        return out

    # identity
    if not os.path.isabs(path):
        return fail("identity", "path-not-absolute")
    if not os.path.exists(path):
        return fail("identity", "path-does-not-exist")
    if not os.path.isfile(path):
        return fail("identity", "not-a-regular-file")
    size = os.path.getsize(path)
    if size == 0:
        return fail("identity", "empty-file")
    out["bytes"] = size
    out["checks"]["identity"] = {"ok": True, "detail": f"regular-file:{size}B"}

    # durable
    durable, root = is_durable_path(path)
    if not durable:
        return fail("durable", f"under-scratch-root:{root}")
    out["checks"]["durable"] = {"ok": True, "detail": os.path.realpath(path)}

    # sha256
    actual = sha256_file(path)
    out["actual_sha256"] = actual
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected or ""):
        return fail("sha256", "expected-digest-missing-or-malformed")
    if actual != expected:
        return fail("sha256", f"mismatch:expected={expected[:12]}..,actual={actual[:12]}..")
    out["checks"]["sha256"] = {"ok": True, "detail": actual}

    # parser
    with open(path, "rb") as fh:
        data = fh.read()
    ok, detail = _parse(parser, data)
    if not ok:
        return fail("parser", detail)
    out["checks"]["parser"] = {"ok": True, "detail": detail}
    out["status"] = RESOLVED
    return out


def gate_bundle(refs: list[dict[str, Any]]) -> dict[str, Any]:
    results = [resolve(r) for r in refs]
    unresolved = [r for r in results if r["status"] != RESOLVED]
    return {
        "gate": "crown2.evidence_durability",
        "scratch_roots": scratch_roots(),
        "artifacts": len(results),
        "resolved": len(results) - len(unresolved),
        "unresolved": [{"name": r["name"], "path": r["path"], "status": r["status"]} for r in unresolved],
        "standing": "ALIVE[ALL_EVIDENCE_RESOLVED_FROM_DURABLE_PATHS]" if not unresolved
        else f"REFUSED[EVIDENCE_ARTIFACT_UNRESOLVABLE:{len(unresolved)}_of_{len(results)}]",
        "results": results,
    }


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    if argv[0] == "--refs":
        with open(argv[1], encoding="utf-8") as fh:
            refs = json.load(fh)
        rep = gate_bundle(refs)
        print(json.dumps(rep, indent=2, sort_keys=True))
        return 0 if not rep["unresolved"] else 1
    ref: dict[str, Any] = {"path": argv[0], "parser": "text"}
    i = 1
    while i < len(argv):
        if argv[i] == "--sha256":
            ref["sha256"] = argv[i + 1]
            i += 2
        elif argv[i] == "--parser":
            ref["parser"] = argv[i + 1]
            i += 2
        else:
            i += 1
    if "sha256" not in ref and os.path.isfile(ref["path"]):
        # No expected digest given: bind to the current bytes so the receipt
        # records what was seen; a later re-run against a mutated file refuses.
        ref["sha256"] = sha256_file(ref["path"])
        ref["note"] = "expected_sha256 computed at call time (self-bound)"
    rep = resolve(ref)
    print(json.dumps(rep, indent=2, sort_keys=True))
    return 0 if rep["status"] == RESOLVED else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
