"""Regression tests for imported legacy Silos-style Verilog examples."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

from hdl_sim.engine.simulator import simulate_files
from hdl_sim.parser.loader import load_design_with_meta, read_verilog_text

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "examples" / "examples"
JEX = EX / "新しいフォルダー"


def test_cp932_examples_load_with_encoding_fallback() -> None:
    loaded = load_design_with_meta([EX / "DFF_TST.v"])
    assert loaded.design.modules[0].name == "DFF_tp"
    text = read_verilog_text(EX / "counter_reset_tp.v")
    assert "counter_reset_tp" in text


def test_legacy_example_designs_parse() -> None:
    files = [
        EX / "4add.v",
        EX / "4addtest.v",
        EX / "DFF.v",
        EX / "DFF_TST.v",
        EX / "couter_reset.v",
        EX / "counter_reset_tp.v",
        EX / "sai.v",
        EX / "saitest.v",
        EX / "tff.v",
        EX / "tff_TST.v",
        EX / "watch.v",
        EX / "watch_test.v",
        JEX / "code_coverage.v",
        JEX / "testbench.v",
        JEX / "testbench2.v",
    ]
    for path in files:
        loaded = load_design_with_meta([path])
        assert loaded.design.modules, path


def _run_quiet(paths: list[Path], *, top: str, until: int):
    with contextlib.redirect_stdout(io.StringIO()):
        return simulate_files(paths, top=top, until=until, max_events=5000)


def test_legacy_example_pairs_simulate() -> None:
    cases = [
        ([EX / "4add.v", EX / "4addtest.v"], "mul_ts", 5000),
        ([EX / "DFF.v", EX / "DFF_TST.v"], "DFF_tp", 250),
        ([EX / "couter_reset.v", EX / "counter_reset_tp.v"], "counter_reset_tp", 40000),
        ([EX / "sai.v", EX / "saitest.v"], "sai_test", 15000),
        ([EX / "tff.v", EX / "tff_TST.v"], "TFF_tp", 250),
        ([EX / "watch.v", EX / "watch_test.v"], "DFF_tp", 800),
        ([JEX / "code_coverage.v", JEX / "testbench.v"], "testbench", 150),
        ([JEX / "code_coverage.v", JEX / "testbench2.v"], "testbench", 150),
    ]
    for paths, top, until in cases:
        result = _run_quiet(paths, top=top, until=until)
        assert result.events_processed > 0
        assert result.top_module == top
