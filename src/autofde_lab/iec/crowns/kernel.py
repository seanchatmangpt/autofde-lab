"""The semantic kernel a generator pack exposes to its template.

For a ggen_igniter pack (`priv/ggen/<pack>/{ontology.ttl, gates/*.rq, templates/}`,
the fixed layout in ggen_igniter `priv/ggen/CLAUDE.md`), the kernel is exactly what
the template can see: the rows each gate query returns over the pack ontology,
bound under the gate's stem with any `^\\d+_` prefix stripped (ggen_igniter
`lib/ggen_igniter/pack.ex:408-420`).

The rows are recomputed here with rdflib -- an engine independent of the ones
ggen_igniter ships (oxigraph by default, Elixir `sparql`, QLever). That is
deliberate: the kernel IEC regenerates from must not be read back out of the
committed output it is about to be compared against. The engine identity is part
of every kernel record, because a different engine is a different observation.

Declaration facts (`pack.name`, `template.to`, ...) are kept apart from kernel
rows. They are facts about the generator, not about the domain, and conflating
the two would hide exactly the finding IEC exists to surface: a template that
restates its own declaration as literal text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .census import Census, read_blob
from .model import IECRefusal, content_id
from .templates import split_frontmatter

__all__ = ["PackKernel", "pack_kernel"]

_GATE_PREFIX = re.compile(r"^\d+_")
# Declarations that name something (a path, a pack). Enum-valued keys such as
# `template.mode = file` are excluded: "file" is an English word, and binding it
# would report every prose use of the word as a restated declaration.
_NAME_LIKE_DECLARATIONS = (
    "pack.name",
    "pack.dir",
    "pack.ontology",
    "template.path",
    "template.to",
)


@dataclass(frozen=True)
class PackKernel:
    pack: str
    pack_dir: str
    template_path: str
    template_text: str
    ontology_path: str
    ontology_blob: str
    gates: dict[str, dict[str, str]]  # binding name -> {path, blob}
    rows: dict[str, tuple[dict[str, str], ...]]
    declaration: dict[str, str]
    engine: dict[str, str]

    @property
    def id(self) -> str:
        return content_id(self.to_json(include_id=False))

    def facts(self) -> dict[str, str]:
        """Every kernel and declaration value, keyed by a stable source name."""
        out: dict[str, str] = {}
        for binding, rows in self.rows.items():
            for index, row in enumerate(rows):
                for var, value in row.items():
                    out[f"kernel:{binding}[{index}].{var}"] = value
        for key, value in self.declaration.items():
            if key in _NAME_LIKE_DECLARATIONS:
                out[f"declaration:{key}"] = value
        return out

    def to_json(self, *, include_id: bool = True) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schema": "autofde-lab.iec.pack-kernel/1",
            "pack": self.pack,
            "pack_dir": self.pack_dir,
            "template_path": self.template_path,
            "ontology_path": self.ontology_path,
            "ontology_blob": self.ontology_blob,
            "gates": self.gates,
            "rows": {name: list(rows) for name, rows in self.rows.items()},
            "declaration": self.declaration,
            "engine": self.engine,
        }
        if include_id:
            record["id"] = self.id
        return record


def _lexical(term: Any) -> str:
    return str(term)


def pack_kernel(census: Census, checkout: Path, template_path: str) -> PackKernel:
    """Recompute the kernel a pack template sees, from the frozen commit only."""
    import rdflib

    template_dir = PurePosixPath(template_path).parent
    if template_dir.name != "templates":
        raise IECRefusal(
            "UNSUPPORTED_GENERATOR_CAPABILITY", f"{template_path} is not in a pack"
        )
    pack_dir = template_dir.parent
    subject = census.subject
    ontology_path = str(pack_dir / "ontology.ttl")
    ontology_record = census.file(ontology_path)
    template_text = read_blob(subject, checkout, template_path).decode("utf-8")
    header, unsupported, _body = split_frontmatter(template_text)

    graph = rdflib.Graph()
    graph.parse(
        data=read_blob(subject, checkout, ontology_path).decode("utf-8"),
        format="turtle",
    )

    gates: dict[str, dict[str, str]] = {}
    rows: dict[str, tuple[dict[str, str], ...]] = {}
    gate_prefix = f"{pack_dir}/gates/"
    for record in census.files:
        if not (record.path.startswith(gate_prefix) and record.path.endswith(".rq")):
            continue
        if "/" in record.path[len(gate_prefix) :]:
            continue
        name = _GATE_PREFIX.sub("", PurePosixPath(record.path).stem)
        query = read_blob(subject, checkout, record.path).decode("utf-8")
        result = graph.query(query)
        variables = [str(var) for var in result.vars]
        extracted = []
        for row in result:
            extracted.append(
                {
                    var: _lexical(row[i])
                    for i, var in enumerate(variables)
                    if row[i] is not None
                }
            )
        extracted.sort(key=lambda item: content_id(item))
        gates[name] = {"path": record.path, "blob": record.object_id}
        rows[name] = tuple(extracted)
    if not gates:
        raise IECRefusal("BLOCKED_MISSING_PARSER", f"{pack_dir} has no gates/*.rq")

    declaration = {
        "pack.name": pack_dir.name,
        "pack.dir": str(pack_dir),
        "pack.ontology": ontology_path,
        "template.path": template_path,
    }
    for key, value in (header or {}).items():
        declaration[f"template.{key}"] = value
    if unsupported:
        declaration["template.unsupported_keys"] = ",".join(unsupported)
    return PackKernel(
        pack=pack_dir.name,
        pack_dir=str(pack_dir),
        template_path=template_path,
        template_text=template_text,
        ontology_path=ontology_path,
        ontology_blob=ontology_record.object_id,
        gates=gates,
        rows=rows,
        declaration=declaration,
        engine={"name": "rdflib", "version": rdflib.__version__},
    )
