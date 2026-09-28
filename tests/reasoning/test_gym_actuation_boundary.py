"""Machine-enforced gym actuation boundary (``.claude/rules/gym-actuation-boundary.md``).

The rule says: vendored gyms under ``vendor/gyms/`` are reference only -- never imported, never
launched directly -- and ``gymact`` is the only actuation surface. Until now nothing enforced it.
This scan is static (AST + string constants); it establishes what the source *contains*, not what
a running system does. Scope: ``src/autofde_lab``.

Three properties:

1. No module imports ``vendor.*`` or inserts ``vendor/gyms`` into ``sys.path``.
2. No ``subprocess`` call launches a vendored gym's own entrypoint (``main.py``, ``clients/``,
   its ``.venv``), other than the sanctioned git bookkeeping in the vendor-materialization modules.
3. A module that names a gym *and* imports a live network client (``fastmcp``, ``httpx``, ``requests``,
   ``aiohttp``, ``websockets``) is a potential second live-actuation path. The set of such modules
   must equal ``KNOWN_EXCEPTIONS`` exactly, so a new one fails and a removed one forces this list
   to be updated.

``KNOWN_EXCEPTIONS`` is a recorded fact, not an approval.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "autofde_lab"

LIVE_CLIENT_ROOTS = {"fastmcp", "httpx", "requests", "aiohttp", "websockets", "urllib3"}
GYM_NAMES = (
    "sregym",
    "devops-gym",
    "enterprisebench",
    "terragoat",
    "azuregoat",
    "cloudgoat",
)

#: Modules sanctioned to touch ``vendor/gyms`` for git-level pin bookkeeping only.
VENDOR_BOOKKEEPING = {
    "fabric/vendor_materialization.py",
    "fabric/vendor_materializer.py",
    "fabric/forwardbench_fleet.py",
}

#: Module -> why it exists. OWNER DECISION PENDING (recorded 2026-09-28): ``McpBroker.call`` makes
#: live tool calls on SREGym's kubectl/submit MCP surfaces via ``fastmcp`` without going through
#: ``gymact``. It may be legitimate as an agent-under-test client that SREGym's own conductor
#: mediates, or it may be the parallel actuation path the rule forbids; that ruling is not made here.
KNOWN_EXCEPTIONS = {
    "sregym_sota/mcp.py": "agent-under-test MCP client for SREGym (ruling pending)",
}


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _string_constants(tree: ast.AST) -> list[str]:
    return [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


def names_gym_and_imports_live_client(source: str) -> bool:
    tree = ast.parse(source)
    lowered = source.lower()
    return bool(_imported_roots(tree) & LIVE_CLIENT_ROOTS) and any(
        g in lowered for g in GYM_NAMES
    )


def imports_or_path_inserts_vendor(source: str) -> bool:
    tree = ast.parse(source)
    if any(r == "vendor" for r in _imported_roots(tree)):
        return True
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"insert", "append"}
        ):
            if any(
                "vendor/gyms" in s or "vendor\\gyms" in s
                for s in _string_constants(node)
            ):
                return True
    return False


def launches_vendored_entrypoint(source: str) -> bool:
    tree = ast.parse(source)
    if "subprocess" not in _imported_roots(tree):
        return False
    pattern = re.compile(r"vendor/gyms/[A-Za-z0-9_.-]+/(main\.py|clients/|\.venv)")
    return any(pattern.search(s) for s in _string_constants(tree))


def _modules():
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield str(path.relative_to(SRC)), path.read_text(encoding="utf-8")


def test_the_scan_actually_found_the_source_tree():
    """Guard against a vacuous pass from a bad path."""
    assert len(list(_modules())) > 200


def test_no_module_imports_vendor_or_inserts_it_into_sys_path():
    offenders = [rel for rel, src in _modules() if imports_or_path_inserts_vendor(src)]
    assert not offenders, f"direct vendor access: {offenders}"


def test_no_module_launches_a_vendored_gym_entrypoint():
    offenders = [
        rel
        for rel, src in _modules()
        if rel not in VENDOR_BOOKKEEPING and launches_vendored_entrypoint(src)
    ]
    assert not offenders, (
        f"vendored gym entrypoint launched outside bookkeeping: {offenders}"
    )


def test_live_gym_clients_are_exactly_the_recorded_exceptions():
    found = {rel for rel, src in _modules() if names_gym_and_imports_live_client(src)}
    assert found == set(KNOWN_EXCEPTIONS), (
        "modules that name a gym and import a live network client changed.\n"
        f"  new (route through gymact or record with a reason): {sorted(found - set(KNOWN_EXCEPTIONS))}\n"
        f"  gone (remove from KNOWN_EXCEPTIONS): {sorted(set(KNOWN_EXCEPTIONS) - found)}"
    )


def test_the_detectors_can_fire_and_can_stay_quiet():
    """Anti-vacuity: each detector flags its violation and ignores the sanctioned look-alike."""
    assert imports_or_path_inserts_vendor("from vendor.gyms.sregym import driver")
    assert imports_or_path_inserts_vendor(
        "import sys\nsys.path.insert(0, 'vendor/gyms/sregym')"
    )
    assert not imports_or_path_inserts_vendor(
        "from autofde_lab.fabric import vendor_materialization"
    )

    assert launches_vendored_entrypoint(
        "import subprocess\nsubprocess.run(['vendor/gyms/sregym/.venv/bin/python', 'main.py'])"
    )
    assert not launches_vendored_entrypoint(
        "import subprocess\nsubprocess.run(['git', 'submodule', 'status'])"
    )
    assert not launches_vendored_entrypoint(
        "x = 'vendor/gyms/sregym/main.py'  # a citation, no subprocess"
    )

    assert names_gym_and_imports_live_client(
        "import httpx\nBASE = 'http://sregym.local'"
    )
    assert not names_gym_and_imports_live_client(
        "import httpx\nBASE = 'http://example.com'"
    )
    assert not names_gym_and_imports_live_client("SREGYM_NOTE = 'reference only'")
