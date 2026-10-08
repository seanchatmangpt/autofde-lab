"""Doctrine boundary lab: sd: strategies x 243 worlds over the fortune5_safe model.

Model-only (evidence ceiling REPO_LOCAL_FIXTURE), authority NONE, ceiling CONSTRUCT.
Nothing here selects, admits or actuates; receipts bind simulated consequences only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from .catalog import (
    CATALOG_SHA256,
    Catalog,
    CatalogIntegrityError,
    Strategy,
    is_admitted,
    load_catalog,
)
from .matrix import (
    EVIDENCE_CEILING,
    DoctrineMatrixResult,
    EpisodeRecord,
    ProvenanceRefused,
    run_doctrine_matrix,
    run_strategy_episode,
    wilson,
)
from .ocel import episode_log, log_bytes, log_sha256, ocel_filename
from .primitives import BASE_POLICY, DUALS, PRIMITIVES, compose
from .report import build_report
from .seal import (
    SealKeyRefused,
    admit_for_seal,
    key_provenance,
    report_signature,
    seal_episodes,
    signer_from_env,
    verify_ledger,
)
from .verify import RunVerification, verify_run
from .world import ALL_WORLDS, World, world_by_id


def run_lab(
    out_dir: Path | str,
    *,
    seeds: Sequence[int],
    worlds: Sequence[World],
    ordinals: Sequence[int] | None = None,
    rounds: int = 3,
) -> dict[str, Any]:
    """Run the matrix and write report.json, ledger.jsonl and ocel/<episode>.json."""
    out = Path(out_dir)
    ocel_dir = out / "ocel"
    ocel_dir.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog()
    strategies = (
        tuple(catalog.get(o) for o in ordinals) if ordinals else catalog.operationalized
    )
    result = run_doctrine_matrix(
        seeds, worlds, strategies, catalog=catalog, rounds=rounds
    )
    sealed: list[tuple[EpisodeRecord, str]] = []
    for episode in result.episodes:
        document = episode_log(episode)
        (ocel_dir / ocel_filename(episode.id)).write_bytes(log_bytes(document))
        sealed.append((episode, log_sha256(document)))
    ledger_path = out / "ledger.jsonl"
    if ledger_path.exists():
        ledger_path.unlink()
    signer = signer_from_env()
    verification = seal_episodes(sealed, ledger_path, signer=signer)
    report = build_report(result, catalog)
    report["ledger"] = {
        "valid": verification.valid,
        "records": verification.records,
        "tail_digest": verification.tail_digest,
        "report_signature": report_signature(
            signer,
            report["report_digest"],
            verification.records,
            verification.tail_digest,
        ),
        **key_provenance(signer),
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


__all__ = [
    "ALL_WORLDS",
    "BASE_POLICY",
    "CATALOG_SHA256",
    "DUALS",
    "EVIDENCE_CEILING",
    "PRIMITIVES",
    "Catalog",
    "CatalogIntegrityError",
    "DoctrineMatrixResult",
    "EpisodeRecord",
    "ProvenanceRefused",
    "RunVerification",
    "SealKeyRefused",
    "Strategy",
    "World",
    "admit_for_seal",
    "build_report",
    "compose",
    "episode_log",
    "is_admitted",
    "key_provenance",
    "load_catalog",
    "log_bytes",
    "log_sha256",
    "ocel_filename",
    "run_doctrine_matrix",
    "run_lab",
    "report_signature",
    "run_strategy_episode",
    "seal_episodes",
    "signer_from_env",
    "verify_ledger",
    "verify_run",
    "wilson",
    "world_by_id",
]
