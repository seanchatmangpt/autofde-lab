from autofde_lab.ptd_exp.migration import migrate_v1


def test_migration():
    r = migrate_v1(
        {
            "schema": "autofde-lab.ptd.experiment/v1",
            "experiment_id": "x",
            "trials": [],
            "criteria": {},
        }
    )
    assert r["schema"].endswith("/v2")
