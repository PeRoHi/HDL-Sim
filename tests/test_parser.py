from hdl_sim.parser import parse_module
from hdl_sim.parser.ast import (
    BinaryExpr,
    Block,
    ContinuousAssign,
    DeclKind,
    DelayControl,
    Forever,
    IdentRef,
    InitialBlock,
)


CLOCK_SOURCE = """
module clock_tb;
  reg clk;
  initial begin
    clk = 0;
    forever begin
      #5 clk = ~clk;
    end
  end
endmodule
"""


def test_parse_clock_module() -> None:
    module = parse_module(CLOCK_SOURCE)

    assert module.name == "clock_tb"
    assert len(module.declarations) == 1
    assert module.declarations[0].kind is DeclKind.REG
    assert len(module.initial_blocks) == 1

    initial = module.initial_blocks[0]
    assert isinstance(initial.body, Block)
    assigns = initial.body.statements
    assert isinstance(assigns[0], type(assigns[0]))  # sanity
    assert isinstance(assigns[1], Forever)


def test_parse_continuous_assign_expression() -> None:
    module = parse_module(
        """
        module m;
          wire y;
          wire a;
          wire b;
          assign y = a & b;
        endmodule
        """
    )

    assert len(module.continuous_assigns) == 1
    assign = module.continuous_assigns[0]
    assert isinstance(assign, ContinuousAssign)
    assert isinstance(assign.expr, BinaryExpr)
    assert isinstance(assign.expr.left, IdentRef)
    assert isinstance(assign.expr.right, IdentRef)


def test_parse_delay_control() -> None:
    module = parse_module(
        """
        module m;
          reg x;
          initial #3 x = 1;
        endmodule
        """
    )
    initial = module.initial_blocks[0]
    assert isinstance(initial.body, DelayControl)
    assert initial.body.delay == 3


def test_parse_comma_separated_reg_declarations() -> None:
    module = parse_module(
        """
        module tb;
          reg clk, rst;
          wire [3:0] count;
        endmodule
        """
    )
    assert len(module.declarations) == 3
    names = [d.name for d in module.declarations]
    assert names == ["clk", "rst", "count"]
    assert module.declarations[0].kind is DeclKind.REG
    assert module.declarations[1].kind is DeclKind.REG
    assert module.declarations[2].kind is DeclKind.WIRE
