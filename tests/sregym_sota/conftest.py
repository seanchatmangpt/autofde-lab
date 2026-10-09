from __future__ import annotations

# Root tests/conftest.py intentionally imports numpy before DSPy. After that
# repository-wide bootstrap, import the real package once here. This conftest
# previously installed a bare module-type stub for `autofde_lab` into
# sys.modules at collection time and never removed it, which shadowed the real
# package for every test module collected afterwards in the same session
# (measured: `from autofde_lab import DeterministicPlanningDomain` failed with
# "unknown location" in tests/planner_league and tests/reasoning). The real
# package imports cleanly in ~0.3s, so the stub shortcut is not worth the
# session-wide pollution.
import autofde_lab  # noqa: F401
