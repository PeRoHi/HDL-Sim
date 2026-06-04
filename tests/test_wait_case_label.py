"""`wait` as case label / `wait_cnt` identifiers vs wait(condition)."""

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


def test_wait_cnt_identifier_not_split() -> None:
    mod = parse_module(
        """
module m;
  reg [7:0] wait_cnt;
  initial begin
    wait_cnt = 0;
    wait(wait_cnt);
  end
endmodule
"""
    )
    decl = mod.declarations[0]
    assert decl.name == "wait_cnt"
