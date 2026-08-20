"""Concatenation lvalues: assign {a,b} and procedural {a,b} = / <=."""

from hdl_sim.engine.simulator import Simulator
from hdl_sim.parser.ast import ConcatLvalue, ContinuousAssign
from hdl_sim.parser.parser import parse_module


def test_parse_concat_continuous_assign() -> None:
    mod = parse_module(
        """
        module m;
          wire a;
          wire [1:0] b;
          assign {a, b} = 3'b101;
        endmodule
        """
    )
    assign = mod.continuous_assigns[0]
    assert isinstance(assign, ContinuousAssign)
    assert isinstance(assign.target, ConcatLvalue)
    assert [p.base for p in assign.target.parts] == ["a", "b"]


def test_assign_concat_splits_msb_first() -> None:
    sim = Simulator.from_source(
        """
        module t;
          wire a;
          wire [1:0] b;
          assign {a, b} = 3'b101;
        endmodule
        """
    )
    sim.run(until=0, max_events=20)
    assert sim._nets["a"].value == 1
    assert sim._nets["b"].value == 0b01


def test_procedural_concat_blocking_and_part_select() -> None:
    sim = Simulator.from_source(
        """
        module t;
          reg [3:0] x;
          reg y;
          initial {x[1:0], y} = 3'b110;
        endmodule
        """
    )
    sim.run(until=0, max_events=20)
    assert sim._nets["x"].value == 0b0011
    assert sim._nets["y"].value == 0


def test_procedural_concat_nba() -> None:
    sim = Simulator.from_source(
        """
        module t;
          reg a;
          reg [1:0] b;
          initial {a, b} <= 3'b111;
        endmodule
        """
    )
    sim.run(until=0, max_events=20)
    assert sim._nets["a"].value == 1
    assert sim._nets["b"].value == 0b11


def test_concat_keeps_rhs_lsbs_when_narrower_lhs() -> None:
    sim = Simulator.from_source(
        """
        module t;
          wire a;
          wire [1:0] b;
          assign {a, b} = 8'b0000_1101;
        endmodule
        """
    )
    sim.run(until=0, max_events=20)
    assert sim._nets["a"].value == 1
    assert sim._nets["b"].value == 0b01
