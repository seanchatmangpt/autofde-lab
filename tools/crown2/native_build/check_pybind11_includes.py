#!/usr/bin/env python3
"""Falsifier for the Crown-2 native blocker class: a C++ source that is compiled
into a non-Python target (skdecide_pddl, built even with BUILD_PYTHON_BINDING=OFF)
must not include pybind11 headers, because cpp/CMakeLists.txt only appends
pybind11_INCLUDE_DIR to INCLUDE_DIRS when BUILD_PYTHON_BINDING or ONLY_PYTHON is ON.

Rule (encoded, no LLM needed next time):
  include "pybind11/..." is allowed only in files matching ALLOWED_GLOBS
  (py_*.cc / python binding sources) or files guarded by a BUILD_PYTHON_BINDING #if.

Usage: python3 tools/crown2/native_build/check_pybind11_includes.py [cpp/src]
Exit 0 = clean, 1 = violations (prints file:line).
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3] / "cpp" / "src"
ALLOWED_BASENAME = re.compile(r"^(py_.*|.*_py|python.*|.*py_bind.*)\.(cc|hh|h|cpp|hpp)$")
INCLUDE = re.compile(r'^\s*#\s*include\s*[<"]pybind11/')

def violations(root):
    out = []
    for p in sorted(root.rglob("*")):
        if p.suffix not in (".cc", ".hh", ".h", ".cpp", ".hpp") or ALLOWED_BASENAME.match(p.name):
            continue
        if "python" in p.parts or "py" in p.parts:
            continue
        lines = p.read_text(errors="replace").splitlines()
        guarded = any("BUILD_PYTHON_BINDING" in l or "SKDECIDE_PYTHON" in l for l in lines)
        for i, l in enumerate(lines, 1):
            if INCLUDE.match(l) and not guarded:
                out.append(f"{p}:{i}: {l.strip()}")
    return out

if __name__ == "__main__":
    root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
    v = violations(root)
    print("\n".join(v) if v else f"OK: no unguarded pybind11 includes under {root}")
    sys.exit(1 if v else 0)
