"""The v26.9.17 release-level crown: ReleaseState machine + ReleaseRun orchestrator
+ the subprocess-isolated fresh-consumer verifier (PRD §12; ARD §45, §50).

Deliberately does NOT re-export `ReleaseRun` here: `python -m autofde_lab.sa2a.
release.fresh_consumer` executes THIS package `__init__.py` before the submodule
itself, so importing `run.py` (which imports `episode1`/`episode2`) at package
scope would make `fresh_consumer.py`'s `assert_no_runtime_imports()` self-check
fail even in a genuinely separate subprocess -- a real bug this project hit and
fixed while building this package. Import `ReleaseRun` directly from
`autofde_lab.sa2a.release.run`; import `ReleaseState` from
`autofde_lab.sa2a.release.state_machine` (zero episode/experience imports, safe
at package scope) -- both re-exported below.
"""

from __future__ import annotations

from autofde_lab.sa2a.release.state_machine import ReleaseState

__all__ = ["ReleaseState"]
