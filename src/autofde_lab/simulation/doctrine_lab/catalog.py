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

from .primitives import PRIMITIVE_NAMES, PRIMITIVES, compose, concealed

CATALOG_PATH = Path(__file__).with_name("data") / "catalog.json"
CATALOG_SHA256 = "49d404d32300e17704580455bbbd3e4a60773dbd1ff091c90e4a310a3bb65e30"
DOCTRINE_IRI = "https://ggen.dev/ontology/strategic-doctrine#"
MAX_TITLE = 60
CATALOG_SCHEMA = "autofde-lab.doctrine-lab.catalog/v1"
# The two allowed free-text values (provenance, non_claim) are bounded single-line
# strings: a short statement fits, a paragraph of source text does not.
MAX_FREE_TEXT = 160
# Allow-lists: anything outside them (free text such as ``quote`` or ``summary``)
# is refused, so no source text can ride in under a re-pinned digest.
TOP_LEVEL_KEYS = frozenset(
    {
        "iri",
        "prefix",
        "schema",
        "authority",
        "authority_ceiling",
        "non_claim",
        "provenance",
        "primitives",
        "strategies",
    }
)
ENTRY_KEYS = frozenset({"ordinal", "iri", "short_title", "status", "primitives"})
PRIMITIVE_KEYS = frozenset({"name", "dual", "iri"})
STATUSES = frozenset({"operationalized", "stub"})

# Catalogs that passed ``load_catalog`` in this process, by sha256. Episodes and
# seals refuse any catalog digest not in this map (forged-origin guard), and
# seals resolve the admitted Strategy from it to bind a receipt's signature.
_ADMITTED: dict[str, "Catalog"] = {}


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
    keys = set(doc)
    if keys != TOP_LEVEL_KEYS:
        raise CatalogIntegrityError(
            "catalog top-level keys outside allow-list: "
            f"extra={sorted(keys - TOP_LEVEL_KEYS)} "
            f"missing={sorted(TOP_LEVEL_KEYS - keys)}"
        )
    if doc["schema"] != CATALOG_SCHEMA:
        raise CatalogIntegrityError(
            f"catalog schema {doc['schema']!r} is not {CATALOG_SCHEMA}"
        )
    for field in ("provenance", "non_claim"):
        value = doc[field]
        if (
            not isinstance(value, str)
            or len(value) > MAX_FREE_TEXT
            or any(ch in value for ch in "\n\r")
        ):
            raise CatalogIntegrityError(
                f"catalog {field} is not a single-line string <= {MAX_FREE_TEXT} chars"
            )
    declared = tuple(
        p.get("name") if isinstance(p, dict) else None
        for p in doc.get("primitives", ())
    )
    if declared != PRIMITIVE_NAMES:
        raise CatalogIntegrityError("catalog primitive algebra differs from sd: 14")
    for primitive in doc["primitives"]:
        if not isinstance(primitive, dict):
            raise CatalogIntegrityError(f"primitive {primitive!r} is not an object")
        primitive_keys = set(primitive)
        if primitive_keys != PRIMITIVE_KEYS:
            raise CatalogIntegrityError(
                f"primitive {primitive.get('name')!r} keys outside allow-list: "
                f"extra={sorted(primitive_keys - PRIMITIVE_KEYS)} "
                f"missing={sorted(PRIMITIVE_KEYS - primitive_keys)}"
            )
        if primitive["iri"] != f"sd:{primitive['name']}":
            raise CatalogIntegrityError(
                f"primitive {primitive['name']!r} iri {primitive['iri']!r} is not sd:"
            )
        if primitive["dual"] != PRIMITIVES[primitive["name"]].dual:
            raise CatalogIntegrityError(
                f"primitive {primitive['name']!r} dual {primitive['dual']!r} "
                "differs from the sd: algebra"
            )
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
    return digest in _ADMITTED


def admitted_catalog(digest: str) -> Catalog | None:
    """The Catalog admitted in-process under ``digest``, or None."""
    return _ADMITTED.get(digest)


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    seen: set[str] = set()
    for key, _ in pairs:
        if key in seen:
            raise CatalogIntegrityError(f"duplicate JSON key {key!r} in catalog bytes")
        seen.add(key)
    return dict(pairs)


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
        doc = json.loads(data, object_pairs_hook=_no_duplicate_keys)
    except CatalogIntegrityError:
        raise
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
    _ADMITTED[digest] = catalog
    return catalog
