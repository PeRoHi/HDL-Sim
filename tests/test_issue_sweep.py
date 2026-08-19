"""Regression tests for 2026-08 issue sweep (arith, ifdef, function width, memory)."""

from __future__ import annotations

import pytest

from hdl_sim.engine.simulator import Simulator
from hdl_sim.parser.preprocess import preprocess


def test_signed_division_truncates_toward_zero() -> None:
    sim = Simulator.from_source(
        """
        module t;
          reg signed [7:0] a, b, c;
          initial begin a = -7; b = 3; c = a / b; end
        endmodule
        """
    )
    sim.run(until=1, max_events=20)
    assert sim._nets["c"].value == (-2) & 0xFF


def test_modulo_operator() -> None:
    sim = Simulator.from_source(
        """
        module t;
          integer a;
          initial a = 10 % 3;
        endmodule
        """
    )
    sim.run(until=1, max_events=20)
    assert sim._nets["a"].value == 1


def test_ifdef_keeps_defined_branch() -> None:
    source = preprocess(
        """
`define SYNTHESIS 1
module m;
`ifdef SYNTHESIS
  assign a = 1;
`endif
  assign b = 1;
endmodule
"""
    ).source
    assert "assign a = 1" in source
    assert "assign b = 1" in source


def test_ifdef_drops_undefined_branch() -> None:
    source = preprocess(
        """
module m;
`ifdef SYNTHESIS
  assign a = 1;
`else
  assign b = 1;
`endif
endmodule
"""
    ).source
    assert "assign a = 1" not in source
    assert "assign b = 1" in source


def test_function_return_width_uses_range() -> None:
    sim = Simulator.from_source(
        """
        module t;
          function [15:0] wide;
            input [15:0] x;
            begin wide = x + 16'h0100; end
          endfunction
          integer r;
          initial r = wide(16'h00FF);
        endmodule
        """
    )
    sim.run(until=1, max_events=30)
    assert sim._nets["r"].value == 0x1FF


def test_memory_oob_and_negative_index_are_errors() -> None:
    with pytest.raises(ValueError, match="out of range"):
        sim = Simulator.from_source(
            """
            module t;
              reg [7:0] mem [0:1];
              integer x;
              initial begin mem[0]=8'h11; mem[1]=8'h22; x = mem[5]; end
            endmodule
            """
        )
        sim.run(until=1, max_events=20)

    with pytest.raises(ValueError, match="out of range"):
        sim = Simulator.from_source(
            """
            module t;
              reg [7:0] mem [0:1];
              integer x;
              initial begin mem[0]=8'h11; mem[1]=8'h22; x = mem[-1]; end
            endmodule
            """
        )
        sim.run(until=1, max_events=20)


def test_bit_nba_preserves_x() -> None:
    sim = Simulator.from_source(
        """
        module t;
          reg [1:0] a;
          initial begin
            a = 2'b00;
            a[1] <= 1'bx;
          end
        endmodule
        """
    )
    sim.run(until=1, max_events=20)
    assert sim._nets["a"].x_mask & 0b10


def test_task_decl_init_assign_runs() -> None:
    sim = Simulator.from_source(
        """
        module t;
          integer y;
          task sety;
            reg [7:0] n = 8'd7;
            begin y = n; end
          endtask
          initial sety();
        endmodule
        """
    )
    sim.run(until=1, max_events=30)
    assert sim._nets["y"].value == 7
