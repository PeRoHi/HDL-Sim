"""Simulation smoke test for bundled sai example."""

from pathlib import Path

from hdl_sim.engine.elaborator import elaborate
from hdl_sim.engine.simulator import Simulator
from hdl_sim.parser.loader import load_design_with_meta


def test_sai_testbench_simulates_with_module_functions() -> None:
    root = Path(__file__).resolve().parents[1] / "examples" / "examples"
    paths = [root / "sai.v", root / "saitest.v"]
    loaded = load_design_with_meta(paths)
    elaborated = elaborate(loaded.design, top="sai_test")
    assert any(func.name == "dec" for func in elaborated.functions)
    result = Simulator(elaborated).run(until=15_000, max_events=5000)
    assert result.events_processed > 10
    assert result.stop_time >= 1000
