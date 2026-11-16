"""Plan-kind matrix: run every plankinds adapter present, fail closed on any gap.

collect() -> (rows, unsupported); check() raises AssertionError listing every MISSING kind and
every runnable case whose outcome differs from its expectation. A SKIP/UNSUPPORTED row counts
as present (loudly reported) but a missing module never does."""
from __future__ import annotations

import importlib
import json
import pkgutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / ".results" / "plankind_matrix.json"
EXPECTED = [f"K{i}" for i in range(1, 18)]


def _load_registry():
    """{KIND: module}; a module that fails to import is returned as {KIND-from-name: Exception}."""
    import plankinds
    mods, errors = {}, {}
    for m in pkgutil.iter_modules(plankinds.__path__):
        if not m.name.startswith("k"):
            continue
        try:
            mod = importlib.import_module(f"plankinds.{m.name}")
            mods[mod.KIND] = mod
        except Exception as e:  # reported as an error row, never dropped
            digits = "".join(ch for ch in m.name[1:].split("_")[0] if ch.isdigit())
            errors[f"K{int(digits)}" if digits else m.name] = f"{type(e).__name__}: {e}"
    return mods, errors


def collect(registry=None, expected=None, run_kind=None):
    """Rows for every expected kind. registry: {KIND: module} (default: real plankinds)."""
    import plankinds
    run_kind = run_kind or plankinds.run_kind
    errors = {}
    if registry is None:
        registry, errors = _load_registry()
    rows = []
    for k in (EXPECTED if expected is None else expected):
        if k in registry:
            try:
                rows += run_kind(registry[k])
            except Exception as e:
                rows.append({"kind": k, "title": getattr(registry[k], "TITLE", "?"), "case": "-",
                             "expect": "-", "status": "ERROR", "detail": f"{type(e).__name__}: {e}",
                             "ok": False})
        elif k in errors:
            rows.append({"kind": k, "title": "?", "case": "-", "expect": "-", "status": "ERROR",
                         "detail": errors[k], "ok": False})
        else:
            rows.append({"kind": k, "title": "-", "case": "-", "expect": "-", "status": "MISSING",
                         "detail": "no plankinds module", "ok": False})
    for k, mod in registry.items():  # kinds outside the expected list still get reported
        if k not in (EXPECTED if expected is None else expected):
            rows += run_kind(mod)
    unsupported = [r for r in rows if r["status"] == "UNSUPPORTED"]
    return rows, unsupported


def summarize(rows):
    out = {}
    for r in rows:
        s = out.setdefault(r["kind"], {"title": r["title"], "cases": 0, "ok": 0, "note": ""})
        if r["status"] in ("SKIP", "MISSING", "ERROR"):
            s["note"] = f"{r['status']}: {r['detail']}"
            continue
        s["cases"] += 1
        s["ok"] += bool(r.get("ok"))
        if r["status"] == "UNSUPPORTED":
            s["note"] = f"UNSUPPORTED: {r['detail']}"
    return out


def table(rows) -> str:
    lines = [f"{'kind':<5} {'title':<46} {'cases':>5} {'ok':>3}  note"]
    for k, s in sorted(summarize(rows).items(), key=lambda kv: int(kv[0][1:])):
        lines.append(f"{k:<5} {s['title'][:46]:<46} {s['cases']:>5} {s['ok']:>3}  {s['note'][:90]}")
    return "\n".join(lines)


def write(rows, unsupported, path=RESULTS):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"rows": rows, "unsupported": unsupported,
                                "summary": summarize(rows)}, indent=1))
    return path


def check(rows=None, unsupported=None, out=RESULTS):
    if rows is None:
        rows, unsupported = collect()
    write(rows, unsupported or [], out)
    print(table(rows))
    problems = []
    for r in rows:
        if r["status"] in ("MISSING", "ERROR"):
            problems.append(f"{r['kind']} {r['status']}: {r['detail']}")
        elif r["status"] not in ("SKIP",) and not r.get("ok"):
            problems.append(f"{r['kind']}/{r['case']}: expected {r['expect']} got {r['status']} "
                            f"({r['detail'][:120]})")
    assert not problems, "plan matrix not green:\n  " + "\n  ".join(problems)
    return rows


if __name__ == "__main__":
    sys.path.insert(0, str(HERE.parent))
    try:
        check()
    except AssertionError as e:
        print(e)
        sys.exit(1)
