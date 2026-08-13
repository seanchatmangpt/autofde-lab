#!/usr/bin/env python3
# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Real, single-provider `gymact` certification check, run as its own
subprocess -- the fix for a real, found gap: `gymact_certification_checker.py`
imports `gymact.models`/`gymact.providers` directly, in-process, and
`gymact` is an ordinary `pyproject.toml` dependency of `autofde-lab`. A
caller that imports and calls `check_environment_provider_conformance`
in-process therefore always has `gymact` present in its own `sys.modules`
-- exactly the "self-certification" shape
`~/gymact/docs/2026-08-12-gymact-certification-and-ggen-from-sregym.md`'s
central finding rejects, and exactly what
`src/autofde_lab/hub/domain/gym_procedure/standalone_verifier.py`'s own
`FORBIDDEN_RUNTIME_MODULES`/`assert_no_runtime_imports()` pattern was built
to prevent for Level 4 evidence.

This script is the structural fix, not a claim of full independence
--------------------------------------------------------------------------
Running the check in a fresh subprocess means the CALLING process (a test,
a CI job, an interactive session) never has `gymact` enter its own
`sys.modules` merely by asking for a certification result -- that is a
real, checkable, subprocess-boundary property
(`tests/reasoning/test_gymact_certification_process_isolation_chicago.py`
proves it the same way
`tests/ecosystem/test_identity_mutation_chicago.py::test_verifier_runs_independently_in_a_fresh_process`
proves it for `standalone_verifier.py`). It does NOT, on its own, establish
the deeper identity-binding independence `standalone_verifier.py` itself
was found to lack (commit `7369e0ab`, "retract: the ALIVE reconstruction
does not establish independent standing" -- a fabricated directory with a
copied artifact tree still reconstructed as ALIVE, because nothing bound
the artifact to a specific real trial). This script's manifest is not
bound to any external identity either -- it is honestly a subprocess-isolated
STRUCTURAL/SMOKE check, not an unforgeable receipt. Never claim more than
that for this script's output.

Usage
-----
    python scripts/run_gymact_certification_check.py \\
        --module gymact.gyms.sregym --class SregymVendorProvider \\
        [--gym-name sregym] [--smoke] [--scenario <id>] [--config '{"k": "v"}']

Prints one real `CertificationManifest` + its `CertificationCheckResult`
tuple as JSON to stdout, exit code 0 on a completed check (conformance
level, including `CERT_BUILD_BROKEN`, is reported IN the JSON -- it is not
a subprocess failure), non-zero only on a real, unexpected script error
(bad args, provider construction failure is still reported as JSON with a
non-zero exit so callers can distinguish "checked, and it's broken" from
"couldn't even run the check").
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sys
from dataclasses import asdict


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True, help="real module path, e.g. gymact.gyms.sregym")
    parser.add_argument("--class", dest="class_name", required=True, help="real class name ending in Provider")
    parser.add_argument("--gym-name", default=None, help="defaults to the module's last dotted component")
    parser.add_argument("--smoke", action="store_true", help="run the real materialize->observe->checkpoint->teardown smoke cycle")
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--config", default=None, help="JSON object passed to materialize() as config")
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> dict:
    # Real gymact import happens here, inside this subprocess only -- the
    # caller's own process never sees "gymact" in its sys.modules merely
    # from invoking this script.
    from autofde_lab.reasoning.gymact_certification_checker import check_environment_provider_conformance

    try:
        module = importlib.import_module(args.module)
    except Exception as exc:  # noqa: BLE001 -- reported honestly, not a crash
        return {"error": f"real import of {args.module!r} failed: {type(exc).__name__}: {exc}"}

    provider_cls = getattr(module, args.class_name, None)
    if provider_cls is None:
        return {"error": f"{args.module!r} has no real attribute {args.class_name!r}"}

    try:
        provider = provider_cls()
    except Exception as exc:  # noqa: BLE001 -- real, honest construction failure
        return {
            "error": None,
            "conformance_level": "CONSTRUCTION_FAILED",
            "detail": f"real zero-arg construction of {args.class_name!r} raised: {type(exc).__name__}: {exc}",
        }

    config = json.loads(args.config) if args.config else None
    gym_name = args.gym_name or args.module.rsplit(".", 1)[-1]

    manifest, results = await check_environment_provider_conformance(
        provider,
        gym_name=gym_name,
        environment_factory_config=config,
        scenario=args.scenario,
        run_smoke_cycle=args.smoke,
    )
    return {
        "error": None,
        "manifest": asdict(manifest),
        "results": [asdict(r) for r in results],
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    outcome = asyncio.run(_run(args))
    print(json.dumps(outcome, indent=2))
    return 0 if outcome.get("error") is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
