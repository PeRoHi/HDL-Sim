"""Bundled example .spj projects in ./spj/."""

import json
from pathlib import Path

import pytest

from hdl_sim.web import spj_store


@pytest.fixture()
def spj_root(tmp_path, monkeypatch):
    repo_spj = Path(__file__).resolve().parents[1] / "spj"
    monkeypatch.setattr(spj_store, "spj_dir", lambda: repo_spj)
    return repo_spj


def test_repo_spj_includes_saikoro(spj_root: Path) -> None:
    path = spj_root / "saikoro.spj"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format"] == "hdl-sim-project"
    assert data["top"] == "sai_test"
    names = {f["path"] for f in data["files"]}
    assert names == {"sai.v", "saitest.v"}


def test_no_spj_left_under_examples() -> None:
    examples = Path(__file__).resolve().parents[1] / "examples"
    assert list(examples.rglob("*.spj")) == []


def test_spj_store_loads_saikoro(spj_root: Path) -> None:
    loaded = spj_store.load_spj_file("saikoro.spj")
    assert loaded["data"]["top"] == "sai_test"
