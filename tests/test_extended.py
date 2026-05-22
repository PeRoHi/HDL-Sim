from pathlib import Path

from hdl_sim.engine.simulator import Simulator, simulate_files
from hdl_sim.parser import load_design_with_meta, parse_module
from hdl_sim.parser.ast import BinaryExpr, ConcatExpr, ForStmt

ROOT = Path(__file__).resolve().parents[1]


def test_param_range_width_minus_one() -> None:
    sim = Simulator.from_source(
        """
        module m;
          parameter WIDTH = 8;
          reg [WIDTH-1:0] bus;
          initial bus = 8'hFF;
        endmodule
        """
    )
    sim.run(until=0, max_events=10)
    assert sim._nets["bus"].width == 8


def test_for_loop_sum() -> None:
    sim = Simulator.from_source(
        """
        module m;
          integer i;
          reg [3:0] sum;
          initial begin
            sum = 0;
            for (i = 0; i < 4; i = i + 1)
              sum = sum + i;
          end
        endmodule
        """
    )
    sim.run(until=0, max_events=100)
    assert sim._nets["sum"].value == 6


def test_concat_expr() -> None:
    sim = Simulator.from_source(
        """
        module m;
          reg [3:0] a;
          reg [3:0] b;
          reg [7:0] y;
          initial begin
            a = 4'hA;
            b = 4'h5;
            y = {a, b};
          end
        endmodule
        """
    )
    sim.run(until=0, max_events=20)
    assert sim._nets["y"].value == 0xA5


def test_define_and_include() -> None:
    header = ROOT / "examples" / "lib" / "pulse.v"
    header.write_text(
        """
        `define PULSE_HIGH 1
        initial #1 d = `PULSE_HIGH;
        """
    )
    top = ROOT / "examples" / "tb_include.v"
    top.write_text(
        """
        module tb_include;
          reg d;
          `include "lib/pulse.v"
        endmodule
        """
    )
    loaded = load_design_with_meta([top], include_paths=[ROOT / "examples"])
    sim = Simulator(loaded.design)
    sim.run(until=2, max_events=50)
    assert sim._nets["d"].value == 1
    header.unlink()
    top.unlink()


def test_cli_top_module() -> None:
    result = simulate_files(
        [ROOT / "examples" / "lib" / "and2.v", ROOT / "examples" / "tb_multi.v"],
        top="tb_multi",
        until=2,
        max_events=100,
    )
    assert result.top_module == "tb_multi"
