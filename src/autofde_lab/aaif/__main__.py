# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""CLI execution entrypoint for AutoFDE AAIF FastMCP server.

Invoked via ``python -m autofde_lab.aaif`` as declared in ``mcp/mcp_servers.json``.
Runs the FastMCP server over standard input/output (stdio) transport.
"""

from __future__ import annotations

import sys
from autofde_lab.aaif import build_mcp_server
from autofde_lab.fabric.service import DecisionFabric


def main() -> None:
    fabric = DecisionFabric()
    server = build_mcp_server(fabric)
    server.run()


if __name__ == "__main__":
    main()
