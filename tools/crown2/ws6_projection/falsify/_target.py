"""Import shim: pulls the real WS6 target (no copies, no mocks)."""
import os, sys
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from capability_graph import *  # noqa: F401,F403
from capability_graph import QualifiedCapabilityReceipt, add_qualified, empty_graph, project_domain, digest_of, graph_digest  # noqa: F401
