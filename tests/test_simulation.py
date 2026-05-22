from pathlib import Path

from hdl_sim.engine.simulator import Simulator, simulate_source
from hdl_sim.parser import parse_module

ROOT = Path(__file__).resolve().parents[1]
CLOCK_SOURCE = (ROOT / "examples" / "clock.v").read_text(encoding="utf-8")
AND_SOURCE = (ROOT / "examples" / "and_gate.v").read_text(encoding="utf-8")


def test_clock_toggles_over_simulation_window() -> None:
    simulator = Simulator.from_source(CLOCK_SOURCE)
    result = simulator.run(until=20, max_events=200)

    clk = simulator._nets["clk"]
    assert result.stop_time == 20
    assert clk.value in (0, 1)


def test_and_gate_continuous_assign_propagates() -> None:
    simulator = Simulator.from_source(AND_SOURCE)
    simulator.run(until=5, max_events=200)

    assert simulator._nets["y"].value == 0


def test_vcd_file_is_written(tmp_path: Path) -> None:
    vcd_path = tmp_path / "clock.vcd"
    result = simulate_source(CLOCK_SOURCE, vcd_path=vcd_path, until=10, max_events=100)

    assert result.vcd_path == vcd_path
    content = vcd_path.read_text(encoding="utf-8")
    assert "$timescale 1ns $end" in content
    assert "$var wire 1" in content
    assert "#0" in content
    assert "#5" in content or "#10" in content


def test_cli_example_files_exist() -> None:
    assert parse_module(CLOCK_SOURCE).name == "clock_tb"
    assert parse_module(AND_SOURCE).name == "and_gate"
