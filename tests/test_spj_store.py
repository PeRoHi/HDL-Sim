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
