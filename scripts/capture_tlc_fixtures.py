"""Capture real SANY/TLC ``-tool`` transcripts from the pinned jar as fixtures.

Usage::

    PYTHONPATH=src python scripts/capture_tlc_fixtures.py tests/iec/fixtures/tlc/v1.7.4

Every fixture is the real stdout of the real jar, with exactly two textual
substitutions recorded in MANIFEST.json: the per-run working directory becomes
``$WORKDIR`` and the JVM temp directory SANY extracts the standard modules into
becomes ``$JAVA_TMPDIR``. Nothing else is edited.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from autofde_lab.iec.brce_mutants import EXPECTED_VIOLATION, BrceMutant, brce_mutant
from autofde_lab.iec.brce_reference import brce_reference_system
from autofde_lab.iec.tla_projection import render_cfg, render_tla
from autofde_lab.iec.tlc_court import TlaToolchain, tlc_argv

_STDLIB_PATH = re.compile(r"^(Parsing file )(/\S+)/(\w+\.tla)$", re.MULTILINE)


def _sanitize(text: str, workdir: Path) -> str:
    resolved = str(workdir.resolve())
    text = text.replace(resolved, "$WORKDIR").replace(str(workdir), "$WORKDIR")
    return _STDLIB_PATH.sub(
        lambda m: m.group(0)
        if m.group(2) == "$WORKDIR"
        else f"{m.group(1)}$JAVA_TMPDIR/{m.group(3)}",
        text,
    )


def _portable(argv: tuple[str, ...], tc: TlaToolchain) -> list[str]:
    mapping = {tc.java_executable: "java", str(tc.jar_path): "$TLA2TOOLS_JAR"}
    return [mapping.get(a, a) for a in argv]


def main(out_dir: str) -> int:
    tc = TlaToolchain.discover()
    if not isinstance(tc, TlaToolchain):
        print(f"{tc.code}: {tc.reason}", file=sys.stderr)
        return 3
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cases: list[tuple[str, object, str, dict]] = []
    ref = brce_reference_system()
    cases.append(
        (
            "tlc_reference_liveness_holds",
            ref,
            "tlc",
            {
                "properties": ("AdmittedEventuallyTerminal",),
                "invariants": (),
                "deadlock_check": False,
            },
        )
    )
    cases.append(
        (
            "tlc_reference_invariant_holds",
            ref,
            "tlc",
            {
                "properties": (),
                "invariants": ("AtMostOneConsequence",),
                "deadlock_check": False,
            },
        )
    )
    cases.append(
        (
            "tlc_reference_deadlock",
            ref,
            "tlc",
            {
                "properties": (),
                "invariants": ("AtMostOneConsequence",),
                "deadlock_check": True,
            },
        )
    )
    for kind in BrceMutant:
        prop = EXPECTED_VIOLATION[kind]
        system = brce_mutant(kind)
        is_live = prop in {p.name for p in system.liveness}
        cases.append(
            (
                f"tlc_mutant_{kind.value.lower()}",
                system,
                "tlc",
                {
                    "properties": (prop,) if is_live else (),
                    "invariants": () if is_live else (prop,),
                    "deadlock_check": False,
                },
            )
        )
    cases.append(("tlc_config_error", ref, "tlc-badcfg", {"deadlock_check": False}))
    cases.append(("sany_reference_ok", ref, "sany", {}))
    cases.append(
        (
            "sany_parse_error",
            None,
            "sany-text",
            {
                "text": "---- MODULE Broken ----\nVARIABLES x\nInit == x = \nNext == x' = y\n====\n",
                "module": "Broken",
            },
        )
    )
    cases.append(
        (
            "sany_semantic_error",
            None,
            "sany-text",
            {
                "text": "---- MODULE Sem ----\nVARIABLES x\nInit == x = 0\nNext == x' = y\n====\n",
                "module": "Sem",
            },
        )
    )

    manifest: dict = {
        "tla2tools_release": "1.7.4",
        "jar_sha256": tc.jar_sha256,
        "java_version": tc.java_version,
        "captured_by": "scripts/capture_tlc_fixtures.py",
        "substitutions": {
            "$WORKDIR": "per-run working directory",
            "$JAVA_TMPDIR": "JVM temp dir holding SANY's extracted standard modules",
        },
        "fixtures": {},
    }
    for name, system, mode, opts in cases:
        with tempfile.TemporaryDirectory(prefix="tlc-fixture-") as tmp:
            work = Path(tmp)
            if mode.startswith("sany"):
                if mode == "sany":
                    proj = render_tla(system)  # type: ignore[arg-type]
                    module, text = proj.module_name, proj.tla
                else:
                    module, text = opts["module"], opts["text"]
                (work / f"{module}.tla").write_text(text)
                argv = (
                    tc.java_executable,
                    "-cp",
                    str(tc.jar_path),
                    "tla2sany.SANY",
                    f"{module}.tla",
                )
            else:
                proj = render_tla(system)  # type: ignore[arg-type]
                (work / f"{proj.module_name}.tla").write_text(proj.tla)
                if mode == "tlc-badcfg":
                    cfg = "SPECIFICATION Spec\nINVARIANT Nope\n"
                else:
                    cfg = render_cfg(
                        system,
                        invariants=opts["invariants"],
                        properties=opts["properties"],
                    )  # type: ignore[arg-type]
                (work / "M.cfg").write_text(cfg)
                argv = tlc_argv(
                    tc,
                    proj.module_name,
                    "M.cfg",
                    "meta",
                    deadlock_check=opts["deadlock_check"],
                )
            completed = subprocess.run(
                argv, cwd=work, capture_output=True, text=True, timeout=120, check=False
            )
            (out / f"{name}.stdout").write_text(_sanitize(completed.stdout, work))
            manifest["fixtures"][name] = {
                "argv": _portable(argv, tc),
                "exit_code": completed.returncode,
                "stderr_nonempty": bool(completed.stderr.strip()),
            }
            print(name, completed.returncode)
    (out / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main(sys.argv[1] if len(sys.argv) > 1 else "tests/iec/fixtures/tlc/v1.7.4")
    )
