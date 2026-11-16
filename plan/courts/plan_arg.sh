#!/bin/sh
# Court shim: planner/run.sh hardcodes spec/ paths and ignores its args, so mutants would never
# be seen. This invokes L1's SAME toolchain (planner/.venv + planner/plan.py) on <domain> <problem>.
# exit codes pass through plan.py: 0 solved+validated, 2 NO PLAN, 3 invalid plan, 4 no venv.
P="$(cd "$(dirname "$0")/../planner" && pwd)"
[ -x "$P/.venv/bin/python" ] || exit 4
OUT="$(cd "$(dirname "$0")" && pwd)/work/plan.$$.soln"
"$P/.venv/bin/python" -u "$P/plan.py" "$1" "$2" "$OUT"; rc=$?
rm -f "$OUT"; exit $rc
