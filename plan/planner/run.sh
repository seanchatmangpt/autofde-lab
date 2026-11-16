#!/bin/sh
# Plan + validate; exits nonzero if no plan or invalid plan.
D="$(cd "$(dirname "$0")" && pwd)"
[ -x "$D/.venv/bin/python" ] || { uv venv --python 3.12 "$D/.venv" -q && uv pip install -q --python "$D/.venv/bin/python" --prerelease=allow unified-planning up-aries || exit 4; }
if [ $# -ge 2 ]; then
  exec "$D/.venv/bin/python" -u "$D/plan.py" "$1" "$2" "${3:-/dev/null}"
fi
exec "$D/.venv/bin/python" -u "$D/plan.py" "$D/../spec/servengine_ideal_domain.pddl" "$D/../spec/problem_enterprise_ops.pddl" "$D/plan_solution.soln"
