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
    declared = tuple(p["name"] for p in doc.get("primitives", ()))
    if declared != PRIMITIVE_NAMES:
        raise CatalogIntegrityError("catalog primitive algebra differs from sd: 14")
    ordinals = [s["ordinal"] for s in doc.get("strategies", ())]
    if ordinals != list(range(1, 34)):
        raise CatalogIntegrityError("catalog must carry ordinals 1..33 in order")
    for entry in doc["strategies"]:
        if "quote" in entry:
            raise CatalogIntegrityError(f"ordinal {entry['ordinal']} carries a quote")
        if len(entry["short_title"]) > MAX_TITLE:
            raise CatalogIntegrityError(f"ordinal {entry['ordinal']} title too long")
        for name in entry["primitives"]:
            if name not in PRIMITIVE_NAMES:
                raise CatalogIntegrityError(f"unknown primitive {name!r}")
        if entry["status"] == "operationalized" and not entry["primitives"]:
            raise CatalogIntegrityError(f"ordinal {entry['ordinal']} has no primitives")


def load_catalog(
    path: Path | str = CATALOG_PATH, *, expected_sha256: str = CATALOG_SHA256
) -> Catalog:
    data = Path(path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise CatalogIntegrityError(
            f"catalog sha256 {digest} does not match pinned {expected_sha256}"
        )
    doc = json.loads(data)
    _check(doc)
    return Catalog(
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
