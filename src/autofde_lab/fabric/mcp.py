# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""FastMCP projection of the shared scikit-decide decision fabric."""

from __future__ import annotations

from typing import Any

from autofde_lab.fabric.dspy import DecisionCompiler, compile_request_text
from autofde_lab.fabric.models import DecisionRequest
from autofde_lab.fabric.service import DecisionFabric


def create_server(
    fabric: DecisionFabric | None = None,
    *,
    compiler: DecisionCompiler | None = None,
) -> Any:
    """Create a FastMCP server without duplicating decision semantics."""
    try:
        from fastmcp import FastMCP
    except ImportError as error:
        raise RuntimeError(
            "FastMCP is unavailable; install requirements-agentic.txt"
        ) from error

    service = fabric or DecisionFabric()
    server = FastMCP("scikit-decide-fabric")

    @server.tool
    def decision_catalog() -> dict[str, Any]:
        """List registered decision domains and solvers."""
        return service.catalog().as_dict()

    @server.tool
    def decision_match(
        domain: str,
        domain_arguments: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Return compatible solvers for a constructed domain."""
        return service.match(
            domain,
            domain_arguments=domain_arguments,
            use_cache=use_cache,
        ).as_dict()

    @server.tool
    def decision_solve(request: dict[str, Any]) -> dict[str, Any]:
        """Solve and return a receipt-bearing bounded trajectory."""
        return service.solve(DecisionRequest.from_dict(request)).as_dict()

    @server.tool
    def decision_cache_stats() -> dict[str, Any]:
        """Return exact reuse and avoidance metrics."""
        return service.cache_stats()

    @server.tool
    def decision_cache_hotset() -> dict[str, Any]:
        """Return the measured 80/20 hot set."""
        return service.cache_hotset()

    if compiler is not None:

        @server.tool
        def decision_compile(job: str) -> dict[str, Any]:
            """Compile a natural-language job at the DSPy frontier."""
            return compile_request_text(job, service.catalog(), compiler).as_dict()

    return server


def main() -> None:
    """Run the MCP server over stdio."""
    create_server().run()


if __name__ == "__main__":
    main()
