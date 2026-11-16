#!/usr/bin/env bash
# Runs every instance under each available solver; asserts selection vs expected.json. Exit 1 on mismatch.
set -u
# minizinc needs a real temp dir; an inherited TMPDIR that does not exist fails every gecode run
[ -d "${TMPDIR:-}" ] || export TMPDIR=/tmp
cd "$(dirname "$0")"
command -v minizinc >/dev/null || { echo "minizinc missing"; exit 2; }
python3 gen_instances.py >/dev/null || exit 2
SOLVERS="${SOLVERS:-gecode cbc}"
fail=0; n=0
for s in $SOLVERS; do
  for f in instances/*.dzn; do
    name=$(basename "$f" .dzn)
    out=$(timeout 60 minizinc --solver "$s" alignment_dispatch.mzn "$f" 2>&1); rc=$?
    line=$(printf '%s\n' "$out" | grep '^{' | tail -1)
    verdict=$(EXP="$name" LINE="$line" python3 - <<'P'
import json,os
e=json.load(open("expected.json"))[os.environ["EXP"]]
try: g=json.loads(os.environ["LINE"])
except Exception: print("UNPARSEABLE"); raise SystemExit
print("OK" if g==e else f"MISMATCH got={g} want={e}")
P
)
    n=$((n+1))
    if [ $rc -ne 0 ] || [ "$verdict" != OK ]; then fail=$((fail+1)); echo "FAIL [$s] $name rc=$rc $verdict"; printf '%s\n' "$out" | head -5; fi
  done
done
echo "ran=$n failed=$fail"
[ $fail -eq 0 ]
