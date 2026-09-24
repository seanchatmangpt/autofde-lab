"""Read-only command line for the Inverse Ecosystem Compiler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .anti_unification import AntiUnifier
from .brce_reference import brce_reference_system
from .ggen_create_adapter import GgenCreateAdapter
from .model import RepositorySubject, canonical_json
from .runner import PassiveCorpusRunner, RepositoryInput
from .structural import StructuralParserRegistry
from .tla_projection import render_tla


def _subject(args: argparse.Namespace) -> RepositorySubject:
    return RepositorySubject(
        repository=args.repository,
        revision=args.revision,
        default_branch=args.branch,
        visibility=args.visibility,
    )


def _scan(args: argparse.Namespace) -> int:
    result = PassiveCorpusRunner().run(
        (
            RepositoryInput(
                subject=_subject(args),
                root=args.root,
                included_paths=tuple(args.include) if args.include else None,
            ),
        )
    )
    repository = result.repositories[0]
    payload = {
        "run_id": result.run_id,
        "session_id": result.session.session_id,
        "subject_id": repository.subject.subject_id,
        "files": len(repository.inventory.entries),
        "total_bytes": repository.inventory.total_bytes,
        "skipped": repository.inventory.skipped,
        "structural": [
            {
                "path": path,
                "standing": document.standing.value,
                "language": document.language,
                "document_id": document.document_id,
            }
            for path, document in repository.structural_documents
        ],
        "receipt_ids": [receipt.receipt_id for receipt in result.receipts],
        "authority": "NONE",
    }
    if args.rdf:
        payload["rdf_projection"] = repository.rdf_projection
    print(canonical_json(payload))
    return 0


def _parse(args: argparse.Namespace) -> int:
    path = Path(args.path)
    content = path.read_bytes()
    document = StructuralParserRegistry().parse(
        path=path.name,
        content=content,
        source_digest="local:" + str(path.stat().st_mtime_ns),
    )
    print(canonical_json(document))
    return 0 if document.standing.value == "OBSERVED" else 2


def _anti_unify(args: argparse.Namespace) -> int:
    members = [json.loads(Path(path).read_text()) for path in args.json_files]
    result = AntiUnifier().generalize(
        members,
        member_ids=tuple(args.json_files),
    )
    print(
        canonical_json(
            {
                "generalization_id": result.generalization_id,
                "template": result.template,
                "substitutions": result.substitutions,
                "reconstructed": [
                    result.reconstruct(index) for index in range(len(members))
                ],
            }
        )
    )
    return 0


def _ggen_create_plan(args: argparse.Namespace) -> int:
    adapter = GgenCreateAdapter(
        executable_revision=args.ggen_create_revision,
    )
    plan = adapter.plan_capture(
        _subject(args),
        generator_name=args.generator,
        included_paths=tuple(args.include),
    )
    print(canonical_json(plan))
    return 0


def _brce_tla(args: argparse.Namespace) -> int:
    projection = render_tla(brce_reference_system())
    payload = {
        "projection_id": projection.projection_id,
        "source_system_id": projection.source_system_id,
        "module_name": projection.module_name,
        "tla": projection.tla,
        "cfg": projection.cfg,
        "verification": "NOT_RUN",
        "authority": "NONE",
    }
    print(canonical_json(payload))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m autofde_lab.iec",
        description="Inverse Ecosystem Compiler read-only exploration surface",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser(
        "scan", help="passively inventory and observe a checkout"
    )
    scan.add_argument("root")
    scan.add_argument("--repository", required=True)
    scan.add_argument("--revision", required=True)
    scan.add_argument("--branch", default="main")
    scan.add_argument(
        "--visibility",
        choices=("public", "private", "internal"),
        default="public",
    )
    scan.add_argument("--include", action="append", default=[])
    scan.add_argument("--rdf", action="store_true")
    scan.set_defaults(func=_scan)

    parse = subparsers.add_parser(
        "parse", help="structurally parse one known-format file"
    )
    parse.add_argument("path")
    parse.set_defaults(func=_parse)

    anti = subparsers.add_parser("anti-unify", help="generalize JSON structures")
    anti.add_argument("json_files", nargs="+")
    anti.set_defaults(func=_anti_unify)

    plan = subparsers.add_parser(
        "ggen-create-plan",
        help="construct zero-authority ggen-create invocation intents",
    )
    plan.add_argument("--repository", required=True)
    plan.add_argument("--revision", required=True)
    plan.add_argument("--branch", default="main")
    plan.add_argument(
        "--visibility",
        choices=("public", "private", "internal"),
        default="public",
    )
    plan.add_argument("--ggen-create-revision", required=True)
    plan.add_argument("--generator", required=True)
    plan.add_argument("--include", action="append", required=True)
    plan.set_defaults(func=_ggen_create_plan)

    tla = subparsers.add_parser(
        "brce-tla",
        help="render BRCE reference TLA+ without executing a model checker",
    )
    tla.set_defaults(func=_brce_tla)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
