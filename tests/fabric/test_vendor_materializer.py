import subprocess

from autofde_lab.fabric.vendor_materialization import (
    VendorMaterializationState,
    audit_vendor,
)
from autofde_lab.fabric.vendor_materializer import materialize_vendor
from tests.fabric.test_vendor_materialization import git, make_superproject


def test_materializer_initializes_exact_gitlink_without_weakening_pin(tmp_path):
    parent, _, sha = make_superproject(tmp_path)
    git(parent, "submodule", "deinit", "-f", "--", "vendor/gyms/example")
    audit_before = audit_vendor(parent, "vendor/gyms/example", pinned_revision=sha)
    assert audit_before.state is VendorMaterializationState.PINNED_UNMATERIALIZED

    audit_after = materialize_vendor(
        parent,
        "vendor/gyms/example",
        pinned_revision=sha,
        allow_file_protocol=True,
    )
    assert audit_after.state is VendorMaterializationState.MATERIALIZED_EXACT
    assert audit_after.observed_revision == sha


def test_materializer_refuses_populated_parent_inheriting_directory(tmp_path):
    parent, _, sha = make_superproject(tmp_path)
    vendor = parent / "vendor/gyms/example"
    subprocess.run(["rm", "-rf", str(vendor)], check=True)
    vendor.mkdir()
    (vendor / "rogue").write_text("do not overwrite")

    audit = materialize_vendor(parent, "vendor/gyms/example", pinned_revision=sha)
    assert audit.state is VendorMaterializationState.REFUSED_PARENT_INHERITANCE
    assert (vendor / "rogue").read_text() == "do not overwrite"
