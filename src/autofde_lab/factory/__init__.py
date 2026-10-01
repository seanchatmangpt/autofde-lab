"""Autonomous, LLM-free EXPLORE -> MANUFACTURE -> EXPLOIT loop.

Computes candidate dispositions and compiled experience. It has no production
actuation path: the only "world" it touches is an in-process fault simulator.
"""

__all__ = ["FactoryVerdict", "run_factory", "verify_ledger"]


def __getattr__(name: str):
    if name == "run_factory":
        from .loop import run_factory

        return run_factory
    if name in ("FactoryVerdict", "verify_ledger"):
        from . import verify

        return getattr(verify, name)
    raise AttributeError(name)
