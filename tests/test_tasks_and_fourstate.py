from pathlib import Path

from hdl_sim.engine.simulator import Simulator, simulate_source

ROOT = Path(__file__).resolve().parents[1]


def test_task_output_port() -> None:
    sim = Simulator.from_source(
        """
        module m;
          reg [7:0] a;
          reg [7:0] b;
          task swap;
            input [7:0] x;
            output [7:0] y;
            begin y = x + 1; end
          endtask
          initial begin
            a = 3;
            swap(a, b);
          end
        endmodule
        """
    )
    sim.run(until=0, max_events=30)
    assert sim._nets["b"].value == 4


def test_casex_dont_care() -> None:
    sim = Simulator.from_source(
        """
        module m;
          reg [3:0] sel;
          reg [7:0] out;
          initial begin
            sel = 4'b1010;
            casex (sel)
              4'b10x0: out = 8'd11;
              default: out = 8'd0;
            endcase
          end
        endmodule
        """
    )
    sim.run(until=0, max_events=20)
    assert sim._nets["out"].value == 11


def test_dumpvars_level_filter(tmp_path: Path) -> None:
    vcd_path = tmp_path / "partial.vcd"
    simulate_source(
        """
        module tb;
          reg top_sig;
          reg sub_sig;
          initial begin
            top_sig = 0;
            sub_sig = 1;
            $dumpfile("WAVE");
            $dumpvars(1, tb);
          end
        endmodule
        """.replace("WAVE", str(vcd_path)),
        until=0,
        max_events=20,
    )
    text = vcd_path.read_text(encoding="utf-8")
    assert "top_sig" in text or "tb.top_sig" in text
    # Web viewer exports the full netlist even when $dumpvars limits scope.
    assert "sub_sig" in text or "tb.sub_sig" in text


def test_monitor_system_task(capsys) -> None:
    sim = Simulator.from_source(
        """
        module m;
          reg x;
          initial begin
            x = 0;
            $monitor("x=%0d", x);
            x = 1;
          end
        endmodule
        """
    )
    sim.run(until=0, max_events=20)
    captured = capsys.readouterr().out
    assert "x=" in captured
