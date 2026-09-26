"""Run-level verifier: bind report.json, ocel/*.json and ledger.jsonl together.

``verify_ledger`` proves the hash chain and HMACs only. It cannot see an OCEL
file edited on disk, a report edited on disk, or a ledger whose tail was cut
(the chain of a prefix is still a valid chain). ``verify_run`` closes those:

* every ledger record's ``data_fingerprint`` equals the sha256 of its OCEL file,
  and there is exactly one OCEL file per record;
* the ledger's record count and tail digest equal the anchor in report.json
  (external anchor against tail truncation);
* report.json's ``report_digest`` recomputes from its body;
* report and every record carry authority NONE with a SELECT/CONSTRUCT ceiling,
  the lab evidence ceiling and ``selection`` None (no replay needed);
* the report's catalog digest is the admitted vendored catalog, and every
  record's subject resolves in it to an operationalized strategy of the run
  whose policy digest and signature-bound ``value_digest`` recompute from the
  catalog (a forged primitive composition is refused without replay);
* subjects are unique (duplicate delivery) and the keyed ``report_signature``
  binds report_digest, record count and tail digest under the ledger key;
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

from .catalog import Catalog, CatalogIntegrityError, load_catalog
from .matrix import EVIDENCE_CEILING, receipt_body, run_doctrine_matrix
from .ocel import episode_log, log_bytes, ocel_filename
from .report import build_report, report_body
from .seal import (
    AUTHORITY,
    CEILINGS,
    NAMESPACE,
    OBSERVED_AT,
    key_provenance,
    report_signature,
    signer_from_env,
    verify_ledger,
)
from .world import world_by_id

SUBJECT_PREFIX = "doctrine-lab:"


@dataclass(frozen=True)
class RunVerification:
    valid: bool
    records: int
    failures: tuple[str, ...]


def _ledger_rows(ledger_path: Path) -> list[dict]:
    rows = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("ledger row is not an object")
            rows.append(row["signed_attestation"])
    return rows


def parse_subject(subject: str) -> tuple[int, str, int]:
    """``doctrine-lab:sd-NN@<world>#s<seed>`` -> (ordinal, world_id, seed)."""
    body = subject[len(SUBJECT_PREFIX) :]
    strategy_id, rest = body.split("@", 1)
    world_id, seed = rest.rsplit("#s", 1)
    if not strategy_id.startswith("sd-"):
        raise ValueError(f"subject strategy {strategy_id!r} is not sd-")
    return int(strategy_id[3:]), world_id, int(seed)


def _check_authority(report: dict) -> list[str]:
    failures = []
    if report.get("authority") != AUTHORITY:
        failures.append(f"report authority {report.get('authority')!r} is not NONE")
    if report.get("authority_ceiling") not in CEILINGS:
        failures.append(
            f"report authority_ceiling {report.get('authority_ceiling')!r} "
            "is not SELECT/CONSTRUCT"
        )
    if report.get("selection") is not None:
        failures.append("report selection is not None")
    if report.get("evidence_ceiling") != EVIDENCE_CEILING:
        failures.append(
            f"report evidence_ceiling {report.get('evidence_ceiling')!r} "
            f"is not {EVIDENCE_CEILING}"
        )
    return failures


def _check_record(att: dict, subject: str, report: dict, catalog: Catalog) -> list[str]:
    failures = []
    owner = str(att.get("owner", ""))
    ceiling = owner.removeprefix(f"authority={AUTHORITY};ceiling=")
    if ceiling == owner or ceiling not in CEILINGS:
        failures.append(f"{subject} owner {owner!r} is not authority NONE <= CONSTRUCT")
    if att.get("namespace") != NAMESPACE:
        failures.append(f"{subject} namespace {att.get('namespace')!r} is foreign")
    if att.get("rollout_reason") != EVIDENCE_CEILING:
        failures.append(f"{subject} evidence ceiling is not {EVIDENCE_CEILING}")
    try:
        ordinal, world_id, seed = parse_subject(subject)
        strategy = catalog.get(ordinal)
    except (ValueError, KeyError) as exc:
        return failures + [f"{subject} does not resolve in the catalog: {exc}"]
    if strategy.status != "operationalized":
        failures.append(f"{subject} names stub ordinal {ordinal}")
        return failures
    if strategy.id not in report.get("strategy_ids", ()):
        failures.append(f"{subject} strategy is not in the report's strategy_ids")
    if world_id not in report.get("world_ids", ()):
        failures.append(f"{subject} world is not in the report's world_ids")
    if seed not in report.get("seeds", ()):
        failures.append(f"{subject} seed is not in the report's seeds")
    if att.get("policy_digest") != strategy.policy.digest:
        failures.append(f"{subject} policy_digest is not the catalog strategy's")
    expected_value = stable_digest(
        receipt_body(
            catalog.sha256, ordinal, strategy.signature, str(att.get("key_digest"))
        )
    )
    if att.get("value_digest") != expected_value:
        failures.append(
            f"{subject} value_digest does not bind the catalog signature "
            f"{strategy.signature!r}"
        )
    return failures


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

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("report.json is not an object")
        rows = _ledger_rows(ledger_path)
        attestations = [dict(r["attestation"]) for r in rows]
        key_ids = {str(r["key_id"]) for r in rows}
    except (ValueError, KeyError, TypeError) as exc:
        return RunVerification(
            False, chain.records, (*failures, f"malformed run artifact: {exc}")
        )
    failures.extend(_check_authority(report))
    anchor = report.get("ledger") or {}
    if not isinstance(anchor, dict):
        anchor = {}
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
    recomputed = stable_digest(report_body(report))
    if recomputed != report.get("report_digest"):
        failures.append("report_digest does not recompute from report body")
    expected_signature = report_signature(
        signer, recomputed, chain.records, chain.tail_digest
    )
    if anchor.get("report_signature") != expected_signature:
        failures.append("report_signature does not bind report body to the ledger key")

    catalog_meta = report.get("catalog") or {}
    catalog: Catalog | None = None
    try:
        catalog = load_catalog(expected_sha256=str(catalog_meta.get("sha256")))
    except CatalogIntegrityError as exc:
        failures.append(f"report catalog is not the admitted catalog: {exc}")

    if key_ids - {expected_key["key_id"]}:
        failures.append(
            f"ledger sealed by {sorted(key_ids)} not {expected_key['key_id']}"
        )
    expected_files: set[str] = set()
    seen_subjects: set[str] = set()
    for att in attestations:
        subject = str(att.get("subject_id", ""))
        if not subject.startswith(SUBJECT_PREFIX):
            failures.append(f"foreign subject {subject!r}")
            continue
        if subject in seen_subjects:
            failures.append(f"duplicate delivery of {subject}")
            continue
        seen_subjects.add(subject)
        if att.get("observed_at") != OBSERVED_AT:
            failures.append(f"{subject} observed_at is not pinned to {OBSERVED_AT}")
        if catalog is not None:
            failures.extend(_check_record(att, subject, report, catalog))
        name = ocel_filename(subject[len(SUBJECT_PREFIX) :])
        expected_files.add(name)
        path = ocel_dir / name
        if not path.exists():
            failures.append(f"missing ocel/{name}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if att.get("data_fingerprint") != f"ocel:{digest}":
            failures.append(f"ocel/{name} does not match its ledger fingerprint")
        if att.get("release_id") != f"catalog:{catalog_meta.get('sha256')}":
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
