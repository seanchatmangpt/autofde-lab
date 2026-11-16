#!/usr/bin/env bash
set -u
miss=0
for t in minizinc uv python3 just; do
  if command -v "$t" >/dev/null 2>&1; then echo "ok   $t: $(command -v $t)"; else echo "MISSING $t" >&2; miss=1; fi
done
if python3 -c "import ortools; print('ok   ortools', ortools.__version__)" 2>/dev/null; then :; else
  if uv run --quiet --with ortools python -c "import ortools; print('ok   ortools (via uv)', ortools.__version__)" 2>/dev/null; then :; else echo "MISSING ortools" >&2; miss=1; fi
fi
[ $miss -eq 0 ] || { echo "bootstrap FAILED" >&2; exit 1; }
echo "bootstrap OK"
