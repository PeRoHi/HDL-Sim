"""Tests for persistent project storage API."""

from __future__ import annotations

from pathlib import Path

import pytest

from hdl_sim.web import projects as project_store
from hdl_sim.web.app import ProjectSaveRequest, SourceFile, create_app

ROOT = Path(__file__).resolve().parents[1]
COUNTER_DUT = ROOT / "examples" / "project" / "counter_dut.v"
TB_COUNTER = ROOT / "examples" / "project" / "tb_counter.v"


@pytest.fixture()
def isolated_projects(tmp_path, monkeypatch):
    monkeypatch.setattr(project_store, "projects_dir", lambda: tmp_path)
    return tmp_path


def test_create_load_save_project(isolated_projects) -> None:
    project_store.create_project("counter", top="tb_counter")
    saved = project_store.save_project(
        "counter",
        [
            {"path": "counter_dut.v", "content": COUNTER_DUT.read_text(encoding="utf-8")},
            {"path": "tb_counter.v", "content": TB_COUNTER.read_text(encoding="utf-8")},
        ],
        top="tb_counter",
    )
    assert len(saved["files"]) == 2
    loaded = project_store.load_project("counter")
    assert loaded["top"] == "tb_counter"
    paths = {f["path"] for f in loaded["files"]}
    assert paths == {"counter_dut.v", "tb_counter.v"}


def test_save_project_persists_wave_prefs(isolated_projects) -> None:
    project_store.create_project("wave_demo", top="tb")
    wave = {
        "selection": ["tb.clk", "tb.rst"],
        "order": ["tb.rst", "tb.clk"],
        "filePaths": ["tb.v"],
    }
    project_store.save_project(
        "wave_demo",
        [{"path": "tb.v", "content": "module tb; reg clk, rst; endmodule"}],
        top="tb",
        wave=wave,
    )
    loaded = project_store.load_project("wave_demo")
    assert loaded["wave"] == wave


def test_list_projects_corrupt_meta_is_load_failed(isolated_projects) -> None:
    project_store.create_project("broken", top="tb")
    meta = isolated_projects / "broken" / project_store.META_FILE
    meta.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="loadFailed"):
        project_store.list_projects()


def test_load_project_corrupt_meta_is_load_failed(isolated_projects) -> None:
    project_store.create_project("broken", top="tb")
    meta = isolated_projects / "broken" / project_store.META_FILE
    meta.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="loadFailed"):
        project_store.load_project("broken")


def test_save_project_refuses_overwrite_of_corrupt_meta(isolated_projects) -> None:
    project_store.create_project("broken", top="tb")
    meta = isolated_projects / "broken" / project_store.META_FILE
    original = "{not-json"
    meta.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError, match="loadFailed"):
        project_store.save_project(
            "broken",
            [{"path": "tb.v", "content": "module tb; endmodule\n"}],
            top="tb",
        )
    assert meta.read_text(encoding="utf-8") == original
    assert not (isolated_projects / "broken" / "tb.v").exists()


def test_list_projects_whitespace_meta_is_load_failed(isolated_projects) -> None:
    project_store.create_project("ws", top="tb")
    meta = isolated_projects / "ws" / project_store.META_FILE
    meta.write_text(" \n", encoding="utf-8")
    with pytest.raises(ValueError, match="loadFailed"):
        project_store.list_projects()


def test_project_http_loadfailed_is_503(isolated_projects) -> None:
    from fastapi.testclient import TestClient

    project_store.create_project("broken", top="tb")
    meta = isolated_projects / "broken" / project_store.META_FILE
    meta.write_text("{not-json", encoding="utf-8")
    client = TestClient(create_app(), base_url="http://127.0.0.1:8765")
    listed = client.get("/api/projects", headers={"Host": "127.0.0.1:8765"})
    assert listed.status_code == 503
    assert listed.json()["error"] == "loadFailed"
    loaded = client.get("/api/projects/broken", headers={"Host": "127.0.0.1:8765"})
    assert loaded.status_code == 503
    assert loaded.json()["error"] == "loadFailed"
    saved = client.put(
        "/api/projects/broken",
        json={"files": [{"path": "tb.v", "content": "module tb; endmodule\n"}], "top": "tb"},
        headers={"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765"},
    )
    assert saved.status_code == 503
    assert saved.json()["error"] == "loadFailed"
    assert meta.read_text(encoding="utf-8") == "{not-json"


def test_project_api_roundtrip(isolated_projects) -> None:
    app = create_app()
    create = next(r for r in app.routes if getattr(r, "path", None) == "/api/projects" and "POST" in getattr(r, "methods", set())).endpoint
    save = next(r for r in app.routes if getattr(r, "path", None) == "/api/projects/{project_name}" and "PUT" in getattr(r, "methods", set())).endpoint
    load = next(r for r in app.routes if getattr(r, "path", None) == "/api/projects/{project_name}" and "GET" in getattr(r, "methods", set())).endpoint

    from hdl_sim.web.app import ProjectCreateRequest

    create(ProjectCreateRequest(name="demo", top="tb"))
    req = ProjectSaveRequest(
        files=[SourceFile(path="tb.v", content="module tb; endmodule")],
        top="tb",
    )
    save("demo", req)
    data = load("demo")
    assert data["name"] == "demo"
    assert data["files"][0]["path"] == "tb.v"
