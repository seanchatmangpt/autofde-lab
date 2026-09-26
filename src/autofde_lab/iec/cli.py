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


def _tlc_court(args: argparse.Namespace) -> int:
    from .brce_mutants import brce_mutant
    from .tlc_court import (
        DEADLOCK_EXEMPTION_REASON,
        TlaToolchain,
        TlcVerdict,
        court,
        write_court_outputs,
    )

    if args.model == "brce":
        system = brce_reference_system()
    elif args.model.startswith("mutant:"):
        system = brce_mutant(args.model.split(":", 1)[1])
    elif args.model == "delegation-admission":
        from .delegation_admission_formal import delegation_admission_system

        system = delegation_admission_system()
    elif args.model.startswith("delegation-mutant:"):
        from .delegation_admission_formal import (
            DelegationAdmissionMutant,
            delegation_admission_mutant,
        )

        kind = DelegationAdmissionMutant(args.model.split(":", 1)[1])
        system = delegation_admission_mutant(kind)
    else:
        raise SystemExit(
            f"unknown model {args.model!r}; use brce, mutant:<KIND>, "
            "delegation-admission, or delegation-mutant:<KIND>"
        )
    tc = TlaToolchain.discover(args.jar)
    out = Path(args.out)
    if not isinstance(tc, TlaToolchain):
        out.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": args.model,
            "verdict": "REFUSED" if tc.refused else "UNSUPPORTED",
            "code": tc.code,
            "reason": tc.reason,
            "authority": "NONE",
        }
        (out / "receipt.json").write_text(canonical_json(payload) + "\n")
        print(canonical_json(payload))
        return 3
    receipt = court(
        system,
        tc,
        workdir=out / "work",
        deadlock_check=False,
        deadlock_reason=DEADLOCK_EXEMPTION_REASON,
        replay_command=f"python -m autofde_lab.iec tlc-court --model {args.model} --out <DIR>",
    )
    write_court_outputs(receipt, out)
    (out / f"{system.name}.tla").write_text(
        (out / "work" / f"{system.name}.tla").read_text()
    )
    print(
        canonical_json(
            {
                "model": args.model,
                "module": system.name,
                "parse": receipt.payload["parse"]["verdict"],
                "model_check": receipt.payload["model_check"],
                "verdicts": receipt.verdicts,
                "receipt_digest": receipt.payload["receipt_digest"],
                "replay_identity": receipt.replay_identity,
            }
        )
    )
    ok = receipt.payload["model_check"] == TlcVerdict.MODEL_CHECK_ALIVE.value
    return 0 if ok else 2



def _delegation_admission(args: argparse.Namespace) -> int:
    from .crowns.delegation_admission import main as delegation_main

    argv = [args.candidate, args.receipt]
    if args.reference:
        argv.extend(["--reference", args.reference])
    if args.gate:
        argv.append("--gate")
    return delegation_main(argv)


def _delegation_admission_benchmark(args: argparse.Namespace) -> int:
    from .crowns.delegation_admission_benchmark import main as benchmark_main

    argv = [
        args.candidate,
        args.receipt,
        "--max-units",
        str(args.max_units),
    ]
    if args.gate:
        argv.append("--gate")
    return benchmark_main(argv)


def _delegation_admission_history(args: argparse.Namespace) -> int:
    from .crowns.delegation_admission_history import main as history_main

    argv = [args.history, args.receipt]
    if args.gate:
        argv.append("--gate")
    return history_main(argv)


def _delegation_admission_batch(args: argparse.Namespace) -> int:
    from .crowns.delegation_admission_batch import main as batch_main

    argv = [args.batch, args.receipt]
    if args.gate:
        argv.append("--gate")
    return batch_main(argv)


def _delegation_admission_repair(args: argparse.Namespace) -> int:
    from .crowns.delegation_admission_repair import main as repair_main

    argv = [args.candidate, args.receipt]
    if args.costs:
        argv.extend(["--costs", args.costs])
    return repair_main(argv)


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

    tlc = subparsers.add_parser(
        "tlc-court",
        help="run SANY + TLC (pinned tla2tools.jar) on the BRCE reference or a mutant",
    )
    tlc.add_argument(
        "--model",
        required=True,
        help=(
            "brce | mutant:<BRCE_KIND> | delegation-admission | "
            "delegation-mutant:<UNBOUNDED_DELEGATION|SELF_VERIFICATION|"
            "MODIFY_WITHOUT_CHANGE|STANDING_WITHOUT_CAPACITY>"
        ),
    )
    tlc.add_argument("--out", required=True)
    tlc.add_argument("--jar", default=None, help="tla2tools.jar path (digest-checked)")
    tlc.set_defaults(func=_tlc_court)

    delegation = subparsers.add_parser(
        "delegation-admission",
        help="evaluate one exact-subject delegation/admission artifact",
    )
    delegation.add_argument("candidate")
    delegation.add_argument("receipt")
    delegation.add_argument("--reference")
    delegation.add_argument("--gate", action="store_true")
    delegation.set_defaults(func=_delegation_admission)

    benchmark = subparsers.add_parser(
        "delegation-admission-benchmark",
        help="run mutation and capacity-sweep courts",
    )
    benchmark.add_argument("candidate")
    benchmark.add_argument("receipt")
    benchmark.add_argument("--max-units", type=int, default=32)
    benchmark.add_argument("--gate", action="store_true")
    benchmark.set_defaults(func=_delegation_admission_benchmark)

    history = subparsers.add_parser(
        "delegation-admission-history",
        help="evaluate an ordered delegation/admission history",
    )
    history.add_argument("history")
    history.add_argument("receipt")
    history.add_argument("--gate", action="store_true")
    history.set_defaults(func=_delegation_admission_history)

    batch = subparsers.add_parser(
        "delegation-admission-batch",
        help="evaluate generated marketplace delegation batches",
    )
    batch.add_argument("batch")
    batch.add_argument("receipt")
    batch.add_argument("--gate", action="store_true")
    batch.set_defaults(func=_delegation_admission_batch)

    repair = subparsers.add_parser(
        "delegation-admission-repair",
        help="plan minimum numeric evidence-scope repair",
    )
    repair.add_argument("candidate")
    repair.add_argument("receipt")
    repair.add_argument("--costs")
    repair.set_defaults(func=_delegation_admission_repair)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
