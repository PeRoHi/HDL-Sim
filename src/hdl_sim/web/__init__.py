"""Web UI server for HDL-Sim."""

from __future__ import annotations


def create_app():
    """Create the FastAPI app without importing web dependencies at package import time."""

    from hdl_sim.web.app import create_app as _create_app

    return _create_app()


def main() -> int:
    """Run the browser UI."""

    from hdl_sim.web.launcher import main as _main

    return _main()


__all__ = ["create_app", "main"]
