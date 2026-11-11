"""``python -m autofde_lab.coprocessor <kind>``: envelope on stdin, canonical JSON out."""

from __future__ import annotations

import sys

from autofde_lab.coprocessor import envelope as E


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write("usage: python -m autofde_lab.coprocessor <kind> < envelope.json\n")
        return 0 if argv else 2
    kind = argv[0]
    try:
        env = E.Envelope.from_json(sys.stdin.read())
    except Exception as exc:  # noqa: BLE001
        res = E.refused(f"bad envelope: {exc}", kind=kind)
        sys.stdout.write(E.canonical_json(res.to_dict()) + "\n")
        return res.exit_code()
    env = E.Envelope(kind=kind, payload=env.payload, options=env.options)
    E.load_kind_modules()
    res = E.dispatch(env)
    sys.stdout.write(E.canonical_json(res.to_dict()) + "\n")
    return res.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
