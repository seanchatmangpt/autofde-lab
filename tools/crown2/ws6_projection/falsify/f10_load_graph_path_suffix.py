"""F10 (COSMETIC): load_graph slices basename[:-len('.json')] unconditionally, so a file
without .json suffix compares a truncated name; save_graph output renamed .JSON fails
for the wrong reason; a directory literally named '<digest>.json/' is not handled."""
from _target import *
import os, shutil, tempfile
d = tempfile.mkdtemp()
p = save_graph(d, empty_graph())
alt = p[:-5] + ".txt"
shutil.copy(p, alt)
try:
    load_graph(alt); print("NOT_REPRODUCED"); raise SystemExit(1)
except ValueError as e:
    print("load_graph(.txt copy of valid content):", str(e)[:90])
print("REPRODUCED: content-address check conflates suffix with digest")
