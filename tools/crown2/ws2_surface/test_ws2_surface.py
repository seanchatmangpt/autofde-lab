#!/usr/bin/env python3
"""Chicago-style tests for WS2 surface discovery (stdlib unittest, real files,
real repos, no mocks).

Falsifiers encoded here:
  F1  beam4pm surface contains `mix deps.get` (mix_exs) and `cargo build --release`
      for native/rf1-dfg-oracle.
  F2  every recipe named in every discovered beam4pm justfile appears as a
      justfile capability (cross-checked against `just --summary --justfile`,
      run from a scratch cwd, i.e. no command executed inside beam4pm).
  F3  `git push` / `rm -rf` style recipes classify CONSEQUENTIAL / DESTRUCTIVE,
      `git push --force` DESTRUCTIVE, and dependency-only recipes inherit.
  F4  extractor coverage on a synthetic fixture repo covering every declared
      source kind, including `--help` on a real PATH binary (python3).
  F5  OCEL emission via tools/ocel_v2/emitter.py validates green with validate.py.

Run:  python3 test_ws2_surface.py [-v]
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import discover  # noqa: E402
from classify import classify_command  # noqa: E402

BEAM4PM = "/Users/sac/beam4pm"
ORTHO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OCEL_DIR = os.path.join(ORTHO, "tools", "ocel_v2")


class ClassifyRules(unittest.TestCase):
    def test_f3_git_push_consequential_force_destructive(self):
        self.assertEqual(classify_command("git push origin main")["authority_class"], "CONSEQUENTIAL")
        self.assertEqual(classify_command("git push --force origin main")["authority_class"], "DESTRUCTIVE")
        self.assertEqual(classify_command("git push -f")["authority_class"], "DESTRUCTIVE")

    def test_f3_rm_rf_destructive_rm_f_consequential(self):
        self.assertEqual(classify_command("rm -rf build/")["authority_class"], "DESTRUCTIVE")
        self.assertEqual(classify_command("rm -r ./x")["authority_class"], "DESTRUCTIVE")
        c = classify_command("rm -f ggen.lock")
        self.assertEqual(c["authority_class"], "CONSEQUENTIAL")
        self.assertEqual(c["reversibility"], "IRREVERSIBLE")

    def test_multi_line_takes_max(self):
        c = classify_command("rm -f ggen.lock\nggen sync run --dry-run\nggen sync run")
        self.assertEqual(c["authority_class"], "CONSEQUENTIAL")
        self.assertIn("regenerates manufactured source files in the working tree", c["effects"])

    def test_read_and_build(self):
        self.assertEqual(classify_command("@just --list")["authority_class"], "READ")
        self.assertEqual(classify_command("cargo build --release")["authority_class"], "REVERSIBLE_BUILD")
        self.assertEqual(classify_command("mix deps.get")["authority_class"], "NETWORK_FETCH")
        self.assertEqual(classify_command("terraform destroy -auto-approve")["authority_class"], "DESTRUCTIVE")
        self.assertEqual(classify_command("terraform plan")["authority_class"], "READ")


class Beam4pmSurface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.surf = discover.discover(BEAM4PM, "beam4pm", max_depth=4, run_help=False)
        cls.caps = cls.surf.capabilities

    def _find(self, **kw):
        return [c for c in self.caps if all(getattr(c, k) == v for k, v in kw.items())]

    def test_f1_mix_deps_get(self):
        hits = self._find(source_kind="mix_exs", command="mix deps.get")
        self.assertEqual(len(hits), 1, [c.command for c in self.caps if c.source_kind == "mix_exs"])
        self.assertEqual(hits[0].authority_class, "NETWORK_FETCH")
        self.assertEqual(hits[0].cwd, ".")
        self.assertTrue(hits[0].evidence_source.startswith("mix.exs:"))

    def test_f1_rf1_cargo_build_release(self):
        hits = [c for c in self.caps if c.source_kind == "cargo_toml" and c.command == "cargo build --release"
                and c.cwd == os.path.join("native", "rf1-dfg-oracle")]
        self.assertEqual(len(hits), 1, [(c.cwd, c.command) for c in self.caps if c.source_kind == "cargo_toml"][:20])
        self.assertEqual(hits[0].authority_class, "REVERSIBLE_BUILD")
        self.assertEqual(hits[0].evidence_source, "native/rf1-dfg-oracle/Cargo.toml:8")

    def test_f1_ferroplan_workspace_members_expanded(self):
        names = {c.name for c in self.caps if c.source_kind == "cargo_toml"}
        self.assertIn("ferroplan:build-workspace", names)
        self.assertIn("ferroplan-cli:build", names)

    def test_f2_every_justfile_recipe_present(self):
        just = shutil.which("just")
        self.assertIsNotNone(just, "just binary required on PATH for this falsifier")
        justfiles = [s["path"] for s in self.surf.sources if s["kind"] == "justfile"]
        self.assertGreaterEqual(len(justfiles), 2, justfiles)
        with tempfile.TemporaryDirectory() as scratch:
            for jf in justfiles:
                r = subprocess.run([just, "--summary", "--justfile", os.path.join(BEAM4PM, jf), "--working-directory", scratch],
                                   capture_output=True, text=True, timeout=20)
                self.assertEqual(r.returncode, 0, r.stderr)
                expected = set(r.stdout.split())
                got = {c.name for c in self.caps if c.source_kind == "justfile" and c.evidence_source.rsplit(":", 1)[0].lower() == jf.lower()}
                self.assertEqual(expected - got, set(), f"{jf}: missing recipes {expected - got}")

    def test_f3_sync_and_verify_consequential(self):
        for kind in ("justfile", "makefile"):
            sync = [c for c in self._find(source_kind=kind, name="sync") if c.cwd == "."]
            self.assertEqual(len(sync), 1)
            self.assertEqual(sync[0].authority_class, "CONSEQUENTIAL", sync[0])
            verify = [c for c in self._find(source_kind=kind, name="verify") if c.cwd == "."]
            self.assertEqual(len(verify), 1)
            self.assertEqual(verify[0].authority_class, "CONSEQUENTIAL", verify[0])
            self.assertIn("sync", verify[0].depends_on)

    def test_terraform_destroy_destructive(self):
        d = self._find(source_kind="terraform", name="infra/gcp/cloudrun:destroy")
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0].authority_class, "DESTRUCTIVE")

    def test_ci_workflow_steps(self):
        steps = [c for c in self.caps if c.source_kind == "github_workflow" and c.name.startswith("beam4pm-ci.yml:test:")]
        cmds = "\n".join(c.command for c in steps)
        self.assertIn("mix deps.get", cmds)
        self.assertIn("cd native/rf1-dfg-oracle && cargo build --release", cmds)

    def test_every_capability_has_evidence_and_valid_enum(self):
        for c in self.caps:
            c.validate()
            f, ln = c.evidence_source.rsplit(":", 1)
            self.assertTrue(os.path.exists(os.path.join(BEAM4PM, f)), c.evidence_source)
            self.assertTrue(ln.isdigit(), c.evidence_source)


class SyntheticFixture(unittest.TestCase):
    """F4: a fixture repo written to disk exercising every extractor."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="ws2fix-")
        r = cls.tmp

        def w(rel, text):
            p = os.path.join(r, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write(text)

        w("justfile", "set shell := [\"bash\", \"-c\"]\nx := \"1\"\n\n# doc\ndefault:\n    @just --list\n\nbuild target=\"debug\":\n    cargo build\n\n"
                      "[private]\nnuke:\n    rm -rf target\n\npush: build (nuke)\n    git push origin HEAD\n\nship: push\n")
        w("Makefile", ".PHONY: all\nCC=gcc\nall: build\n\t@echo done\nbuild:\n\tcargo build\nforce:\n\tgit push --force\n")
        w("Taskfile.yml", "version: '3'\ntasks:\n  lint:\n    cmds:\n      - ruff check .\n  deploy:\n    deps: [lint]\n    cmds:\n      - terraform apply -auto-approve\n")
        w("package.json", json.dumps({"scripts": {"build": "tsc -p .", "publish": "npm publish"}}))
        w("mix.exs", "defmodule X.MixProject do\n  use Mix.Project\n  def project do\n    [app: :x, deps: deps(), aliases: aliases()]\n  end\n"
                     "  defp deps do\n    [{:jason, \"~> 1.0\"}, {:rustler, \"~> 0.30\"}]\n  end\n  defp aliases do\n    [setup: [\"deps.get\", \"compile\"], \"test.all\": [\"test\"]]\n  end\nend\n")
        w("Cargo.toml", "[workspace]\nmembers = [\"crates/a\"]\n")
        w("crates/a/Cargo.toml", "[package]\nname = \"a\"\nversion = \"0.1.0\"\n\n[[bin]]\nname = \"a\"\npath = \"src/main.rs\"\n\n[lib]\ncrate-type = [\"cdylib\"]\n")
        w(".cargo/config.toml", "[alias]\nxt = \"test --workspace\"\nxb = [\"build\", \"--release\"]\n")
        w("pyproject.toml", "[project]\nname = \"fix\"\nrequires-python = \">=3.10\"\n\n[project.scripts]\nfixcli = \"fix.cli:main\"\n\n"
                            "[project.entry-points.\"fix.plugins\"]\np1 = \"fix.p:P1\"\n\n[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n")
        w(".github/workflows/ci.yml", "name: ci\non:\n  push:\n  workflow_dispatch:\njobs:\n  build:\n    runs-on: ubuntu-latest\n    defaults:\n      run:\n        shell: bash\n"
                                      "    steps:\n      - uses: actions/checkout@v4\n      - name: Build\n        run: |\n          cargo build\n          cargo test\n"
                                      "      - name: Push\n        run: git push\n        working-directory: sub\n")
        w("Dockerfile", "FROM rust:1.80 AS builder\nRUN cargo build\nFROM debian:bookworm\nCMD [\"/app\"]\n")
        w("compose.yml", "services:\n  web:\n    image: x\n  db:\n    image: postgres\n")
        w("infra/main.tf", "terraform {\n  required_providers {\n    aws = {\n      source = \"hashicorp/aws\"\n    }\n  }\n}\n")
        cls.surf = discover.discover(r, "fix", max_depth=4, run_help=True, scratch=r)
        cls.caps = cls.surf.capabilities
        cls.by = {}
        for c in cls.caps:
            cls.by.setdefault((c.source_kind, c.name), c)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_source_kinds_covered(self):
        kinds = {c.source_kind for c in self.caps}
        for k in ("justfile", "makefile", "taskfile", "package_json", "mix_exs", "cargo_toml", "cargo_config",
                  "pyproject", "github_workflow", "dockerfile", "compose", "terraform", "cli_help"):
            self.assertIn(k, kinds, sorted(kinds))

    def test_justfile_classes_and_inheritance(self):
        self.assertEqual(self.by[("justfile", "default")].authority_class, "READ")
        self.assertEqual(self.by[("justfile", "nuke")].authority_class, "DESTRUCTIVE")
        self.assertIn("justfile attributes: [private]", self.by[("justfile", "nuke")].preconditions)
        push = self.by[("justfile", "push")]
        self.assertEqual(push.authority_class, "DESTRUCTIVE")  # git push (CONSEQUENTIAL) max nuke dep (DESTRUCTIVE)
        self.assertEqual(sorted(push.depends_on), ["build", "nuke"])
        ship = self.by[("justfile", "ship")]
        self.assertEqual(ship.command, "just ship")
        self.assertEqual(ship.authority_class, "DESTRUCTIVE")
        self.assertIn("just recipe params: target=\"debug\"", self.by[("justfile", "build")].preconditions)

    def test_makefile(self):
        self.assertEqual(self.by[("makefile", "force")].authority_class, "DESTRUCTIVE")
        self.assertEqual(self.by[("makefile", "all")].depends_on, ["build"])
        self.assertNotIn(("makefile", "CC"), self.by)
        self.assertNotIn(("makefile", ".PHONY"), self.by)

    def test_taskfile(self):
        self.assertEqual(self.by[("taskfile", "lint")].authority_class, "READ")
        d = self.by[("taskfile", "deploy")]
        self.assertEqual(d.authority_class, "CONSEQUENTIAL")
        self.assertEqual(d.depends_on, ["lint"])

    def test_package_json(self):
        self.assertEqual(self.by[("package_json", "publish")].authority_class, "CONSEQUENTIAL")
        self.assertEqual(self.by[("package_json", "build")].command, "tsc -p .")

    def test_mix(self):
        self.assertEqual(self.by[("mix_exs", "deps.get")].authority_class, "NETWORK_FETCH")
        self.assertTrue(any("rust/cargo toolchain" in p for p in self.by[("mix_exs", "deps.get")].preconditions))
        self.assertEqual(self.by[("mix_exs", "alias:setup")].command, "mix setup")
        self.assertIn(("mix_exs", "alias:test.all"), self.by)

    def test_cargo(self):
        self.assertIn(("cargo_toml", "a:build-release"), self.by)
        self.assertIn(("cargo_toml", "a:build-wasm"), self.by)
        self.assertEqual(self.by[("cargo_config", "alias:xb")].command, "cargo build --release")
        self.assertEqual(self.by[("cargo_config", "alias:xt")].command, "cargo test --workspace")

    def test_pyproject(self):
        self.assertEqual(self.by[("pyproject", "script:fixcli")].command, "fixcli --help")
        self.assertIn(("pyproject", "entry-points:fix.plugins"), self.by)
        self.assertIn(("pyproject", "pytest"), self.by)

    def test_workflow_steps_skip_defaults_run(self):
        names = [c.name for c in self.caps if c.source_kind == "github_workflow"]
        self.assertIn("ci.yml:dispatch", names)
        self.assertIn("ci.yml:build:Build", names)
        self.assertIn("ci.yml:build:Push", names)
        self.assertEqual(len([n for n in names if n.startswith("ci.yml:build:")]), 2, names)
        b = self.by[("github_workflow", "ci.yml:build:Build")]
        self.assertEqual(b.command, "cargo build\ncargo test")
        p = self.by[("github_workflow", "ci.yml:build:Push")]
        self.assertEqual(p.cwd, "sub")
        self.assertEqual(p.authority_class, "CONSEQUENTIAL")

    def test_docker_compose_terraform(self):
        self.assertIn(("dockerfile", "Dockerfile:build:builder"), self.by)
        self.assertEqual(self.by[("dockerfile", "Dockerfile:build")].authority_class, "NETWORK_FETCH")
        self.assertEqual(self.by[("compose", "compose.yml:db")].authority_class, "CONSEQUENTIAL")
        self.assertEqual(self.by[("terraform", "infra:destroy")].authority_class, "DESTRUCTIVE")
        self.assertIn("providers: aws", self.by[("terraform", "infra:apply")].preconditions)

    def test_cli_help_real_subprocess_cargo(self):
        # `cargo` is declared in the fixture (justfile/Makefile) and present on PATH on this box.
        if not shutil.which("cargo"):
            self.skipTest("cargo not on PATH")
        h = self.by[("cli_help", "cargo")]
        self.assertEqual(h.authority_class, "READ")
        self.assertIn("exit=0", h.notes)
        self.assertIn("Usage", h.help_excerpt)
        # denylisted coreutils and shell words never get a --help probe
        self.assertNotIn(("cli_help", "echo"), self.by)

    def test_f5_ocel_emission_validates(self):
        ocel = os.path.join(self.tmp, "ws2.ocel.json")
        discover.emit_ocel(self.surf, ocel)
        r = subprocess.run([sys.executable, os.path.join(OCEL_DIR, "validate.py"), ocel], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout), {"strict_type_mismatches": 0, "duplicate_ids": 0, "dangling_refs": 0})
        with open(ocel) as f:
            log = json.load(f)
        self.assertEqual(sum(1 for o in log["objects"] if o["type"] == "Action"), len(self.caps))


if __name__ == "__main__":
    unittest.main()
