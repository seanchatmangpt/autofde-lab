#!/usr/bin/env python3
"""Aggregate per-model TLC court outputs into the release crown receipt.

Input: a directory produced by running, on an exact subject tree,

    python -m autofde_lab.iec tlc-court --model <m> --out <DIR>/<slug> > <DIR>/<slug>.summary.json

for ``brce`` and every ``mutant:<KIND>`` in ``brce_mutants.EXPECTED_VIOLATION``,
plus ``runs.tsv`` (model, slug, exit code) and optionally ``pytest.log`` /
``pytest.exit`` from the real court test suite.

Output: ``release/<version>/receipts/tlc-court.json`` in the shape the
chatman-ecosystem root crown ``receipt_artifact`` evaluator reads
(``standing`` + 40-hex ``subject_sha``). Standing is derived, never asserted:

- ALIVE iff the jar digest equals the pinned digest, every model parses
  (SANY) and reaches MODEL_CHECK_ALIVE, the reference holds every property in
  bound, and every mutant yields COUNTEREXAMPLE_FOUND on its expected property
  with an OCEL counterexample whose file digest matches the receipt.
- REFUSED otherwise (a mutant surviving is ``admission_vacuous``).

FORMAL_PROOF stays UNSUPPORTED(tlaps): TLC is bounded model checking, not proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

MUTANT_EXPECTED = {
    "DO_WITHOUT_AUTHORITY": "ExecutedRequiresAuthority",
    "DUPLICATE_CONSEQUENCE": "AtMostOneConsequence",
    "STANDING_WITHOUT_VERIFY": "NoStandingWithoutVerification",
    "NO_FAIRNESS": "AdmittedEventuallyTerminal",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def build(out_dir: Path, subject_sha: str, pinned_sha256: str, repo: str) -> dict:
    runs = [
        line.split("\t")
        for line in (out_dir / "runs.tsv").read_text().splitlines()
        if line.strip()
    ]
    refusals: list[str] = []
    models: list[dict] = []
    jar_digests: set[str] = set()
    java_versions: set[str] = set()
    tool_versions: set[str] = set()
    for model, slug, exit_code in runs:
        rdir = out_dir / slug
        receipt_path = rdir / "receipt.json"
        summary_path = out_dir / f"{slug}.summary.json"
        receipt = json.loads(receipt_path.read_text())
        jar_digests.add(receipt.get("jar_sha256"))
        java_versions.add(receipt.get("java_version"))
        tool_versions.add(receipt.get("tool_version"))
        verdicts = {p["name"]: p["verdict"] for p in receipt["properties"]}
        props = []
        for p in receipt["properties"]:
            entry = {
                "name": p["name"],
                "kind": p["kind"],
                "verdict": p["verdict"],
                "exit_code": p["exit_code"],
                "distinct_states": p["distinct_states"],
                "states_generated": p["states_generated"],
                "depth": p["depth"],
                "config_digest": p["config_digest"],
                "stdout_digest": p["stdout_digest"],
            }
            cx = p.get("counterexample")
            if cx:
                ocel_file = rdir / f"counterexample.{p['name']}.ocel.json"
                entry["counterexample"] = {
                    "violation": cx["violation"],
                    "length": cx["length"],
                    "loop": cx["loop"],
                    "actions": cx["actions"],
                    "transition_trace_digest": cx["transition_trace_digest"],
                    "ocel_digest": cx["ocel_digest"],
                    "ocel_file_sha256": sha256_file(ocel_file)
                    if ocel_file.is_file()
                    else None,
                }
                if not ocel_file.is_file():
                    refusals.append(f"{model}:{p['name']}:OCEL_FILE_ABSENT")
            props.append(entry)
        if receipt["parse"]["verdict"] != "MODEL_PARSE_ALIVE":
            refusals.append(f"{model}:PARSE:{receipt['parse']['verdict']}")
        if receipt["model_check"] != "MODEL_CHECK_ALIVE" or exit_code != "0":
            refusals.append(
                f"{model}:MODEL_CHECK:{receipt['model_check']}:exit={exit_code}"
            )
        if model == "brce":
            role, expected = "reference", None
            bad = sorted(
                k for k, v in verdicts.items() if v != "PROPERTY_HOLDS_IN_BOUND"
            )
            if bad:
                refusals.append(f"reference:PROPERTY_VIOLATED:{','.join(bad)}")
            killed = None
        else:
            role = "mutant"
            kind = model.split(":", 1)[1]
            expected = MUTANT_EXPECTED.get(kind)
            killed = (
                expected is not None
                and verdicts.get(expected) == "COUNTEREXAMPLE_FOUND"
            )
            if not killed:
                refusals.append(f"{model}:MUTANT_SURVIVED:{expected}:admission_vacuous")
        models.append(
            {
                "model": model,
                "role": role,
                "module": receipt["model"],
                "expected_violation": expected,
                "killed": killed,
                "cli_exit_code": int(exit_code),
                "parse": receipt["parse"]["verdict"],
                "sany_exit_code": receipt["parse"]["exit_code"],
                "model_check": receipt["model_check"],
                "spec_digest": receipt["spec_digest"],
                "properties": props,
                "per_model_receipt_digest": receipt["receipt_digest"],
                "per_model_receipt_file_sha256": sha256_file(receipt_path),
                "replay_identity": receipt["replay"]["identity_digest"],
                "summary_sha256": sha256_file(summary_path),
                "bounds": receipt["bounds"],
            }
        )
    covered = {m["model"].split(":", 1)[1] for m in models if m["role"] == "mutant"}
    missing = sorted(set(MUTANT_EXPECTED) - covered)
    if missing:
        refusals.append(f"MUTANTS_NOT_RUN:{','.join(missing)}")
    if not any(m["role"] == "reference" for m in models):
        refusals.append("REFERENCE_NOT_RUN")
    if jar_digests != {pinned_sha256}:
        refusals.append(f"JAR_DIGEST_MISMATCH:{sorted(map(str, jar_digests))}")
    tests = None
    if (out_dir / "pytest.log").is_file():
        exit_line = (out_dir / "pytest.exit").read_text().strip()
        tests = {
            "command": "AUTOFDE_TLC_REQUIRED=1 python -m pytest -q -o addopts= -rs "
            "tests/iec/test_tlc_court.py tests/iec/test_tlc_transcript.py "
            "tests/iec/test_tla_projection_fairness.py tests/iec/test_graph_protocol_tla.py "
            "tests/iec/test_frontier_formal.py",
            "exit_code": int(exit_line.split("=")[1]),
            "summary": (out_dir / "pytest.log").read_text().strip().splitlines()[-1],
            "output_sha256": sha256_file(out_dir / "pytest.log"),
        }
        if tests["exit_code"] != 0:
            refusals.append(f"COURT_TESTS_FAILED:exit={tests['exit_code']}")
    standing = "ALIVE" if not refusals else "REFUSED"
    body = {
        "schema": "autofde-lab/release-tlc-court-receipt/v1",
        "release": "v26.9.25",
        "requirements": ["AC-07", "F-08"],
        "repository": repo,
        "subject_sha": subject_sha,
        "subject_note": "evaluated commit = parent of the receipt commit (a commit cannot contain its own hash)",
        "standing": standing,
        "type": None if standing == "ALIVE" else "TLC_COURT_REFUSED",
        "refusals": refusals,
        "toolchain": {
            "tla2tools_release": "1.7.4",
            "jar_sha256": sorted(map(str, jar_digests))[0]
            if len(jar_digests) == 1
            else None,
            "jar_sha256_pinned": pinned_sha256,
            "jar_sha256_pin_file": "tools/tla/tla2tools-1.7.4.sha256",
            "jar_digest_matches_pin": jar_digests == {pinned_sha256},
            "tool_version": sorted(map(str, tool_versions)),
            "java_version": sorted(map(str, java_versions)),
        },
        "command": "for m in brce mutant:DO_WITHOUT_AUTHORITY mutant:DUPLICATE_CONSEQUENCE "
        "mutant:STANDING_WITHOUT_VERIFY mutant:NO_FAIRNESS; do "
        "python -m autofde_lab.iec tlc-court --model $m --out <DIR>/<slug>; done",
        "models": models,
        "court_tests": tests,
        "formal_proof": {
            "verdict": "UNSUPPORTED",
            "reason": "UNSUPPORTED(formal-proof-runtime:tlaps-not-installed)",
        },
        "authority": "NONE",
        "evidence_ceiling": "Bounded explicit-state model check of the projected BRCE TLA+ model "
        "and its four mutants by pinned TLC; not a proof, not evidence about any production "
        "implementation.",
    }
    body["output_sha256"] = hashlib.sha256(canonical(body).encode()).hexdigest()
    return body


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--court-out", required=True, type=Path)
    ap.add_argument("--subject-sha", required=True)
    ap.add_argument(
        "--pin-file", default=Path("tools/tla/tla2tools-1.7.4.sha256"), type=Path
    )
    ap.add_argument("--repository", default="seanchatmangpt/autofde-lab")
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args(argv)
    if len(args.subject_sha) != 40:
        raise SystemExit("subject sha must be 40 hex characters")
    pinned = args.pin_file.read_text().split()[0]
    body = build(args.court_out, args.subject_sha, pinned, args.repository)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    print(
        canonical(
            {
                "standing": body["standing"],
                "refusals": body["refusals"],
                "output_sha256": body["output_sha256"],
            }
        )
    )
    return 0 if body["standing"] == "ALIVE" else 2


if __name__ == "__main__":
    sys.exit(main())
