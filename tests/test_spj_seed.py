"""SPJ projects load correctly (includes, vend patch)."""

import json
from pathlib import Path

import pytest

from hdl_sim.engine.elaborator import elaborate
from hdl_sim.parser.loader import load_design_with_meta
from hdl_sim.web.app import SourceFile, load_design_from_files


def test_saikoro_spj_in_repo() -> None:
    path = Path(__file__).resolve().parents[1] / "spj" / "saikoro.spj"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["top"] == "sai_test"


def test_no_spj_left_under_examples() -> None:
    examples = Path(__file__).resolve().parents[1] / "examples"
    assert list(examples.rglob("*.spj")) == []


def test_vending_spj_resolves_include() -> None:
    root = Path(__file__).resolve().parents[1] / "spj" / "silos_vending.spj"
    data = json.loads(root.read_text(encoding="utf-8"))
    files = [SourceFile(**item) for item in data["files"]]
    assert any(f.path == "vending.v" and f.include_only for f in files)
    loaded, _base, tmp = load_design_from_files(files)
    tmp.cleanup()
    elaborated = elaborate(loaded.design, top=data["top"])
    assert elaborated.top_module == "stimulus"


def test_gate_spj_elaborates_vend() -> None:
    root = Path(__file__).resolve().parents[1] / "spj" / "silos_gate.spj"
    data = json.loads(root.read_text(encoding="utf-8"))
    files = [SourceFile(**item) for item in data["files"]]
    loaded, _base, tmp = load_design_from_files(files)
    tmp.cleanup()
    elaborated = elaborate(loaded.design, top=data["top"])
    assert "vend" in {m.name for m in loaded.design.modules}
