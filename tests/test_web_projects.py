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
