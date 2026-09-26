"""Run-level verifier: bind report.json, ocel/*.json and ledger.jsonl together.

``verify_ledger`` proves the hash chain and HMACs only. It cannot see an OCEL
file edited on disk, a report edited on disk, or a ledger whose tail was cut
(the chain of a prefix is still a valid chain). ``verify_run`` closes those:

* every ledger record's ``data_fingerprint`` equals the sha256 of its OCEL file,
  and there is exactly one OCEL file per record;
* the ledger's record count and tail digest equal the anchor in report.json
  (external anchor against tail truncation);
* report.json's ``report_digest`` recomputes from its body;
* with ``replay=True`` the whole run is re-executed from the report's own
  parameters and every artifact must be byte/field identical.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from autofde_lab._cache.provenance import AttestationSigner
from autofde_lab.simulation.fortune5_safe.model import stable_digest

from .catalog import CatalogIntegrityError, load_catalog
from .matrix import run_doctrine_matrix
from .ocel import episode_log, log_bytes, ocel_filename
from .report import build_report, report_body
from .seal import OBSERVED_AT, key_provenance, signer_from_env, verify_ledger
from .world import world_by_id

SUBJECT_PREFIX = "doctrine-lab:"


@dataclass(frozen=True)
class RunVerification:
    valid: bool
    records: int
    failures: tuple[str, ...]


def _ledger_attestations(ledger_path: Path) -> list[dict]:
    rows = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line)["signed_attestation"]["attestation"])
    return rows


def _ledger_key_ids(ledger_path: Path) -> set[str]:
    return {
        str(json.loads(line)["signed_attestation"]["key_id"])
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def verify_run(
    out_dir: Path | str,
    *,
    replay: bool = False,
    signer: AttestationSigner | None = None,
) -> RunVerification:
    out = Path(out_dir)
    failures: list[str] = []
    ledger_path = out / "ledger.jsonl"
    report_path = out / "report.json"
    ocel_dir = out / "ocel"
    for required in (ledger_path, report_path, ocel_dir):
        if not required.exists():
            return RunVerification(False, 0, (f"missing {required.name}",))

    signer = signer or signer_from_env()
    chain = verify_ledger(ledger_path, signer=signer)
    if not chain.valid:
        failures.append(f"ledger chain invalid: {chain.error}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    anchor = report.get("ledger") or {}
    if anchor.get("records") != chain.records:
        failures.append(
            f"ledger records {chain.records} != report anchor {anchor.get('records')}"
        )
    if anchor.get("tail_digest") != chain.tail_digest:
        failures.append("ledger tail digest != report anchor")
    expected_key = key_provenance(signer)
    for field, value in expected_key.items():
        if anchor.get(field) != value:
            failures.append(
                f"report anchor {field} {anchor.get(field)!r} != verifying key {value!r}"
            )
    if stable_digest(report_body(report)) != report.get("report_digest"):
        failures.append("report_digest does not recompute from report body")

    attestations = _ledger_attestations(ledger_path)
    key_ids = _ledger_key_ids(ledger_path)
    if key_ids - {expected_key["key_id"]}:
        failures.append(
            f"ledger sealed by {sorted(key_ids)} not {expected_key['key_id']}"
        )
    expected_files: set[str] = set()
    for att in attestations:
        subject = str(att.get("subject_id", ""))
        if not subject.startswith(SUBJECT_PREFIX):
            failures.append(f"foreign subject {subject!r}")
            continue
        if att.get("observed_at") != OBSERVED_AT:
            failures.append(f"{subject} observed_at is not pinned to {OBSERVED_AT}")
        name = ocel_filename(subject[len(SUBJECT_PREFIX) :])
        expected_files.add(name)
        path = ocel_dir / name
        if not path.exists():
            failures.append(f"missing ocel/{name}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if att.get("data_fingerprint") != f"ocel:{digest}":
            failures.append(f"ocel/{name} does not match its ledger fingerprint")
        if att.get("release_id") != f"catalog:{report['catalog']['sha256']}":
            failures.append(f"{subject} release_id does not bind the report catalog")
    present = {p.name for p in ocel_dir.iterdir() if p.is_file()}
    for extra in sorted(present - expected_files):
        failures.append(f"ocel/{extra} is not bound by any ledger record")
    if report.get("episode_count") != len(attestations):
        failures.append("report episode_count != ledger records")

    if replay and not failures:
        failures.extend(_replay(report, ocel_dir, attestations))
    return RunVerification(not failures, chain.records, tuple(failures))


def _replay(report: dict, ocel_dir: Path, attestations: list[dict]) -> list[str]:
    failures: list[str] = []
    try:
        catalog = load_catalog(expected_sha256=report["catalog"]["sha256"])
    except CatalogIntegrityError as exc:
        return [f"replay: catalog refused: {exc}"]
    strategies = [catalog.get(int(i.split("-")[1])) for i in report["strategy_ids"]]
    worlds = [world_by_id(w) for w in report["world_ids"]]
    result = run_doctrine_matrix(
        report["seeds"], worlds, strategies, catalog=catalog, rounds=report["rounds"]
    )
    rebuilt = json.loads(json.dumps(build_report(result, catalog), sort_keys=True))
    if report_body(rebuilt) != report_body(report):
        failures.append("replay: report body differs from re-execution")
    if len(result.episodes) != len(attestations):
        failures.append("replay: episode count differs from ledger")
    for episode, att in zip(result.episodes, attestations):
        if att.get("subject_id") != f"{SUBJECT_PREFIX}{episode.id}":
            failures.append(f"replay: ledger order differs at {episode.id}")
            continue
        if att.get("value_digest") != episode.receipt.episode_digest:
            failures.append(f"replay: {episode.id} episode digest differs")
        path = ocel_dir / ocel_filename(episode.id)
        if path.read_bytes() != log_bytes(episode_log(episode)):
            failures.append(f"replay: ocel/{path.name} differs from re-execution")
    return failures
