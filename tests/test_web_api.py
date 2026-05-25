"""API-level tests for the web UI backend (no HTTP client required)."""

from __future__ import annotations

from pathlib import Path

from hdl_sim.web.app import SimulateRequest, SourceFile, create_app

ROOT = Path(__file__).resolve().parents[1]
SILOS = ROOT / "examples" / "silos_regression.v"
AND2 = ROOT / "examples" / "lib" / "and2.v"
TB_MULTI = ROOT / "examples" / "tb_multi.v"


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


def test_simulate_multifile_via_app_handler() -> None:
    app = create_app()
    handler = next(
        r for r in app.routes if getattr(r, "path", None) == "/api/simulate"
    ).endpoint
    req = SimulateRequest(
        files=[
            SourceFile(path="lib/and2.v", content=AND2.read_text(encoding="utf-8")),
            SourceFile(path="tb_multi.v", content=TB_MULTI.read_text(encoding="utf-8")),
        ],
        top="tb_multi",
        until=5,
        max_events=200,
    )
    data = handler(req)
    assert data["ok"] is True
    assert data["top_module"] == "tb_multi"
    assert "done ry=" in data["console"]
    assert data["files_loaded"] == ["lib/and2.v", "tb_multi.v"]


def test_example_bundle_includes_lib() -> None:
    app = create_app()
    handler = next(
        r for r in app.routes if getattr(r, "path", None) == "/api/examples/{example_id:path}"
    ).endpoint
    data = handler("tb_multi.v")
    paths = [f["path"] for f in data["files"]]
    assert "lib/and2.v" in paths
    assert "tb_multi.v" in paths
    assert data["top"] == "tb_multi"


def test_ui_info_reports_ide_layout() -> None:
    app = create_app()
    handler = next(
        r for r in app.routes if getattr(r, "path", None) == "/api/ui-info"
    ).endpoint
    data = handler()
    assert data["ide_layout"] is True
    assert data["version"] == "0.3.0"
    assert data["version_label"] == "Ver 0.3.0"
