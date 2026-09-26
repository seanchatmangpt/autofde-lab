"""Pinned doctrine catalog (sd: strategic-doctrine) consumed by the lab.

The catalog is a vendored copy under ``data/catalog.json``, checked against a
pinned sha256 before use. It carries ordinals, lab-own paraphrased labels
(<= 60 chars) and primitive tuples only: no source text, no ``quote`` field, and a
mandatory non-claim. Until ggen-marketplace ``packs/strategic-doctrine-pack``
publishes ``generated/catalog.json`` this is a VENDORED_MINIMAL stand-in; the
pin is the seam that replacement must cross.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from autofde_lab.simulation.fortune5_safe.model import PolicyVector

from .primitives import PRIMITIVE_NAMES, compose, concealed

CATALOG_PATH = Path(__file__).with_name("data") / "catalog.json"
CATALOG_SHA256 = "49d404d32300e17704580455bbbd3e4a60773dbd1ff091c90e4a310a3bb65e30"
DOCTRINE_IRI = "https://ggen.dev/ontology/strategic-doctrine#"
MAX_TITLE = 60
# Allow-lists: anything outside them (free text such as ``quote`` or ``summary``)
# is refused, so no source text can ride in under a re-pinned digest.
ENTRY_KEYS = frozenset({"ordinal", "iri", "short_title", "status", "primitives"})
STATUSES = frozenset({"operationalized", "stub"})

# Digests of catalogs that passed ``load_catalog`` in this process. Episodes and
# seals refuse any catalog digest not in this set (forged-origin guard).
_ADMITTED_DIGESTS: set[str] = set()


class CatalogIntegrityError(ValueError):
    """The catalog bytes or content are not admissible."""


@dataclass(frozen=True)
class Strategy:
    ordinal: int
    iri: str
    short_title: str
    status: str
    primitives: tuple[str, ...]

    @property
    def id(self) -> str:
        return f"sd-{self.ordinal:02d}"

    @property
    def policy(self) -> PolicyVector:
        return compose(self.primitives)

    @property
    def signature(self) -> str:
        """Operational identity: the primitive composition, not the label."""
        return ">".join(self.primitives)

    @property
    def concealed(self) -> bool:
        return concealed(self.primitives)


@dataclass(frozen=True)
class Catalog:
    sha256: str
    provenance: str
    non_claim: str
    strategies: tuple[Strategy, ...]

    def get(self, ordinal: int) -> Strategy:
        for strategy in self.strategies:
            if strategy.ordinal == ordinal:
                return strategy
        raise KeyError(f"no strategy with ordinal {ordinal}")

    @property
    def operationalized(self) -> tuple[Strategy, ...]:
        return tuple(s for s in self.strategies if s.status == "operationalized")


def _check(doc: dict) -> None:
    if doc.get("iri") != DOCTRINE_IRI or doc.get("prefix") != "sd":
        raise CatalogIntegrityError("catalog is not the sd: strategic-doctrine graph")
    if doc.get("authority") != "NONE":
        raise CatalogIntegrityError("catalog authority must be NONE")
    if doc.get("authority_ceiling") not in ("SELECT", "CONSTRUCT"):
        raise CatalogIntegrityError("catalog authority ceiling must be <= CONSTRUCT")
    if "no text reproduced" not in str(doc.get("non_claim", "")):
        raise CatalogIntegrityError("catalog licensing non-claim is absent")
    declared = tuple(
        p.get("name") if isinstance(p, dict) else None
        for p in doc.get("primitives", ())
    )
    if declared != PRIMITIVE_NAMES:
        raise CatalogIntegrityError("catalog primitive algebra differs from sd: 14")
    strategies = doc.get("strategies")
    if not isinstance(strategies, list):
        raise CatalogIntegrityError("catalog strategies is not a list")
    ordinals = [s.get("ordinal") if isinstance(s, dict) else None for s in strategies]
    if ordinals != list(range(1, 34)):
        raise CatalogIntegrityError("catalog must carry ordinals 1..33 in order")
    for entry in doc["strategies"]:
        _check_entry(entry)


def _check_entry(entry: object) -> None:
    if not isinstance(entry, dict):
        raise CatalogIntegrityError("catalog entry is not an object")
    ordinal = entry.get("ordinal")
    keys = set(entry)
    if "quote" in keys:
        raise CatalogIntegrityError(f"ordinal {ordinal} carries a quote")
    if keys != ENTRY_KEYS:
        extra = sorted(keys - ENTRY_KEYS)
        missing = sorted(ENTRY_KEYS - keys)
        raise CatalogIntegrityError(
            f"ordinal {ordinal} keys outside allow-list: extra={extra} missing={missing}"
        )
    iri = entry["iri"]
    local = f"strategy-{ordinal:02d}" if isinstance(ordinal, int) else None
    if local is None or iri not in (f"sd:{local}", f"{DOCTRINE_IRI}{local}"):
        raise CatalogIntegrityError(f"ordinal {ordinal} iri {iri!r} is not sd:")
    if entry["status"] not in STATUSES:
        raise CatalogIntegrityError(
            f"ordinal {ordinal} unknown status {entry['status']!r}"
        )
    title = entry["short_title"]
    if not isinstance(title, str) or len(title) > MAX_TITLE:
        raise CatalogIntegrityError(f"ordinal {ordinal} title too long")
    primitives = entry["primitives"]
    if not isinstance(primitives, list):
        raise CatalogIntegrityError(f"ordinal {ordinal} primitives is not a list")
    for name in primitives:
        if name not in PRIMITIVE_NAMES:
            raise CatalogIntegrityError(f"unknown primitive {name!r}")
    if entry["status"] == "operationalized" and not primitives:
        raise CatalogIntegrityError(f"ordinal {ordinal} has no primitives")
    if entry["status"] == "stub" and primitives:
        raise CatalogIntegrityError(f"ordinal {ordinal} is a stub with primitives")


def is_admitted(digest: str) -> bool:
    """True iff a catalog with this sha256 passed ``load_catalog`` in-process."""
    return digest in _ADMITTED_DIGESTS


def load_catalog(
    path: Path | str = CATALOG_PATH, *, expected_sha256: str = CATALOG_SHA256
) -> Catalog:
    data = Path(path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise CatalogIntegrityError(
            f"catalog sha256 {digest} does not match pinned {expected_sha256}"
        )
    try:
        doc = json.loads(data)
    except ValueError as exc:
        raise CatalogIntegrityError(f"catalog is not JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise CatalogIntegrityError("catalog is not a JSON object")
    _check(doc)
    catalog = Catalog(
        digest,
        doc["provenance"],
        doc["non_claim"],
        tuple(
            Strategy(
                s["ordinal"],
                s["iri"],
                s["short_title"],
                s["status"],
                tuple(s["primitives"]),
            )
            for s in doc["strategies"]
        ),
    )
    _ADMITTED_DIGESTS.add(digest)
    return catalog
