"""Verilog-2001 ANSI-style port declarations (input wire / output reg)."""

from hdl_sim.parser.parser import parse_module


def test_ansi_port_list_input_wire() -> None:
    mod = parse_module(
        """
module top (
  input wire clk,
  input wire reset_n,
  output reg [7:0] q
);
endmodule
"""
    )
    assert [p.name for p in mod.ports] == ["clk", "reset_n", "q"]
    clk, reset_n, q = mod.ports
    from hdl_sim.parser.ast import DeclKind, PortDirection

    assert clk.direction is PortDirection.INPUT
    assert clk.net_kind is DeclKind.WIRE
    assert reset_n.net_kind is DeclKind.WIRE
    assert q.direction is PortDirection.OUTPUT
    assert q.net_kind is DeclKind.REG
    assert q.range is not None


def test_ansi_port_body_decl() -> None:
    mod = parse_module(
        """
module m;
  input wire a;
  output reg b;
endmodule
"""
    )
    a, b = mod.ports
    from hdl_sim.parser.ast import DeclKind

    assert a.net_kind is DeclKind.WIRE
    assert b.net_kind is DeclKind.REG
