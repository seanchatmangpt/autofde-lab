"""Optional adapter: Azure incident surfaces. ALWAYS UNAVAILABLE, by construction.

Sentinel, Defender XDR, Logic Apps, Entra and Confidential Ledger are
deployment-time surfaces that exist in a customer tenant, never a dependency of
this repository's core. There is nothing on a developer filesystem that could make
them AVAILABLE, and a probe that guessed otherwise from a stray credential file or
an installed CLI would be manufacturing a tenant claim from a local artifact.

So this probe reports UNAVAILABLE unconditionally and records that its search
boundary is the empty local filesystem — a deliberately honest negative rather
than a lookup that could accidentally succeed.
"""

from __future__ import annotations

from skdecide.adapters.base import AdapterProbe, AdapterStatus

__all__ = ["AzureIncidentAdapter"]

SURFACES = (
    "Microsoft Sentinel",
    "Defender XDR",
    "Logic Apps",
    "Entra",
    "Azure Confidential Ledger",
)


class AzureIncidentAdapter:
    """Declares the Azure incident surfaces as deployment-time only."""

    name = "azure"

    def probe(self) -> AdapterProbe:
        return AdapterProbe(
            status=AdapterStatus.UNAVAILABLE,
            detail=(
                "Azure incident surfaces ("
                + ", ".join(SURFACES)
                + ") are deployment-time surfaces bound to a customer tenant, never "
                "a core dependency. UNAVAILABLE is returned unconditionally: no local "
                "filesystem state can establish tenant access, so none is consulted."
            ),
            searched=("<none: deployment-time surface, not locally probeable>",),
        )
