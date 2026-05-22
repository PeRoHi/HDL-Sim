from pathlib import Path

from hdl_sim.engine.simulator import Simulator, simulate_source
from hdl_sim.vcd.writer import VCDWriter

ROOT = Path(__file__).resolve().parents[1]


def test_vcd_hierarchical_scope() -> None:
    nets = {}
    from hdl_sim.engine.nets import SimNet
    from hdl_sim.parser.ast import DeclKind

    nets["tb.dut.clk"] = SimNet(name="tb.dut.clk", width=1, kind=DeclKind.REG)
    nets["tb.dut.count"] = SimNet(name="tb.dut.count", width=4, kind=DeclKind.REG)
    writer = VCDWriter("tb", nets)
    rendered = writer.render()
    assert "$scope module tb $end" in rendered
    assert "$scope module dut $end" in rendered
    assert "$var wire 1" in rendered


def test_function_call() -> None:
    sim = Simulator.from_source(
        """
        module m;
          function [7:0] add1;
            input [7:0] a;
            begin add1 = a + 1; end
          endfunction
          reg [7:0] y;
          initial y = add1(8'h3);
        endmodule
        """
    )
    sim.run(until=0, max_events=20)
    assert sim._nets["y"].value == 4


def test_dumpfile_dumpvars(tmp_path: Path) -> None:
    vcd_path = tmp_path / "wave.vcd"
    simulate_source(
        """
        module m;
          reg clk;
          initial begin
            clk = 0;
            $dumpfile("WAVE");
            $dumpvars(0);
            clk = 1;
          end
        endmodule
        """.replace("WAVE", str(vcd_path)),
        until=0,
        max_events=20,
    )
    text = vcd_path.read_text(encoding="utf-8")
    assert "$dumpvars" in text
    assert "#0" in text


def test_comb_always_via_delta() -> None:
    sim = Simulator.from_source(
        """
        module m;
          reg a;
          reg b;
          reg y;
          initial begin
            a = 1;
            b = 0;
          end
          always @(*) y = a & b;
        endmodule
        """
    )
    sim.run(until=0, max_events=50)
    assert sim._nets["y"].value == 0
    sim._nets["b"].update(1, time=0)
    sim._delta.flush(0)
    assert sim._nets["y"].value == 1
