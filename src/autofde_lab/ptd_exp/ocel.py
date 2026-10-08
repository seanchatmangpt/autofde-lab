"""OCEL 2.0 projection of a PTD evaluation via the canonical ``autofde_lab.ocel`` log.

Timestamps are event ordinals, not wall-clock, so the projection is replay-stable.
"""

from __future__ import annotations

from autofde_lab.ocel import OcelAttribute, OcelAttributeValue, OcelLog, OcelObject


def project_ocel(subject_id, experiment_id, epochs, attack_rows) -> OcelLog:
    """``epochs``: ordered epoch ids. ``attack_rows``: dicts with task_id/source_epoch/target_epoch/status."""
    log = OcelLog().with_objects(
        OcelObject(subject_id, "PTDSubject"),
        OcelObject(experiment_id, "PTDExperiment"),
        *[OcelObject(e, "PTDEpoch") for e in epochs],
        *[OcelObject(r["task_id"], "PTDAttack") for r in attack_rows],
    )
    tick = 0
    for e in epochs:
        tick += 1
        log = log.append_event(
            f"admit:{e}",
            "AdmitEpoch",
            [(subject_id, "subject"), (e, "epoch"), (experiment_id, "experiment")],
            timestamp_ns=tick,
        )
    for r in attack_rows:
        tick += 1
        log = log.append_event(
            f"attack:{r['task_id']}",
            "EvaluateAttack",
            [
                (r["task_id"], "attack"),
                (r["source_epoch"], "source"),
                (r["target_epoch"], "target"),
                (experiment_id, "experiment"),
            ],
            timestamp_ns=tick,
            attributes=[
                OcelAttribute("status", OcelAttributeValue.string(r["status"]))
            ],
        )
    return log.validate()
