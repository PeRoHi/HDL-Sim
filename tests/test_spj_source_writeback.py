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


def test_load_spj_fills_source_path_from_examples(isolated_spj, monkeypatch) -> None:
    """source_path の無い .spj を開くと examples の一意なファイルから補完される。"""

    import json

    import hdl_sim.web.app as app_module

    examples = isolated_spj / "examples"
    (examples / "kadai").mkdir(parents=True)
    unique = examples / "kadai" / "unique_dut.v"
    unique.write_text("module unique_dut; endmodule\n", encoding="utf-8")
    # 同名ファイルが複数ある場合は補完しない
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


def test_load_legacy_path_reference_spj(isolated_spj) -> None:
    """files がパス文字列の旧 .spj は内容を読み込み source_path を付与して返す。"""

    import json

    src_dir = isolated_spj / "rtl"
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
                "files": ["../rtl/ref_dut.v"],
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
    assert data["files"][0]["source_path"] == str(dut.resolve())
    assert "module ref_dut" in data["files"][0]["content"]


def test_spj_roundtrip_load_edit_save_updates_source(isolated_spj) -> None:
    """開く → 編集 → 保存 で参照元 .v が更新されるエンドツーエンド。"""

    import json

    src_dir = isolated_spj / "rtl"
    src_dir.mkdir()
    dut = src_dir / "rt_dut.v"
    dut.write_text("module rt_dut; endmodule\n", encoding="utf-8")

    spj_path = spj_store.spj_dir() / "rt.spj"
    spj_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "project": {"name": "rt"},
                "simulation": {"top_module": "rt_dut"},
                "files": ["../rtl/rt_dut.v"],
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

    # UI 相当: 内容を編集してそのまま保存
    edited = dict(data)
    edited.pop("filename", None)
    edited["files"][0]["content"] = "module rt_dut; wire w; endmodule\n"
    result = _save_endpoint(app)("rt.spj", edited)
    assert result["updated_sources"] == [str(dut.resolve())]
    assert dut.read_text(encoding="utf-8") == "module rt_dut; wire w; endmodule\n"


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
