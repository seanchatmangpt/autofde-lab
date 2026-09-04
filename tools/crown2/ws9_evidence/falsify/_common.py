"""Shared helpers for WS9 falsifiers. Imports the REAL target (no mocks)."""
from __future__ import annotations

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, TARGET)

import evidence  # noqa: E402  (the real WS9 target)

# A real, durable scratch dir INSIDE the worktree (under $HOME, not under any transient root).
SCRATCH = os.path.join(HERE, ".scratch")


def fresh_scratch(name: str) -> str:
    d = os.path.join(SCRATCH, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    return d


def cleanup(name: str) -> None:
    shutil.rmtree(os.path.join(SCRATCH, name), ignore_errors=True)
    if os.path.isdir(SCRATCH) and not os.listdir(SCRATCH):
        os.rmdir(SCRATCH)


def write(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def report(title: str, severity: str, reproduced: bool, detail: str) -> None:
    tag = "REPRODUCED" if reproduced else "DID-NOT-REPRODUCE"
    print(f"[{tag}] severity={severity} :: {title}")
    print(detail)
