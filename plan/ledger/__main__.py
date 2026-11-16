import json, sys
from .core import LedgerError, settle


def main() -> int:
    try:
        out = settle(json.load(sys.stdin)).as_dict()
    except (LedgerError, json.JSONDecodeError) as e:
        json.dump({"refused": type(e).__name__, "detail": str(e)}, sys.stdout)
        print()
        return 2
    json.dump(out, sys.stdout)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
