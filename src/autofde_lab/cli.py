# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unified Typer entrypoint for AutoFDE Lab: Fabric, CMCA, OCEL 2.0, and BEAM Bridge."""

from __future__ import annotations

import typer

from autofde_lab.beam.beam_port_bridge import main as run_beam_bridge
from autofde_lab.cmca.cli import app as cmca_app
from autofde_lab.fabric.cli import app as fabric_app
from autofde_lab.ocel.cli import app as ocel_app
from autofde_lab.sa2a.cli import app as sa2a_app

app = typer.Typer(
    name="autofde",
    help="AutoFDE Lab: Autonomous Institutional Governance & Decision Engineering Substrate.",
    no_args_is_help=True,
)

app.add_typer(
    fabric_app,
    name="fabric",
    help="Decision fabric domains and solvers catalog, match, and solve.",
)
app.add_typer(
    cmca_app,
    name="cmca",
    help="CMCA multifractal consequence allocation and Q16.16 ranking.",
)
app.add_typer(
    ocel_app,
    name="ocel",
    help="OCEL 2.0 log validation, digests, and object-centric conformance.",
)
app.add_typer(
    sa2a_app,
    name="sa2a",
    help="Semantic Agent-to-Agent (SA2A) RFC-SA2A-001 v26.9.16 protocol and frontier governor.",
)


@app.command("beam-bridge")
def beam_bridge() -> None:
    """Run the BEAM cluster stdio JSON-lines port bridge loop."""
    run_beam_bridge()


def main() -> None:
    """Main CLI entrypoint."""
    app()


if __name__ == "__main__":
    main()
