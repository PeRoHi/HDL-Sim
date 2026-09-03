from hdl_sim.engine.four_state import FourStateValue, bitwise_and, to_int
from hdl_sim.engine.simulator import Simulator, simulate_source
from hdl_sim.parser.ast import IntLiteral


def test_generate_for_unroll() -> None:
    sim = Simulator.from_source(
        """
        module m;
          parameter WIDTH = 4;
          reg [WIDTH-1:0] out;
          generate
            for (i = 0; i < WIDTH; i = i + 1) begin
              wire bitw;
            end
          endgenerate
          initial out = 4'b0;
        endmodule
        """
    )
    assert any("g_" in name or "_bitw" in name or "g_0" in name for name in sim._nets)


def test_generate_if() -> None:
    sim = Simulator.from_source(
        """
        module m;
          parameter USE = 1;
          reg x;
          generate
            if (USE)
              initial x = 1;
            else
              initial x = 0;
          endgenerate
        endmodule
        """
    )
    sim.run(until=0, max_events=20)
    assert sim._nets["x"].value == 1


def test_fork_join() -> None:
    sim = Simulator.from_source(
        """
        module m;
          reg a;
          reg b;
          initial begin
            a = 0;
            b = 0;
            fork
              begin
                a = 1;
                b = 1;
              end
            join
          end
        endmodule
        """
    )
    sim.run(until=0, max_events=30)
    assert sim._nets["a"].value == 1
    assert sim._nets["b"].value == 1


def test_inout_port() -> None:
    sim = Simulator.from_source(
        """
        module child(inout bus);
          assign bus = 1'b1;
        endmodule
        module top;
          wire bus;
          child c1 (.bus(bus));
          
        endmodule
        """
    )
    sim.run(until=1, max_events=30)
    bus_names = [n for n in sim._nets if n.endswith("bus")]
    assert bus_names
    assert sim._nets[bus_names[0]].value == 1


def test_dumpvars_explicit_signals(tmp_path) -> None:
    vcd_path = tmp_path / "sig.vcd"
    simulate_source(
        """
        module m;
          reg clk;
          reg rst;
          initial begin
            clk = 0;
            rst = 1;
            $dumpfile("WAVE");
            $dumpvars(clk);
          end
        endmodule
        """.replace("WAVE", str(vcd_path)),
        until=0,
        max_events=20,
    )
    text = vcd_path.read_text(encoding="utf-8")
    assert "$var" in text
    assert "clk" in text
    # VCD definitions include the full elaborated netlist for the web waveform viewer.
    assert "rst" in text.split("$enddefinitions")[0]


def test_four_state_bitwise_and_unit() -> None:
    left = FourStateValue.from_literal(IntLiteral(value=0b0101, width=4, x_mask=0b0010, z_mask=0))
    right = FourStateValue.from_literal(IntLiteral(value=0b0110, width=4, x_mask=0b0001, z_mask=0))
    assert to_int(bitwise_and(left, right)) == 0b0100
