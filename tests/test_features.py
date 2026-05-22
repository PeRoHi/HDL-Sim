from pathlib import Path

from hdl_sim.engine.simulator import Simulator, simulate_files
from hdl_sim.parser import load_design

ROOT = Path(__file__).resolve().parents[1]


def test_load_multiple_files() -> None:
    design = load_design(
        [
            ROOT / "examples" / "lib" / "and2.v",
            ROOT / "examples" / "tb_multi.v",
        ]
    )
    assert design.top.name == "tb_multi"
    assert len(design.modules) == 2


def test_multifile_simulation() -> None:
    result = simulate_files(
        [
            ROOT / "examples" / "lib" / "and2.v",
            ROOT / "examples" / "tb_multi.v",
        ],
        until=3,
        max_events=200,
    )
    assert result.top_module == "tb_multi"
    assert result.stop_time >= 2


def test_parameterized_range() -> None:
    source = """
    module m;
      parameter WIDTH = 8;
      reg [7:0] bus;
      initial bus = 8'hFF;
    endmodule
    """
    sim = Simulator.from_source(source)
    sim.run(until=0, max_events=10)
    assert sim._nets["bus"].width == 8
    assert sim._nets["bus"].value == 0xFF


def test_display_in_initial(tmp_path: Path, capsys) -> None:
    source = """
    module m;
      reg [3:0] x;
      initial begin
        x = 3;
        $display("x=%d", x);
      end
    endmodule
    """
    Simulator.from_source(source).run(until=0, max_events=10)
    captured = capsys.readouterr()
    assert "x=3" in captured.out
