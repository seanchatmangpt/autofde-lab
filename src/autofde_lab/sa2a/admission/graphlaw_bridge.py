"""Bridge connecting Python SA2A to Praxis GraphLaw (praxis-graphlaw-wasm).

Executes native Rust semantic validation pipelines (OWL RL, Safe Datalog, SHACL, ShEx,
and N3 denial verification) with deterministic replay verification and BLAKE3 hashing.

Artifact-identity discipline (AFDE-2609): mirrors the content-addressed loading
pattern in `src/autofde_lab/wasm/_runtime.py` (`ArtifactImage.from_descriptor` and
the Node/Wasmtime ambient-import guards) rather than inventing a new one. At
construction time this bridge computes the real SHA-256 of the loaded
`praxis_graphlaw_wasm_bg.wasm` bytes and compares it against a pinned expected
digest, checks the declared size and the WebAssembly v1 magic prefix, and inspects
the module's real declared imports via `WebAssembly.Module.imports()` (Node.js),
refusing any import outside an explicitly admitted, narrowly-named set. The real
local artifact is not zero-import: it declares a wasm-bindgen glue function
(`__wbindgen_object_drop_ref`) and a host entropy-source binding
(`__wbg_getRandomValues_3f44b700395062e5`) from `./praxis_graphlaw_wasm_bg.js`. Both
are explicitly named and admitted below (Law 4's "unless explicitly required and
admitted"); anything else is a typed refusal, not a silent load.
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PRAXIS_WASMPKG_DIR = Path("/Users/sac/praxis/crates/praxis-graphlaw-wasm/pkg")

# Pinned content-addressed identity of the real local praxis-graphlaw-wasm
# artifact, confirmed via `shasum -a 256` against the real file bytes this
# session (see docs/jira/v26.9.16/AFDE-2609-wasm-artifact-discipline-consumer-seam.md
# "Local closure work"). A mismatch means the bytes at PRAXIS_WASMPKG_DIR are not
# the artifact this bridge was built to drive -- refuse, do not silently load.
EXPECTED_ARTIFACT_SHA256 = (
    "187688d9e7e33a575713d6911d75687adb38713ed37412e211af263dfcbe0c28"
)
EXPECTED_ARTIFACT_SIZE = 3249361

# The WASM v1 magic prefix, per the spec -- same check as wasm/_runtime.py.
_WASM_V1_MAGIC = b"\x00asm\x01\x00\x00\x00"

# Real declared imports of the pinned artifact (module, name), confirmed this
# session via `node -e 'WebAssembly.Module.imports(...)'` against the real bytes.
# Narrowly and explicitly admitted per A2A-2609 Law 4 -- any import outside this
# set is refused, so a future artifact rebuild that adds a new ambient capability
# (filesystem, network, shell) is caught rather than silently accepted.
ADMITTED_IMPORTS = frozenset(
    {
        ("./praxis_graphlaw_wasm_bg.js", "__wbindgen_object_drop_ref"),
        ("./praxis_graphlaw_wasm_bg.js", "__wbg_getRandomValues_3f44b700395062e5"),
    }
)

_IMPORT_INSPECTION_SCRIPT = r"""
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const bytes = Buffer.from(input.wasm, 'base64');
WebAssembly.compile(bytes).then((mod) => {
  const imports = WebAssembly.Module.imports(mod).map((i) => [i.module, i.name]);
  process.stdout.write(JSON.stringify(imports));
}).catch((err) => {
  console.error(String((err && err.stack) || err));
  process.exit(1);
});
"""


class GraphLawArtifactIntegrityError(RuntimeError):
    """Raised when the loaded praxis-graphlaw-wasm bytes fail digest, size, or
    WebAssembly v1 magic-prefix verification against the pinned expected identity."""


class GraphLawUnadmittedImportError(RuntimeError):
    """Raised when the loaded praxis-graphlaw-wasm module declares a real import
    outside the explicitly named and admitted ADMITTED_IMPORTS set."""


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

        self.artifact_sha256 = self._verify_artifact_integrity()

    def _verify_artifact_integrity(self) -> str:
        """Content-addressed load-time verification, mirroring
        `wasm/_runtime.py`'s `ArtifactImage.from_descriptor`: digest, size, and
        WebAssembly v1 magic prefix, plus an ambient-import check this module adds
        on top (see ADMITTED_IMPORTS). Raises a typed error on any mismatch --
        never a silent load of bytes that are not the pinned artifact.
        """
        data = self._wasm_bg.read_bytes()

        digest = hashlib.sha256(data).hexdigest()
        if digest != EXPECTED_ARTIFACT_SHA256:
            raise GraphLawArtifactIntegrityError(
                "praxis-graphlaw-wasm artifact digest mismatch: "
                f"expected {EXPECTED_ARTIFACT_SHA256}, observed {digest} "
                f"(path: {self._wasm_bg})"
            )
        if len(data) != EXPECTED_ARTIFACT_SIZE:
            raise GraphLawArtifactIntegrityError(
                "praxis-graphlaw-wasm artifact size mismatch: "
                f"expected {EXPECTED_ARTIFACT_SIZE}, observed {len(data)} "
                f"(path: {self._wasm_bg})"
            )
        if not data.startswith(_WASM_V1_MAGIC):
            raise GraphLawArtifactIntegrityError(
                f"praxis-graphlaw-wasm artifact is not a WebAssembly v1 module (path: {self._wasm_bg})"
            )

        self._verify_ambient_imports(data)
        return digest

    def _verify_ambient_imports(
        self, data: bytes, admitted: frozenset[tuple[str, str]] = ADMITTED_IMPORTS
    ) -> None:
        """Inspect the real declared imports of the compiled module (Node.js
        `WebAssembly.Module.imports()`) and refuse any import outside
        `admitted` (defaults to the module-level ADMITTED_IMPORTS), rather than
        silently accepting arbitrary ambient capabilities the way an uninspected
        load would.

        `admitted` is exposed as a real parameter (not hardcoded to the module
        constant) so a Chicago-style falsifier test can call this method
        directly against the real compiled artifact with a real, hand-built,
        narrower frozenset -- exercising the genuine refusal path without
        monkeypatching (banned by testing-chicago-style.md) and without needing
        an artifact that happens to declare an unadmitted import today.
        """
        envelope = json.dumps({"wasm": base64.b64encode(data).decode("ascii")})
        try:
            res = subprocess.run(
                [self._node_bin, "--no-warnings", "-e", _IMPORT_INSPECTION_SCRIPT],
                input=envelope,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GraphLawUnadmittedImportError(
                f"failed to inspect praxis-graphlaw-wasm module imports: {exc}"
            ) from exc
        if res.returncode != 0:
            raise GraphLawUnadmittedImportError(
                f"failed to compile praxis-graphlaw-wasm module for import inspection: {res.stderr.strip()}"
            )
        try:
            raw_imports = json.loads(res.stdout.strip())
        except json.JSONDecodeError as exc:
            raise GraphLawUnadmittedImportError(
                f"could not parse praxis-graphlaw-wasm import inspection output: {res.stdout.strip()!r}"
            ) from exc

        observed = {(entry[0], entry[1]) for entry in raw_imports}
        unadmitted = observed - admitted
        if unadmitted:
            raise GraphLawUnadmittedImportError(
                "praxis-graphlaw-wasm module declares unadmitted import(s), refusing to load: "
                f"{sorted(unadmitted)}. Admitted set: {sorted(admitted)}"
            )

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
