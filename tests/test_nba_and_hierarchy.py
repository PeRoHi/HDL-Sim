from pathlib import Path

from hdl_sim.engine.simulator import Simulator, simulate_source
from hdl_sim.parser import parse_design

ROOT = Path(__file__).resolve().parents[1]
COUNTER_SOURCE = (ROOT / "examples" / "counter.v").read_text(encoding="utf-8")
HIERARCHY_SOURCE = (ROOT / "examples" / "hierarchy.v").read_text(encoding="utf-8")


def test_counter_increments_on_posedge() -> None:
    simulator = Simulator.from_source(COUNTER_SOURCE)
    simulator.run(until=25, max_events=500)

    count = simulator._nets["count"]
    # posedge at t=5, 15, 25
    assert count.value == 3


def test_hierarchy_and_gate() -> None:
    design = parse_design(HIERARCHY_SOURCE)
    assert design.top.name == "tb"
    assert len(design.modules) == 2

    simulator = Simulator(design)
    simulator.run(until=5, max_events=200)

    assert simulator._nets["ry"].value == 0


def test_hierarchy_vcd_contains_instance_signals(tmp_path: Path) -> None:
    vcd_path = tmp_path / "hierarchy.vcd"
    result = simulate_source(HIERARCHY_SOURCE, vcd_path=vcd_path, until=3, max_events=100)

    content = vcd_path.read_text(encoding="utf-8")
    assert result.vcd_path == vcd_path
    assert "u_and.y" in content or "ry" in content
