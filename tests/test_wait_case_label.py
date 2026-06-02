"""`wait` as case branch label must not clash with wait(condition) statement."""

from hdl_sim.parser.parser import parse_module


def test_case_label_wait_and_wait_statement() -> None:
    mod = parse_module(
        """
module m;
  reg [2:0] state;
  reg ready;
  initial case (state)
    3'd0: state = 1;
    wait: state = 2;
    default: state = 0;
  endcase
  initial wait(ready);
endmodule
"""
    )
    assert len(mod.initial_blocks) == 2
