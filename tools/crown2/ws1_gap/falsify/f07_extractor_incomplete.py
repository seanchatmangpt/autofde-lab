#!/usr/bin/env python3
"""F07: ambiguous ACTION_DISCOVERY vs ACTION_GAP when the repo-surface extractor is
incomplete. A REAL scratch repo contains a Makefile target `oracles:` that builds the
native oracles; the extractor only parses package.json/mix.exs (coverage declared
partial). Classifier has no UNVERIFIED output and returns ACTION_GAP although the
action exists in the repo (correct: ACTION_DISCOVERY_GAP)."""
import os, subprocess, tempfile
from _common import fresh_base, run
d = tempfile.mkdtemp(prefix="ws1_f07_")
open(os.path.join(d, "Makefile"), "w").write("oracles:\n\tcargo build --release --manifest-path native/rf1-dfg-oracle/Cargo.toml\n")
open(os.path.join(d, "mix.exs"), "w").write("defmodule B.MixProject do\n use Mix.Project\nend\n")
# ground truth: the action really is on the repo surface
assert "oracles" in subprocess.run(["make", "-n", "-p", "-C", d], capture_output=True, text=True).stdout
def partial_extractor(repo):  # parses mix.exs only, never Makefile
    return [] if os.path.exists(os.path.join(repo, "mix.exs")) else []
fx = fresh_base(); fx["name"] = "f07"
fx["no_plan"]["missing_transition"] = {"provides": "NATIVE_ORACLES_BUILT"}
fx["repo_surface_actions"] = partial_extractor(d)
fx["repo_surface_meta"] = {"extractor_coverage": "partial", "unparsed": ["Makefile"]}
fx["manufacturers"] = [{"name": "ggen-pack:native-oracle-builder", "provides": ["NATIVE_ORACLES_BUILT"]}]
rec = run("f07_extractor_incomplete", fx, "ACTION_DISCOVERY_GAP",
          f"Makefile target `oracles` exists in {d} but extractor coverage=partial; classifier cannot say UNVERIFIED")
assert rec["reproduces"], "did not reproduce"
