import json, sys
from .solver import solve

def main() -> int:
    try:
        data = json.load(sys.stdin)
        out = solve(data)
    except (ValueError, KeyError, TypeError) as e:
        json.dump({"error": f"{type(e).__name__}: {e}"}, sys.stdout)
        print()
        return 2
    json.dump(out, sys.stdout, indent=2)
    print()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
