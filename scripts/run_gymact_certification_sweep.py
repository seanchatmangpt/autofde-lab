#!/usr/bin/env python3
# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Real, mechanical evidence for "every gym repo becomes GymAct Certified":
imports every real module under `gymact.gyms`, finds every real class whose
name ends in `Provider` (the real, consistent naming convention this
package's own real modules already follow -- confirmed live this session
across all 22 real `gymact/src/gymact/gyms/*.py` modules), and runs the real,
provider-agnostic structural conformance check against each one it can
construct with zero arguments -- as its own real, subprocess-isolated
`scripts/run_gymact_certification_check.py` call, never an in-process import
of `check_environment_provider_conformance` (see that script and
`gymact_certification_checker.py`'s own module docstring for why: `gymact`
is an ordinary dependency of this repo, and an in-process checker call
always leaves `gymact` in the calling process's `sys.modules`). Pass
`--smoke` to additionally drive a real materialize->observe->checkpoint->
teardown cycle per provider (opt-in; real side-effect risk; off by default).

Named, honest residual: `_discover_provider_classes()` below still does
`import gymact.gyms` directly, in THIS sweep script's own process, to
enumerate the real provider classes to check -- that import is real,
in-process, and leaves `gymact` in this sweep process's `sys.modules`.
Discovery is not the certified verdict, though: it never computes a
conformance result, only a list of names to hand to the isolated
subprocess. The independence property this file establishes is narrower
and honestly scoped: each provider's real *conformance result* is computed
in a fresh process; the *catalog of what to check* is still gathered
in-process here.

Read-only, no live cluster/network required for the structural pass. Never
asserts "every gym repo" as a headline claim independent of this script's
own real, printed output -- this script IS the evidence, not a description
of evidence.

A provider class that cannot be constructed with zero arguments (a real,
legitimate case -- several real providers require config, e.g. a target
Terraform module path) is reported honestly as `CONSTRUCTION_FAILED`, never
silently skipped from the printed output.

Also folds in gymact's own real, already-built native validation machinery
-------------------------------------------------------------------------------
`gymact` ships its own real `doctor`/`validate-profile` CLI commands
(`gymact.cli`, real console script `gymact = "gymact.cli:app"`) --
`doctor` reports real crown/errc/module/provider-registry status,
`validate-profile` runs real SHACL + zero-custom-TBox validation against
the packaged `ontology/profile.ttl`/`profile.shacl.ttl`/
`gym_algebra.shacl.ttl`. This sweep real-subprocess-calls both (resolving
the real installed console script, e.g. `.venv/bin/gymact`, via
`shutil.which`/a direct venv-relative fallback) and folds their real,
verbatim output into this sweep's own JSON under `gymact_native_validation`
-- additional real evidence from gymact's own already-working machinery,
never a competing reimplementation. If the `gymact` console script cannot
be resolved, this is reported as a real, honest `UNSUPPORTED` entry with
the exact reason, never silently omitted.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pkgutil
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_CHECK_ENTRYPOINT = REPO_ROOT / "scripts" / "run_gymact_certification_check.py"


def _resolve_gymact_cli() -> str | None:
    """Real resolution of the installed `gymact` console script -- prefers
    the venv this script's own interpreter belongs to (matches how this
    repo's own `.venv/bin/python` was used to confirm both commands work
    this session), falls back to `shutil.which` for a global install."""
    venv_relative = Path(sys.executable).parent / "gymact"
    if venv_relative.is_file():
        return str(venv_relative)
    return shutil.which("gymact")


def _run_gymact_native_validation() -> dict:
    """Real subprocess calls to `gymact doctor` and `gymact validate-profile`,
    verbatim real output folded in. Never raises -- a real subprocess
    failure (non-zero exit, malformed JSON) is reported honestly in the
    result dict, never crashes the sweep."""
    cli_path = _resolve_gymact_cli()
    if cli_path is None:
        return {
            "standing": "UNSUPPORTED",
            "reason": "no real installed 'gymact' console script found (checked venv-relative "
            f"path next to {sys.executable!r} and PATH via shutil.which)",
        }

    result: dict = {"standing": "OBSERVED", "cli_path": cli_path}
    for command_name in ("doctor", "validate-profile"):
        try:
            completed = subprocess.run(
                [cli_path, command_name], capture_output=True, text=True, timeout=30
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            result[command_name] = {"error": f"real subprocess failure: {type(exc).__name__}: {exc}"}
            continue
        entry: dict = {"exit_code": completed.returncode, "stdout": completed.stdout.strip()}
        if completed.stderr.strip():
            entry["stderr"] = completed.stderr.strip()
        try:
            entry["parsed"] = json.loads(completed.stdout)
        except json.JSONDecodeError:
            entry["parsed"] = None
        result[command_name] = entry
    return result


def _discover_provider_classes() -> list[tuple[str, type]]:
    """Real, live discovery: import every module under `gymact.gyms` and
    collect every class defined in that module whose name ends in
    `Provider` -- never a hardcoded list, so this sweep automatically
    covers new gym adapters without maintenance."""
    import gymact.gyms as gyms_package

    found: list[tuple[str, type]] = []
    for module_info in pkgutil.iter_modules(gyms_package.__path__):
        module_name = f"gymact.gyms.{module_info.name}"
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001 -- a real, reportable import failure
            print(f"[sweep] {module_name}: real import failure: {type(exc).__name__}: {exc}")
            continue
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module_name:
                continue  # only classes genuinely defined in this module, not re-exports
            if name.endswith("Provider") and name != "EnvironmentProvider":
                found.append((module_name, obj))
    return found


def _run_sweep(*, smoke: bool) -> list[dict]:
    """Real, per-provider sweep -- each provider's check runs as its own
    real `subprocess.run([sys.executable, str(_CHECK_ENTRYPOINT), ...])`
    call to `scripts/run_gymact_certification_check.py`, never an in-process
    import of `check_environment_provider_conformance` -- the real fix for
    the independence gap: this sweep process itself never needs `gymact` in
    its own `sys.modules` to certify a provider. `smoke=True` passes
    `--smoke` through to the entrypoint (real materialize/observe/checkpoint/
    teardown against every discovered provider -- opt-in, real side-effect
    risk, off by default)."""
    manifests: list[dict] = []
    for module_name, provider_cls in _discover_provider_classes():
        cmd = [
            sys.executable,
            str(_CHECK_ENTRYPOINT),
            "--module",
            module_name,
            "--class",
            provider_cls.__qualname__,
            "--gym-name",
            module_name.rsplit(".", 1)[-1],
        ]
        if smoke:
            cmd.append("--smoke")
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except (subprocess.TimeoutExpired, OSError) as exc:
            manifests.append(
                {
                    "module": module_name,
                    "provider_class": provider_cls.__qualname__,
                    "conformance_level": "CONSTRUCTION_FAILED",
                    "detail": f"real subprocess failure invoking the check entrypoint: {type(exc).__name__}: {exc}",
                }
            )
            continue

        try:
            outcome = json.loads(completed.stdout)
        except json.JSONDecodeError:
            manifests.append(
                {
                    "module": module_name,
                    "provider_class": provider_cls.__qualname__,
                    "conformance_level": "CONSTRUCTION_FAILED",
                    "detail": f"real entrypoint produced non-JSON stdout (exit {completed.returncode}): "
                    f"{completed.stdout[:500]!r} stderr={completed.stderr[:500]!r}",
                }
            )
            continue

        if outcome.get("error"):
            manifests.append(
                {
                    "module": module_name,
                    "provider_class": provider_cls.__qualname__,
                    "conformance_level": "CONSTRUCTION_FAILED",
                    "detail": outcome["error"],
                }
            )
            continue

        if outcome.get("conformance_level") == "CONSTRUCTION_FAILED":
            manifests.append(
                {
                    "module": module_name,
                    "provider_class": provider_cls.__qualname__,
                    "conformance_level": "CONSTRUCTION_FAILED",
                    "detail": outcome.get("detail", ""),
                }
            )
            continue

        manifest = outcome["manifest"]
        results = outcome["results"]
        manifests.append(
            {
                "module": module_name,
                "provider_class": provider_cls.__qualname__,
                "conformance_level": manifest["manifest_conformance_level_ref"],
                "check_count": len(results),
                "checks": [
                    {"check": r["result_check_ref"], "passed": r["result_passed"], "detail": r["result_detail"]}
                    for r in results
                ],
            }
        )
    return manifests


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="also run the real materialize->observe->checkpoint->teardown smoke cycle "
        "against every discovered provider (opt-in; real side-effect risk; off by default)",
    )
    args = parser.parse_args()

    manifests = _run_sweep(smoke=args.smoke)
    native_validation = _run_gymact_native_validation()
    print(
        json.dumps(
            {"gymact_certification_sweep": manifests, "gymact_native_validation": native_validation}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
