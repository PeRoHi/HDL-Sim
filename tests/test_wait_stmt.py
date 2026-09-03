"""Procedural wait(condition) statement."""

from hdl_sim.engine.elaborator import elaborate
from hdl_sim.engine.simulator import Simulator
from hdl_sim.parser.parser import parse_design


def test_wait_until_condition_true() -> None:
    source = """
module tb;
  reg ready;
  initial begin
    ready = 0;
    #5 ready = 1;
  end
  initial begin
    wait(ready);
    $finish;
  end
endmodule
"""
    design = parse_design(source)
    elaborated = elaborate(design, top="tb")
    result = Simulator(elaborated).run(until=100, max_events=500)
    assert result.events_processed > 0
