"""Optional adapter boundary — declared interfaces, zero implementations.

Sibling repositories are OPTIONAL. Importing this package must succeed on a clean
checkout with no sibling present; every adapter then reports ``UNAVAILABLE``. A
missing adapter never lowers the standing of the self-contained core.

Adapters describe what EXISTS. None of them actuate, admit, broker, or issue
receipts.

    >>> from skdecide.adapters import probe_all, available
    >>> sorted(probe_all())          # doctest: +ELLIPSIS
    ['azure', 'bcinr', ...]
"""

from __future__ import annotations

from skdecide.adapters.azure import AzureIncidentAdapter
from skdecide.adapters.base import Adapter, AdapterProbe, AdapterStatus
from skdecide.adapters.bcinr import BcinrSchedulerAdapter
from skdecide.adapters.ferroplan import FerroplanAdapter
from skdecide.adapters.ggen import GgenManufactureAdapter
from skdecide.adapters.mfact import MfactProofAdapter
from skdecide.adapters.mfw import MfwExecutionAdapter
from skdecide.adapters.openclaw import OpenclawAdapter
from skdecide.adapters.wasm4pm import Wasm4pmCompatAdapter

__all__ = [
    "Adapter",
    "AdapterProbe",
    "AdapterStatus",
    "AzureIncidentAdapter",
    "BcinrSchedulerAdapter",
    "FerroplanAdapter",
    "GgenManufactureAdapter",
    "MfactProofAdapter",
    "MfwExecutionAdapter",
    "OpenclawAdapter",
    "Wasm4pmCompatAdapter",
    "ADAPTERS",
    "probe_all",
    "available",
]

ADAPTERS: tuple[Adapter, ...] = (
    MfwExecutionAdapter(),
    BcinrSchedulerAdapter(),
    FerroplanAdapter(),
    MfactProofAdapter(),
    GgenManufactureAdapter(),
    OpenclawAdapter(),
    Wasm4pmCompatAdapter(),
    AzureIncidentAdapter(),
)


def probe_all() -> dict[str, AdapterProbe]:
    """Probe every registered adapter. Never raises."""
    results: dict[str, AdapterProbe] = {}
    for adapter in ADAPTERS:
        try:
            results[adapter.name] = adapter.probe()
        except Exception as exc:  # pragma: no cover - adapters must not raise
            results[adapter.name] = AdapterProbe(
                status=AdapterStatus.UNAVAILABLE,
                detail=f"probe raised (adapter bug, treated as absent): {exc!r}",
                searched=(f"<adapter {adapter.name} raised>",),
            )
    return results


def available() -> frozenset[str]:
    """Names of adapters whose backend was located (any non-UNAVAILABLE status)."""
    return frozenset(
        name for name, probe in probe_all().items() if probe.status is not AdapterStatus.UNAVAILABLE
    )
