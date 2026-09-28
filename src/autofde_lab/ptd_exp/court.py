"""PTD experiment court: manifest -> admission -> per-attack verdicts -> campaign -> sealed, replayable report.

Every attack row is PASS, FALSIFIED (measured, with named falsifiers) or REFUSED (not
admissible, so *no* metric is computed -- a refusal is a result, not a gap to fill).
All verdicts are ``technicalStanding`` only; nothing here claims organizational standing.
"""

from __future__ import annotations

from .authority import AuthorityBoundary, admit_authority
from .common_mode import common_mode_persistence
from .economics import ptd_advantage, regeneration_advantage
from .identity import require_distinct_epochs, require_same_subject
from .manifest import manifest_digest, parse_manifest
from .models import PTDThresholds
from .ocel import project_ocel
from .predictor import normalized_prediction_error
from .report import seal_report
from .statistics import confidence_band, mean
from .temporal import strong_temporal_regime
from .transfer import knowledge_depreciation, knowledge_retention


def _refused(src, tgt, attack, reasons):
    return {
        "task_id": attack.task_id,
        "source_epoch": src.epoch_id,
        "target_epoch": tgt.epoch_id,
        "status": "REFUSED",
        "refusals": reasons,
        "falsifiers": [],
        "metrics": None,
    }


def _admission_refusals(src, tgt, attack, allowed):
    out = []
    try:
        require_same_subject(src.subject_id, tgt.subject_id)
    except ValueError:
        out.append("subject_mismatch")
    try:
        require_distinct_epochs(src.epoch_id, tgt.epoch_id)
    except ValueError:
        out.append("epoch_not_distinct")
    if (attack.source_epoch, attack.target_epoch) != (src.epoch_id, tgt.epoch_id):
        out.append("attack_epoch_binding_mismatch")
    if not (src.admitted and tgt.admitted):
        out.append("epoch_unadmitted")
    if src.semantic_digest != tgt.semantic_digest:
        out.append("semantic_drift")
    if src.realization_digest == tgt.realization_digest:
        out.append("realization_did_not_phase")
    if allowed:
        for e in (src, tgt):
            try:
                admit_authority(
                    AuthorityBoundary(e.subject_id, e.authority_id),
                    e.subject_id,
                    allowed,
                )
            except PermissionError:
                out.append(f"authority_refused:{e.epoch_id}")
    return out


def evaluate_epoch_pair(src, tgt, attack, t: PTDThresholds, allowed=()):
    refusals = _admission_refusals(src, tgt, attack, allowed)
    if refusals:
        return _refused(src, tgt, attack, refusals)

    retention = knowledge_retention(attack.stale_performance, attack.fresh_performance)
    adv = regeneration_advantage(attack.realignment_cost, tgt.defender_cost)
    # Structural evidence, independent of the measured performance.
    fact_retention = (
        len(attack.stale_facts & tgt.stable_surface) / len(tgt.stable_surface)
        if tgt.stable_surface
        else 0.0
    )
    common_mode = common_mode_persistence(src.stable_surface, tgt.stable_surface)
    persisted_critical = sorted(
        src.critical & tgt.critical & src.stable_surface & tgt.stable_surface
    )
    pred_err = normalized_prediction_error(attack.predicted_surface, tgt.stable_surface)

    falsifiers = []
    if retention > t.max_retention:
        # churn: surface changed yet attacker facts still cover it; otherwise performance
        # transferred through a channel the recorded surface does not explain.
        falsifiers.append(
            "churn_without_depreciation"
            if fact_retention > t.max_retention
            else "unexplained_transfer_channel"
        )
    elif abs(retention - fact_retention) > t.max_fact_disagreement:
        falsifiers.append("retention_evidence_disagree")
    if adv < t.min_regeneration_advantage:
        falsifiers.append("regeneration_advantage_too_low")
    if t.require_temporal_advantage and not strong_temporal_regime(
        attack.realignment_time, tgt.phase_duration
    ):
        falsifiers.append("attacker_realigns_within_phase")
    if common_mode > t.max_common_mode:
        falsifiers.append("common_mode_persisted")
    if persisted_critical:
        falsifiers.append("critical_fact_persisted")
    if src.authority_compromised or tgt.authority_compromised:
        falsifiers.append("persistent_authority_compromise")

    dep = knowledge_depreciation(attack.stale_performance, attack.fresh_performance)
    return {
        "task_id": attack.task_id,
        "source_epoch": src.epoch_id,
        "target_epoch": tgt.epoch_id,
        "status": "FALSIFIED" if falsifiers else "PASS",
        "refusals": [],
        "falsifiers": falsifiers,
        "persisted_critical": persisted_critical,
        "nondeterministic_surfaces": sorted(
            src.nondeterministic | tgt.nondeterministic
        ),
        "metrics": {
            "retention": retention,
            "depreciation": dep,
            "fact_retention": fact_retention,
            "regeneration_advantage": adv,
            "ptd_advantage": ptd_advantage(
                dep, attack.realignment_cost, tgt.defender_cost
            ),
            "common_mode": common_mode,
            "prediction_error": pred_err,
        },
    }


def evaluate_campaign(rows, epochs=(), t: PTDThresholds | None = None):
    measured = [r for r in rows if r["metrics"] is not None]
    retentions = [r["metrics"]["retention"] for r in measured]
    out = {
        "pair_count": len(rows),
        "pass_count": sum(r["status"] == "PASS" for r in rows),
        "falsified_count": sum(r["status"] == "FALSIFIED" for r in rows),
        "refused_count": sum(r["status"] == "REFUSED" for r in rows),
        "all_pass": bool(rows) and all(r["status"] == "PASS" for r in rows),
        "mean_retention": mean(retentions) if retentions else None,
        "retention_band_95": confidence_band(retentions),  # None == UNKNOWN (n<2)
    }
    if t is not None and t.budget is not None and epochs:
        spent, funded = 0.0, 0
        for e in epochs[1:]:
            if spent + e.defender_cost > t.budget:
                break
            spent += e.defender_cost
            funded += 1
        out["budget"] = {
            "funded_phases": funded,
            "required_phases": len(epochs) - 1,
            "exhausted": funded < len(epochs) - 1,
        }
        out["all_pass"] = out["all_pass"] and not out["budget"]["exhausted"]
    return out


def evaluate_experiment(manifest: dict) -> dict:
    """Deterministic: same manifest bytes -> same sealed report bytes."""
    epochs, attacks, t, allowed = parse_manifest(manifest)
    by_id = {e.epoch_id: e for e in epochs}
    if len(by_id) != len(epochs):
        raise ValueError("duplicate epoch ids")
    rows = []
    for a in attacks:
        src, tgt = by_id.get(a.source_epoch), by_id.get(a.target_epoch)
        if src is None or tgt is None:
            raise ValueError(f"attack {a.task_id} references an unknown epoch")
        rows.append(evaluate_epoch_pair(src, tgt, a, t, allowed))
    ocel = project_ocel(
        manifest["subject_id"],
        manifest["experiment_id"],
        [e.epoch_id for e in epochs],
        rows,
    )
    return seal_report(
        {
            "schema": "autofde-lab.ptd.report/v2",
            "experiment_id": manifest["experiment_id"],
            "subject_id": manifest["subject_id"],
            "manifest_sha256": manifest_digest(manifest),
            "ocel_sha256": ocel.digest(),
            "rows": rows,
            "campaign": evaluate_campaign(rows, epochs, t),
            "standing": {
                "court_verdict": "PASS"
                if rows and all(r["status"] == "PASS" for r in rows)
                else "NOT_PASS",
                "organizationalStanding": "UNKNOWN",
            },
        }
    )
