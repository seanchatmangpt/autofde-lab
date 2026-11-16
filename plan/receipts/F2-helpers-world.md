# F2-helpers-world
Standing: PASS

Base: no git state consulted (coordinator owns git). Moved nm, build, run_visit verbatim from
pipeline/tests/test_staged.py to pipeline/tests/helpers_world.py (60 lines); test_staged.py
now has `from helpers_world import build, nm, run_visit`.

Command: PYTHONPATH=pipeline:pipeline/tests uv run --quiet --with pytest ... pytest pipeline/tests/test_staged.py -q
Exit: 0. Output: `6 passed in 134.13s (0:02:14)`.
