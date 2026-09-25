# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""``python -m autofde_lab.aloop LOG.ocel.json [--out RECEIPT.json] [seal options]``.

Exit codes: 0 qualified (sealed + complete + every rule holds), 3 not
qualified OR consistent under assumed completeness (typed; an unsealed log
never exits 0), 2 refused (malformed or forged log, or a sealed log whose
chain, signature, bijection or completeness fails). The receipt is printed to
stdout when ``--out`` is omitted.

Seal options (sealed-recorder profile, court r9): ``--seal LEDGER.jsonl``
``--key-file FILE --key-id ID`` (recorder verification key; never inside the
log), completeness witnesses ``--git REPO_OBJECT_ID=PATH:REV_RANGE``
(repeatable; real ``git rev-list`` plus the committer clock of the range and
its base, which anchors the log's epoch) and ``--human-ledger FILE`` (JSON list
of ``{"id", "time"}`` human messages; every entry must be sealed).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from autofde_lab.aloop.court import evaluate_path, write_receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m autofde_lab.aloop")
    parser.add_argument("log", type=Path, help="OCEL 2.0 JSON log")
    parser.add_argument("--out", type=Path, default=None, help="receipt output path")
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--subject-sha", default=None, help="exact court subject SHA")
    parser.add_argument(
        "--locator", default=None, help="provenance locator for the log bytes"
    )
    parser.add_argument(
        "--seal", type=Path, default=None, help="sealed-recorder ledger"
    )
    parser.add_argument("--key-file", type=Path, default=None)
    parser.add_argument("--key-id", default=None)
    parser.add_argument(
        "--git",
        action="append",
        default=[],
        metavar="REPO_ID=PATH:RANGE",
        help="commit completeness witness (git rev-list RANGE in PATH)",
    )
    parser.add_argument("--human-ledger", type=Path, default=None)
    args = parser.parse_args(argv)
    seal = None
    if args.seal is not None:
        from autofde_lab.aloop.seal import (
            SealInputs,
            git_witness,
            keyring_from_file,
            load_json,
        )

        if args.key_file is None or not args.key_id:
            parser.error("--seal requires --key-file and --key-id")
        keyring, key = keyring_from_file(args.key_file, args.key_id)
        commits = None
        clock = None
        if args.git:
            commits, clock = {}, {}
            for spec in args.git:
                repo_id, _, rest = spec.partition("=")
                path, _, rev_range = rest.rpartition(":")
                commits[repo_id], clock[repo_id] = git_witness(path, rev_range)
        humans = load_json(args.human_ledger) if args.human_ledger else None
        seal = SealInputs(
            ledger=args.seal,
            keyring=keyring,
            commits=commits,
            human_messages=humans,
            key_material=(key,),
            commit_clock=clock,
        )
    code, receipt = evaluate_path(
        args.log,
        profile_path=args.profile,
        court_subject_sha=args.subject_sha,
        log_locator=args.locator,
        seal=seal,
    )
    if args.out is not None:
        write_receipt(receipt, args.out)
    else:
        sys.stdout.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    sys.stderr.write(f"{receipt['court']} verdict={receipt['verdict']} exit={code}\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
