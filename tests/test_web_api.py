"""API-level tests for the web UI backend (no HTTP client required)."""

from __future__ import annotations

from pathlib import Path

from hdl_sim.web.app import SimulateRequest, SourceFile, create_app

ROOT = Path(__file__).resolve().parents[1]
SILOS = ROOT / "examples" / "silos_regression.v"


def test_simulate_silos_via_app_handler() -> None:
    app = create_app()
    handler = next(
        r for r in app.routes if getattr(r, "path", None) == "/api/simulate"
    ).endpoint
    req = SimulateRequest(
        files=[
            SourceFile(path="silos_regression.v", content=SILOS.read_text(encoding="utf-8"))
        ],
        top="silos_regression_tb",
        until=50,
        max_events=500,
    )
    data = handler(req)
    assert data["ok"] is True
    assert "SILOS_REGRESSION PASS" in data["console"]
    assert data["waveform"] is not None
    assert len(data["signals"]) >= 3
