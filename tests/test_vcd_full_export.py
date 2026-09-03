"""VCD export includes all nets for the waveform viewer."""

from pathlib import Path

from hdl_sim.engine.simulator import simulate_source
from hdl_sim.web.vcd_json import parse_vcd_timeline


def test_dumpvars_does_not_strip_hierarchy_signals_from_vcd(tmp_path: Path) -> None:
    vcd_path = tmp_path / "wave.vcd"
    simulate_source(
        """
        module child(input clk, output reg y);
          always @(posedge clk) y <= ~y;
        endmodule
        module tb;
          reg clk;
          wire y;
          child u (.clk(clk), .y(y));
          initial begin
            clk = 0;
            forever #5 clk = ~clk;
            $dumpvars(1, u);
          end
        endmodule
        """,
        vcd_path=vcd_path,
        until=20,
        max_events=500,
    )
    names = {s.name for s in parse_vcd_timeline(vcd_path.read_text(encoding="utf-8")).signals}
    assert "clk" in names
    assert "y" in names or "u.y" in names
