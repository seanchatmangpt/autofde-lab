def migrate_v1(data):
    if data.get("schema") != "autofde-lab.ptd.experiment/v1":
        raise ValueError("not v1")
    return {
        "schema": "autofde-lab.ptd.campaign/v2",
        "experiment_id": data["experiment_id"],
        "subject_id": data.get("subject_id", "legacy:" + data["experiment_id"]),
        "epochs": data.get("epochs", []),
        "attacks": data.get("trials", []),
        "criteria": data.get("criteria", {}),
        "migrated_from": "v1",
    }
