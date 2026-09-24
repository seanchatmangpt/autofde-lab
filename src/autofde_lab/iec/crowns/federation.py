"""IEC-004: federate ggen-create instead of re-implementing it (PR-005).

ggen-create (`seanchatmangpt/ggen-create`) is the existing exemplar -> ggen package
reverse compiler. IEC calls it; it does not copy it. Two of its capabilities are
used, both pure standard-library Python that run in-process from a pinned
checkout (`src/ggen_create/`), with no `ggen` binary and no network:

* `legacy_model.plan_legacy_factory` -- its repository observation, which
  assigns every file a *role* class (test, schema, template, ...). IEC joins that
  to its own census by path **and** content digest; a digest mismatch means the
  working tree ggen-create walked is not the frozen commit, and the join refuses
  rather than attach a role to the wrong bytes.
* `cases.render_concrete_many` -- its case-family renderer: an exemplar text plus
  named seed identifiers, re-rendered with new values. IEC uses it as a held-out
  predictor for a file family: learn nothing new, render member k from member j
  with ggen-create, compare.

Where ggen-create refuses (`PARAMETER_VALUE_REFUSED` for a path-valued seed,
`PARAMETER_COLLISION_REFUSED` for overlapping seeds), the refusal code is kept as
an exact capability falsifier. That falsifier -- not preference -- is what licenses
IEC to keep its own whole-value generalization for that hole.

The checkout's identity is verified before import, and the imported module must
resolve inside that checkout, so a different installed `ggen_create` can never be
exercised in its place.
"""

from __future__ import annotations

import hashlib
import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Sequence

from .census import Census, read_blob
from .corpus import RepositorySubject, observe_checkout
from .model import IECRefusal, content_id

__all__ = ["GgenCreate"]


class GgenCreate:
    """An exact-subject handle on a ggen-create checkout."""

    def __init__(
        self,
        checkout: Path,
        *,
        repository: str = "seanchatmangpt/ggen-create",
        branch: str = "main",
        commit: str = "HEAD",
    ) -> None:
        self.checkout = Path(checkout)
        self.subject: RepositorySubject = observe_checkout(
            self.checkout,
            repository=repository,
            branch=branch,
            visibility="public",
            inclusion_reason="IEC-004: federated reverse-compiler primitive",
            commit=commit,
        )
        self.cases = self._load("ggen_create.cases")
        self.legacy = self._load("ggen_create.legacy_model")
        self.model = self._load("ggen_create.model")

    def _load(self, name: str) -> ModuleType:
        source = (self.checkout / "src").resolve()
        loaded = sys.modules.get("ggen_create")
        if loaded is not None and not Path(
            loaded.__file__ or ""
        ).resolve().is_relative_to(source):
            raise IECRefusal(
                "REFUSED_AMBIGUOUS_AUTHORITY",
                f"a different ggen_create is already imported from {loaded.__file__}",
            )
        sys.path.insert(0, str(source))
        try:
            module = importlib.import_module(name)
        finally:
            sys.path.remove(str(source))
        if not Path(module.__file__ or "").resolve().is_relative_to(source):
            raise IECRefusal(
                "REFUSED_AMBIGUOUS_AUTHORITY", f"{name} resolved outside {source}"
            )
        return module

    def identity(self) -> dict[str, str]:
        return {
            "repository": self.subject.repository,
            "commit": self.subject.commit,
            "tree": self.subject.tree,
            "app_version": str(self.model.APP_VERSION),
        }

    def role_classes(self, census: Census, subject_checkout: Path) -> dict[str, Any]:
        """ggen-create's role class per file, joined to the census by path and digest."""
        manifest = self.legacy.plan_legacy_factory(Path(subject_checkout))
        by_path = {item["path"]: item for item in manifest["files"]}
        joined, contradicted, unobserved = {}, [], []
        for record in census.files:
            item = by_path.get(record.path)
            if item is None:
                unobserved.append(record.path)
                continue
            blob = read_blob(census.subject, Path(subject_checkout), record.path)
            if item["sha256"] != "sha256:" + hashlib.sha256(blob).hexdigest():
                contradicted.append(record.path)
                continue
            joined[record.path] = item["class"]
        counts: dict[str, int] = {}
        for role in joined.values():
            counts[role] = counts.get(role, 0) + 1
        return {
            "producer": self.identity(),
            "predicate": "ggen-create:roleClass",
            "standing": "DERIVED_DETERMINISTIC",
            "reading": "the class ggen-create's classifier assigns; a role (test, schema, "
            "template...), orthogonal to IEC's artifact origin",
            "joined": len(joined),
            "role_counts": dict(sorted(counts.items())),
            "contradicted_by_digest": contradicted,
            "not_observed_by_ggen_create": unobserved,
            "roles": dict(sorted(joined.items())),
        }

    def render(
        self,
        exemplar: str,
        seeds: Sequence[tuple[str, str]],
        values: Sequence[tuple[str, str]],
    ) -> dict[str, Any]:
        """ggen-create's own concrete render, or its own typed refusal.

        One seed goes through `cases.render_concrete`, the single-seed renderer
        its parity crown exercises; several go through `render_concrete_many`,
        whose defect `differential_probe` records.
        """
        try:
            if len(seeds) == 1:
                api = "cases.render_concrete"
                text, replacements = self.cases.render_concrete(
                    exemplar, seeds[0][1], values[0][1]
                )
            else:
                api = "cases.render_concrete_many"
                text, replacements = self.cases.render_concrete_many(
                    exemplar, list(seeds), list(values)
                )
        except self.model.GgenCreateError as error:
            return {
                "refused": True,
                "api": api,
                "code": error.code,
                "detail": str(error.detail),
            }
        return {
            "refused": False,
            "api": api,
            "text": text,
            "replacements": len(replacements),
        }

    def differential_probe(self, scratch: Path) -> dict[str, Any]:
        """Does `render_concrete_many` agree with `render_concrete` on one seed?

        Its docstring promises "Like `render_concrete`, generalized to multiple
        seeds". The probe checks that promise on ggen-create's own greeter path,
        then drives the public capture lifecycle (start / add / usename / generate)
        in `scratch` -- never in the ggen-create checkout -- to see whether any
        disagreement reaches a user-visible decision.
        """
        single = self.cases.render_concrete("dist/hello.js", "hello", "hola")[0]
        many = self.cases.render_concrete_many(
            "dist/hello.js", [("name", "hello")], [("name", "hola")]
        )[0]
        record: dict[str, Any] = {
            "contract": "render_concrete_many(x, [(name, s)], [(name, v)]) == render_concrete(x, s, v)",
            "input": {"text": "dist/hello.js", "seed": "hello", "value": "hola"},
            "render_concrete": single,
            "render_concrete_many": many,
            "verdict": "PASS" if single == many else "COUNTEREXAMPLE",
        }
        session = self._load("ggen_create.session")
        package = self._load("ggen_create.package")
        root = Path(scratch)
        for relative, body in (
            ("src/hello.js", 'console.log("Hello!")\n'),
            ("test/hello.js", 'console.log("Hello test")\n'),
        ):
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            (root / relative).write_text(body, encoding="utf-8")
        session_path = session.start_session(root, "greeter")
        session.add_paths(session_path, ["src/hello.js", "test/hello.js"], cwd=root)
        session.set_seed(session_path, "Hello")
        try:
            built = package.build_package(session_path, root / "_ggen")
            record["lifecycle"] = {"refused": False, "package": built.package_dir.name}
        except self.model.GgenCreateError as error:
            record["lifecycle"] = {
                "refused": True,
                "code": error.code,
                "detail": str(error.detail),
            }
        record["lifecycle"]["steps"] = [
            "start greeter",
            "add src/hello.js test/hello.js",
            "usename Hello",
            "generate (package.build_package into the scratch root)",
        ]
        return record

    def family_heldout(
        self,
        texts: Sequence[str],
        facts: Sequence[Mapping[str, str]],
        seed_keys: Sequence[str],
    ) -> list[dict[str, Any]]:
        """Predict each member from the previous one via ggen-create alone.

        Seeds are the exemplar's values for `seed_keys`; values are the held-out
        member's values for the same keys. The first key is ggen-create's
        unprefixed `name` seed; the others are named `s1`, `s2`, ... because
        ggen-create splits prefixed variables on the first underscore.
        """
        names = ["name", *[f"s{index}" for index in range(1, len(seed_keys))]]
        results = []
        for held in range(len(texts)):
            exemplar = (held - 1) % len(texts)
            seeds = [
                (name, facts[exemplar][key]) for name, key in zip(names, seed_keys)
            ]
            values = [(name, facts[held][key]) for name, key in zip(names, seed_keys)]
            rendered = self.render(texts[exemplar], seeds, values)
            record: dict[str, Any] = {
                "held_out_member": held,
                "exemplar_member": exemplar,
                "seed_keys": list(seed_keys),
            }
            if rendered["refused"]:
                record.update(
                    verdict="UNSUPPORTED",
                    ggen_create_refusal=rendered["code"],
                    detail=rendered["detail"],
                )
            else:
                record.update(
                    verdict="PASS"
                    if rendered["text"] == texts[held]
                    else "COUNTEREXAMPLE",
                    predicted_digest=content_id(rendered["text"]),
                )
                if rendered["text"] != texts[held]:
                    record.update(predicted=rendered["text"], actual=texts[held])
            results.append(record)
        return results
