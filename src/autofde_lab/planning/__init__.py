"""Declarative external-solver/validator configuration and shell-free invocation.

Ported pattern (not source) from mfw-planner's ``engines.toml`` +
``src/{config.rs,runner.rs}`` (see /Users/sac/mfw/mfw-planner). The port target is the
*wrapper discipline*: external planning tools (fast-downward, VAL, optic-clp, or any
other CLI-shaped solver/validator) are declared once, invoked without a shell, and every
invocation is receipted with a bounded, typed outcome instead of a bare exception.

Public surface: ``EngineConfig``, ``EnginesConfig``, ``probe_engine``, ``run_engine``.
"""

from .config import EngineConfig, EnginesConfig, OutputMode
from .runner import EngineOutcome, EngineRunReceipt, probe_engine, run_engine

__all__ = [
    "EngineConfig",
    "EnginesConfig",
    "OutputMode",
    "EngineOutcome",
    "EngineRunReceipt",
    "probe_engine",
    "run_engine",
]
