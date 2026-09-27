"""Tests for .spj project storage."""

from __future__ import annotations

import json

import pytest

from hdl_sim.web import spj_store


def test_spj_dir_created() -> None:
    path = spj_store.spj_dir()
    assert path.is_dir()


def test_spj_save_and_load_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(spj_store, "spj_dir", lambda: tmp_path)
    monkeypatch.setattr(spj_store, "user_data_dir", lambda: tmp_path)
    payload = {
        "format": "hdl-sim-project",
        "version": 1,
        "name": "demo",
        "top": "tb",
        "files": [{"path": "tb.v", "content": "module tb; endmodule"}],
    }
    saved = spj_store.save_spj_file("demo.spj", payload)
    assert saved["filename"] == "demo.spj"
    loaded = spj_store.load_spj_file("demo.spj")
    assert loaded["filename"] == "demo.spj"
    assert loaded["data"]["top"] == "tb"


def test_spj_list_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(spj_store, "spj_dir", lambda: tmp_path)
    (tmp_path / "a.spj").write_text("{}", encoding="utf-8")
    names = [row["name"] for row in spj_store.list_spj_files()]
    assert names == ["a.spj"]


def test_spj_invalid_name() -> None:
    with pytest.raises(ValueError):
        spj_store.save_spj_file("bad name.spj", {"format": "hdl-sim-project", "files": []})


def test_spj_load_refuses_empty_and_corrupt(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(spj_store, "spj_dir", lambda: tmp_path)
    monkeypatch.setattr(spj_store, "user_data_dir", lambda: tmp_path)
    empty = tmp_path / "empty.spj"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="loadFailed"):
        spj_store.load_spj_file("empty.spj")
    ws = tmp_path / "ws.spj"
    ws.write_text(" \n\t ", encoding="utf-8")
    with pytest.raises(ValueError, match="loadFailed"):
        spj_store.load_spj_file("ws.spj")
    bad = tmp_path / "bad.spj"
    bad.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="loadFailed"):
        spj_store.load_spj_file("bad.spj")


def test_spj_http_loadfailed_is_503(tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from hdl_sim.web.app import create_app

    monkeypatch.setattr(spj_store, "spj_dir", lambda: tmp_path)
    monkeypatch.setattr(spj_store, "user_data_dir", lambda: tmp_path)
    (tmp_path / "bad.spj").write_text("{not-json", encoding="utf-8")
    client = TestClient(create_app(), base_url="http://127.0.0.1:8765")
    loaded = client.get("/api/spj/bad.spj", headers={"Host": "127.0.0.1:8765"})
    assert loaded.status_code == 503
    assert loaded.json()["error"] == "loadFailed"


def test_spj_save_refuses_overwrite_of_corrupt(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(spj_store, "spj_dir", lambda: tmp_path)
    monkeypatch.setattr(spj_store, "user_data_dir", lambda: tmp_path)
    broken = tmp_path / "keep.spj"
    broken.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="loadFailed"):
        spj_store.save_spj_file(
            "keep.spj",
            {
                "format": "hdl-sim-project",
                "files": [{"path": "a.v", "content": "module a; endmodule\n"}],
            },
        )
    assert broken.read_text(encoding="utf-8") == "{not-json"


def test_spj_refuses_empty_overwrite_of_existing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(spj_store, "spj_dir", lambda: tmp_path)
    monkeypatch.setattr(spj_store, "user_data_dir", lambda: tmp_path)
    existing = tmp_path / "keep.spj"
    existing.write_text('{"format": "hdl-sim-project", "files": [{"path": "a.v"}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        spj_store.save_spj_file("keep.spj", {"format": "hdl-sim-project", "files": []})
    assert "a.v" in existing.read_text(encoding="utf-8")
