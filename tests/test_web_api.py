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
    data = handler("@project/and_gate")
    paths = [f["path"] for f in data["files"]]
    assert "lib/and2.v" in paths
    assert "tb_multi.v" in paths
    assert data["top"] == "tb_multi"
    assert data["kind"] == "project"


def test_counter_project_bundle() -> None:
    app = create_app()
    get_handler = next(
        r for r in app.routes if getattr(r, "path", None) == "/api/examples/{example_id:path}"
    ).endpoint
    sim_handler = next(
        r for r in app.routes if getattr(r, "path", None) == "/api/simulate"
    ).endpoint

    bundle = get_handler("@project/counter")
    assert len(bundle["files"]) == 2
    assert bundle["top"] == "tb_counter"

    req = SimulateRequest(
        files=[SourceFile(path=f["path"], content=f["content"]) for f in bundle["files"]],
        top=bundle["top"],
        until=50,
        max_events=500,
    )
    data = sim_handler(req)
    assert data["ok"] is True
    assert "COUNTER_PROJECT PASS" in data["console"]


def test_list_examples_includes_projects() -> None:
    app = create_app()
    handler = next(
        r for r in app.routes if getattr(r, "path", None) == "/api/examples"
    ).endpoint
    items = handler()
    ids = [i["id"] for i in items if i.get("kind") == "project"]
    assert "@project/counter" in ids


def test_ui_info_reports_ide_layout() -> None:
    app = create_app()
    handler = next(
        r for r in app.routes if getattr(r, "path", None) == "/api/ui-info"
    ).endpoint
    data = handler()
    assert data["ide_layout"] is True
    assert data["version"] == "0.4.3"
    assert data["version_label"] == "Ver 0.4.3"
    assert "spj_dir" in data


def test_spj_api_roundtrip() -> None:
    app = create_app()
    save_handler = next(
        r for r in app.routes if getattr(r, "path", None) == "/api/spj/{filename}"
        and "PUT" in getattr(r, "methods", set())
    ).endpoint
    load_handler = next(
        r for r in app.routes if getattr(r, "path", None) == "/api/spj/{filename}"
        and "GET" in getattr(r, "methods", set())
    ).endpoint
    payload = {
        "format": "hdl-sim-project",
        "version": 1,
        "name": "api_demo",
        "top": "tb",
        "files": [{"path": "tb.v", "content": "module tb; endmodule"}],
    }
    saved = save_handler("api_demo.spj", payload)
    assert saved["ok"] is True
    loaded = load_handler("api_demo.spj")
    assert loaded["top"] == "tb"
    assert loaded["files"][0]["path"] == "tb.v"
