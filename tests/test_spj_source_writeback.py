"""Saving .spj writes edited content back to referenced source .v files."""

from __future__ import annotations

from pathlib import Path

import pytest

from hdl_sim.web import spj_store
from hdl_sim.web.app import create_app


@pytest.fixture()
def isolated_spj(tmp_path, monkeypatch):
    spj_root = tmp_path / "spj"
    spj_root.mkdir()
    monkeypatch.setattr(spj_store, "spj_dir", lambda: spj_root)
    return tmp_path


def _save_endpoint(app):
    return next(
        r
        for r in app.routes
        if getattr(r, "path", None) == "/api/spj/{filename}"
        and "PUT" in getattr(r, "methods", set())
    ).endpoint


def test_spj_save_writes_back_to_source_path(isolated_spj) -> None:
    src = isolated_spj / "design.v"
    src.write_text("module m; endmodule\n", encoding="utf-8")

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
    assert result["updated_sources"] == [str(src)]
    assert src.read_text(encoding="utf-8") == "module m; wire w; endmodule\n"


def test_spj_save_skips_unchanged_and_missing_sources(isolated_spj) -> None:
    src = isolated_spj / "same.v"
    content = "module s; endmodule\n"
    src.write_text(content, encoding="utf-8")

    app = create_app()
    payload = {
        "format": "hdl-sim-project",
        "version": 1,
        "name": "demo2",
        "files": [
            {"path": "same.v", "content": content, "source_path": str(src)},
            {
                "path": "gone.v",
                "content": "module g; endmodule\n",
                "source_path": str(isolated_spj / "missing" / "gone.v"),
            },
            {"path": "inline.v", "content": "module i; endmodule\n"},
        ],
    }
    result = _save_endpoint(app)("demo2.spj", payload)
    assert result["ok"] is True
    assert result["updated_sources"] == []
    assert len(result["source_errors"]) == 1
    assert "gone.v" in result["source_errors"][0]
