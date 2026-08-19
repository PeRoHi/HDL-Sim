"""Saving .spj writes edited content to verilog_sources, not source_path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hdl_sim.web import spj_store
from hdl_sim.web.app import create_app


@pytest.fixture()
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr("hdl_sim.web.paths.user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("hdl_sim.web.spj_store.user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("hdl_sim.web.app.user_data_dir", lambda: tmp_path)
    (tmp_path / "spj").mkdir()
    return tmp_path


def _save_endpoint(app):
    return next(
        r
        for r in app.routes
        if getattr(r, "path", None) == "/api/spj/{filename}"
        and "PUT" in getattr(r, "methods", set())
    ).endpoint


def test_spj_save_writes_verilog_sources_not_source_path(isolated_data) -> None:
    src = isolated_data / "design.v"
    src.write_text("module m; endmodule\n", encoding="utf-8")
    original = src.read_text(encoding="utf-8")

    app = create_app()
    payload = {
        "format": "hdl-sim-project",
        "version": 1,
        "name": "demo",
        "files": [
            {
                "path": "design.v",
                "content": "module m; wire w; endmodule\n",
                "source_path": str(src),
            }
        ],
    }
    result = _save_endpoint(app)("demo.spj", payload)
    assert result["ok"] is True
    vs = isolated_data / "verilog_sources" / "demo" / "design.v"
    assert vs.read_text(encoding="utf-8") == "module m; wire w; endmodule\n"
    assert src.read_text(encoding="utf-8") == original
    paths = [item["path"] if isinstance(item, dict) else item for item in result["updated_sources"]]
    assert str(vs.resolve()) in paths


def test_load_spj_fills_source_path_from_examples(isolated_data, monkeypatch) -> None:
    import hdl_sim.web.app as app_module

    examples = isolated_data / "examples"
    (examples / "kadai").mkdir(parents=True)
    unique = examples / "kadai" / "unique_dut.v"
    unique.write_text("module unique_dut; endmodule\n", encoding="utf-8")
    (examples / "dup.v").write_text("module d1; endmodule\n", encoding="utf-8")
    (examples / "kadai" / "dup.v").write_text("module d2; endmodule\n", encoding="utf-8")
    monkeypatch.setattr(app_module, "EXAMPLES_DIR", examples)

    spj_path = spj_store.spj_dir() / "legacy.spj"
    spj_path.write_text(
        json.dumps(
            {
                "format": "hdl-sim-project",
                "version": 1,
                "name": "legacy",
                "files": [
                    {"path": "unique_dut.v", "content": "module unique_dut; endmodule\n"},
                    {"path": "dup.v", "content": "module d1; endmodule\n"},
                ],
            }
        ),
        encoding="utf-8",
    )

    app = create_app()
    load = next(
        r
        for r in app.routes
        if getattr(r, "path", None) == "/api/spj/{filename}"
        and "GET" in getattr(r, "methods", set())
    ).endpoint
    data = load("legacy.spj")
    by_path = {f["path"]: f for f in data["files"]}
    assert by_path["unique_dut.v"]["source_path"] == "examples://kadai/unique_dut.v"
    assert "source_path" not in by_path["dup.v"]


def test_load_legacy_path_reference_spj(isolated_data) -> None:
    src_dir = isolated_data / "spj" / "rtl"
    src_dir.mkdir()
    dut = src_dir / "ref_dut.v"
    dut.write_text("module ref_dut; endmodule\n", encoding="utf-8")

    spj_path = spj_store.spj_dir() / "refstyle.spj"
    spj_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "project": {"name": "refstyle"},
                "simulation": {"top_module": "ref_dut"},
                "files": ["rtl/ref_dut.v"],
            }
        ),
        encoding="utf-8",
    )

    app = create_app()
    load = next(
        r
        for r in app.routes
        if getattr(r, "path", None) == "/api/spj/{filename}"
        and "GET" in getattr(r, "methods", set())
    ).endpoint
    data = load("refstyle.spj")
    assert data["format"] == "hdl-sim-project"
    assert data["top"] == "ref_dut"
    assert data["files"][0]["path"] == "ref_dut.v"
    assert Path(data["files"][0]["source_path"]) == dut.resolve()
    assert "module ref_dut" in data["files"][0]["content"]


def test_legacy_spj_rejects_path_escape(isolated_data) -> None:
    secret = isolated_data / "secret.v"
    secret.write_text("module secret; endmodule\n", encoding="utf-8")
    spj_path = spj_store.spj_dir() / "escape.spj"
    spj_path.write_text(
        json.dumps({"files": ["../secret.v"], "project": {"name": "escape"}}),
        encoding="utf-8",
    )
    app = create_app()
    load = next(
        r
        for r in app.routes
        if getattr(r, "path", None) == "/api/spj/{filename}"
        and "GET" in getattr(r, "methods", set())
    ).endpoint
    with pytest.raises(Exception):
        load("escape.spj")


def test_spj_roundtrip_load_edit_save_updates_verilog_sources(isolated_data) -> None:
    src_dir = isolated_data / "spj" / "rtl"
    src_dir.mkdir()
    dut = src_dir / "rt_dut.v"
    dut.write_text("module rt_dut; endmodule\n", encoding="utf-8")
    original = dut.read_text(encoding="utf-8")

    spj_path = spj_store.spj_dir() / "rt.spj"
    spj_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "project": {"name": "rt"},
                "simulation": {"top_module": "rt_dut"},
                "files": ["rtl/rt_dut.v"],
            }
        ),
        encoding="utf-8",
    )

    app = create_app()
    load = next(
        r
        for r in app.routes
        if getattr(r, "path", None) == "/api/spj/{filename}"
        and "GET" in getattr(r, "methods", set())
    ).endpoint
    data = load("rt.spj")
    edited = dict(data)
    edited.pop("filename", None)
    edited["files"][0]["content"] = "module rt_dut; wire w; endmodule\n"
    result = _save_endpoint(app)("rt.spj", edited)
    vs = isolated_data / "verilog_sources" / "rt" / "rt_dut.v"
    assert vs.read_text(encoding="utf-8") == "module rt_dut; wire w; endmodule\n"
    assert dut.read_text(encoding="utf-8") == original
    assert result["ok"] is True


def test_save_v_file_and_reject_traversal(isolated_data) -> None:
    from fastapi import HTTPException

    app = create_app()
    save_v = next(
        r for r in app.routes if getattr(r, "path", None) == "/api/save_v_file"
    ).endpoint
    ok = save_v({"project_name": "demo", "file_name": "a.v", "source": "module a; endmodule\n"})
    assert ok["ok"] is True
    written = isolated_data / "verilog_sources" / "demo" / "a.v"
    assert written.is_file()
    with pytest.raises(HTTPException):
        save_v({"project_name": "demo", "file_name": "../escape.v", "source": "x"})


def test_spj_save_rejects_dotdot_path(isolated_data) -> None:
    with pytest.raises(ValueError):
        spj_store.save_spj_file(
            "demo.spj",
            {"files": [{"path": "../escape.v", "content": "module x; endmodule\n"}]},
        )
