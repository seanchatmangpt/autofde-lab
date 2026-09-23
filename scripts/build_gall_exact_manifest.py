#!/usr/bin/env python3
"""Build the immutable GALL-005 manifest from exact producer receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from autofde_lab.sa2a.gall.composition import (
    EvidenceReference,
    GALLCompositionManifest,
    ReceiptReference,
)

SEMANTIC_KEY = "sa2a:gall:v26.9.18:exact-chain"


def _head(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _copy(source: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def _corpus_identity(
    receipts: tuple[ReceiptReference, ...], evidence: tuple[EvidenceReference, ...]
) -> str:
    payload = [
        *(
            f"{r.checkpoint}|{r.repository}|{r.repo_sha}|{r.receipt_digest}"
            for r in receipts
        ),
        *(
            f"{e.evidence_class}|{e.repository}|{e.repo_sha}|{e.receipt_digest}"
            for e in evidence
        ),
    ]
    encoded = "\n".join(sorted(payload)).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gall-001", required=True)
    parser.add_argument("--gall-001-sha", required=True)
    parser.add_argument("--gall-002", required=True)
    parser.add_argument("--gall-002-sha", required=True)
    parser.add_argument("--gall-003", required=True)
    parser.add_argument("--gall-003-sha", required=True)
    parser.add_argument("--gall-004", required=True)
    parser.add_argument("--gall-004-sha", required=True)
    parser.add_argument("--weaver", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    out_dir = Path(args.out_dir)
    evidence_dir = out_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    g1 = _copy(args.gall_001, evidence_dir / "GALL-001.json")
    g2 = _copy(args.gall_002, evidence_dir / "GALL-002.json")
    g3 = _copy(args.gall_003, evidence_dir / "GALL-003.json")
    g4 = _copy(args.gall_004, evidence_dir / "GALL-004.json")
    weaver = _copy(args.weaver, evidence_dir / "GALL-004-TELEMETRY.json")

    # Receipt paths are transport locators, but they participate in the
    # composition manifest identity. Bind them relative to the exact
    # autofde-lab checkout so replay is independent of runner workspace path.
    g1_ref = g1.relative_to(repo_root)
    g2_ref = g2.relative_to(repo_root)
    g3_ref = g3.relative_to(repo_root)
    g4_ref = g4.relative_to(repo_root)
    weaver_ref = weaver.relative_to(repo_root)

    receipts = (
        ReceiptReference.from_path(
            checkpoint="GALL-001",
            repository="seanchatmangpt/ggen",
            repo_sha=args.gall_001_sha,
            path=g1_ref,
        ),
        ReceiptReference.from_path(
            checkpoint="GALL-002",
            repository="seanchatmangpt/ggen_igniter",
            repo_sha=args.gall_002_sha,
            path=g2_ref,
        ),
        ReceiptReference.from_path(
            checkpoint="GALL-003",
            repository="seanchatmangpt/ash_a2a",
            repo_sha=args.gall_003_sha,
            path=g3_ref,
        ),
        ReceiptReference.from_path(
            checkpoint="GALL-004",
            repository="seanchatmangpt/beam4pm",
            repo_sha=args.gall_004_sha,
            path=g4_ref,
        ),
    )
    supporting = (
        EvidenceReference.from_path(
            evidence_class="GALL-004-TELEMETRY",
            repository="seanchatmangpt/beam4pm",
            repo_sha=args.gall_004_sha,
            path=weaver_ref,
        ),
    )

    head = _head(repo_root)
    manifest = GALLCompositionManifest(
        schema="autofde.gall.composition/v26.9.18",
        receipts=receipts,
        evidence=supporting,
        autofde_lab_sha=head,
        planner_identity=f"autofde-lab@{head}:FOND-HDDL",
        cmca_identity=f"autofde-lab@{head}:CMCA",
        machine_experience_compiler_identity=f"autofde-lab@{head}:MachineExperienceCompiler",
        corpus_identity=_corpus_identity(receipts, supporting),
        semantic_key=SEMANTIC_KEY,
    )
    manifest.validate_shape()

    manifest_path = out_dir / "gall-composition-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n"
    )
    (out_dir / "deterministic-output.json").write_text(
        json.dumps(
            {
                "classification": "KNOWN",
                "route": "typed-receipt-chain",
                "authority": "none",
            },
            sort_keys=True,
        )
        + "\n"
    )
    print(
        json.dumps(
            {"composition_digest": manifest.digest, "semantic_key": SEMANTIC_KEY},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
