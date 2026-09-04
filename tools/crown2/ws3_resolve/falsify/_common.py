"""Shared loader for WS3 falsifiers: imports the REAL resolve.py, no mocks."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import resolve as R  # noqa: E402
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
MARKET = os.path.expanduser("~/ggen-marketplace/packs")
ONTOLOGY = os.path.join(REPO, "ontology")

def base(ref):
    return os.path.basename(ref)
