import hashlib
import json


def replay_key(subject_id, experiment_id, epochs):
    return hashlib.sha256(
        json.dumps(
            {
                "subject_id": subject_id,
                "experiment_id": experiment_id,
                "epochs": epochs,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def deterministic_report(report):
    return (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
