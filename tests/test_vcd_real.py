"""VCD real signal dump and JSON timeline parsing."""

from pathlib import Path

import pytest

from hdl_sim.engine.simulator import Simulator
from hdl_sim.web.vcd_json import parse_vcd_timeline, timeline_to_json


def test_real_vcd_dump_and_parse() -> None:
    source = """
    module tb;
      real x;
      real y;
      initial begin
        $dumpfile("real_test.vcd");
        $dumpvars(0, tb);
        x = 0.0;
        y = -1.5;
        #10 x = 3.14159;
        #20 y = 2.5;
        #30 $finish;
      end
    endmodule
    """
    vcd_path = Path("real_test.vcd")
    try:
        sim = Simulator.from_source(source, vcd_path=vcd_path)
        sim.run(max_events=200)
        text = vcd_path.read_text(encoding="utf-8")
        assert "$var real" in text
        assert "r3.14159" in text or "r3.1416" in text

        tl = parse_vcd_timeline(text)
        kinds = {s.name: s.kind for s in tl.signals}
        assert kinds.get("x") == "real"
        assert kinds.get("y") == "real"

        data = timeline_to_json(tl)
        by_name = {s["name"]: s for s in data["signals"]}
        x_changes = {t: v for t, v in by_name["x"]["changes"]}
        y_changes = {t: v for t, v in by_name["y"]["changes"]}
        assert float(x_changes[10]) == pytest.approx(3.14159, rel=1e-4)
        assert float(y_changes[30]) == pytest.approx(2.5)
    finally:
        if vcd_path.is_file():
            vcd_path.unlink()
