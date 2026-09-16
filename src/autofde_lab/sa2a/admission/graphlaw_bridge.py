"""Bridge connecting Python SA2A to Praxis GraphLaw (praxis-graphlaw-wasm).

Executes native Rust semantic validation pipelines (OWL RL, Safe Datalog, SHACL, ShEx,
and N3 denial verification) with deterministic replay verification and BLAKE3 hashing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Any

PRAXIS_WASMPKG_DIR = Path("/Users/sac/praxis/crates/praxis-graphlaw-wasm/pkg")


@dataclass(frozen=True)
class DialectResult:
    dialect: str
    status: str
    detail: str
    triples_out: int


@dataclass(frozen=True)
class GraphLawValidationResult:
    graph_hash: str
    profile_hash: str
    dialects: tuple[DialectResult, ...]
    conforms: bool
    replay_status: str
    raw_response: dict[str, Any]


class GraphLawBridge:
    """High-performance bridge to native praxis-graphlaw engine via WASM."""

    def __init__(self, wasm_pkg_dir: Path | str = PRAXIS_WASMPKG_DIR) -> None:
        self._pkg_dir = Path(wasm_pkg_dir)
        self._js_entry = self._pkg_dir / "praxis_graphlaw_wasm.js"
        self._wasm_bg = self._pkg_dir / "praxis_graphlaw_wasm_bg.wasm"
        self._node_bin = shutil.which("node")

        if not self._js_entry.exists() or not self._wasm_bg.exists():
            raise FileNotFoundError(
                f"praxis-graphlaw-wasm package files not found in {self._pkg_dir}"
            )
        if not self._node_bin:
            raise RuntimeError("Node.js runtime required to drive praxis-graphlaw-wasm")

    def version(self) -> str:
        script = f"""
        import init, {{ graphlaw_version }} from "{self._js_entry}";
        import fs from "fs";
        const bytes = fs.readFileSync("{self._wasm_bg}");
        await init(bytes);
        console.log(graphlaw_version());
        """
        res = subprocess.run(
            [self._node_bin, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip().splitlines()[-1]

    def blake3_hex(self, text: str) -> str:
        escaped = json.dumps(text)
        script = f"""
        import init, {{ blake3_hex }} from "{self._js_entry}";
        import fs from "fs";
        const bytes = fs.readFileSync("{self._wasm_bg}");
        await init(bytes);
        console.log(blake3_hex({escaped}));
        """
        res = subprocess.run(
            [self._node_bin, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip().splitlines()[-1]

    def validate_all(
        self,
        ttl: str,
        *,
        profile_ttl: str = "",
        shacl_shapes: str = "",
        shex_schema: str = "",
        shex_shape_map: str = "",
    ) -> GraphLawValidationResult:
        payload = json.dumps(
            {
                "ttl": ttl,
                "profile_ttl": profile_ttl,
                "shacl_shapes": shacl_shapes,
                "shex_schema": shex_schema,
                "shex_shape_map": shex_shape_map,
            }
        )
        script = f"""
        import init, {{ validate_all }} from "{self._js_entry}";
        import fs from "fs";
        const bytes = fs.readFileSync("{self._wasm_bg}");
        await init(bytes);
        const input = {payload};
        const res = validate_all(
            input.ttl,
            input.profile_ttl,
            input.shacl_shapes,
            input.shex_schema,
            input.shex_shape_map
        );
        console.log(res);
        """
        proc = subprocess.run(
            [self._node_bin, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            check=True,
        )
        out_line = proc.stdout.strip().splitlines()[-1]
        data = json.loads(out_line)
        if "error" in data:
            raise RuntimeError(f"GraphLaw validation error: {data['error']}")

        dialects = tuple(
            DialectResult(
                dialect=d["dialect"],
                status=d["status"],
                detail=d.get("detail", ""),
                triples_out=d.get("triples_out", 0),
            )
            for d in data.get("dialects", [])
        )

        all_conforms = all(
            d.status in ("ADMITTED", "PROFILE_NOT_ADMITTED", "UNSUPPORTED")
            for d in dialects
        )

        return GraphLawValidationResult(
            graph_hash=data["graph_hash"],
            profile_hash=data.get("profile_hash", ""),
            dialects=dialects,
            conforms=all_conforms,
            replay_status=data.get("replay", {}).get("status", "UNKNOWN"),
            raw_response=data,
        )

    def graph_hash(self, ttl: str) -> str:
        payload = json.dumps(ttl)
        script = f"""
        import init, {{ graph_hash }} from "{self._js_entry}";
        import fs from "fs";
        const bytes = fs.readFileSync("{self._wasm_bg}");
        await init(bytes);
        console.log(graph_hash({payload}));
        """
        proc = subprocess.run(
            [self._node_bin, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout.strip().splitlines()[-1]

    def run_hooks(self, base_ttl: str, event_ttl: str) -> dict[str, Any]:
        payload = json.dumps({"base": base_ttl, "event": event_ttl})
        script = f"""
        import init, {{ run_hooks }} from "{self._js_entry}";
        import fs from "fs";
        const bytes = fs.readFileSync("{self._wasm_bg}");
        await init(bytes);
        const input = {payload};
        console.log(run_hooks(input.base, input.event));
        """
        proc = subprocess.run(
            [self._node_bin, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            check=True,
        )
        out_line = proc.stdout.strip().splitlines()[-1]
        data = json.loads(out_line)
        if "error" in data:
            raise RuntimeError(f"GraphLaw run_hooks error: {data['error']}")
        return data

