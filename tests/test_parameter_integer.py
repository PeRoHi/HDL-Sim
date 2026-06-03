"""Typed module parameters and $clog2 in localparam expressions."""

from pathlib import Path

from hdl_sim.engine.params import ParameterEvaluator
from hdl_sim.parser.loader import load_design_with_meta
from hdl_sim.parser.parser import parse_module


def test_parameter_integer_in_module_header() -> None:
    mod = parse_module(
        """
module m #(
  parameter integer WIDTH = 8
) (
  input wire clk
);
endmodule
"""
    )
    assert len(mod.parameters) == 1
    assert mod.parameters[0].name == "WIDTH"


def test_clog2_localparam_eval() -> None:
    mod = parse_module(
        """
module m;
  parameter integer TAP_NUM = 4;
  localparam integer SHIFT = $clog2(TAP_NUM);
endmodule
"""
    )
    values = ParameterEvaluator()
    resolved = values.resolve_module_params(mod.parameters)
    assert resolved["SHIFT"] == 2


def test_moving_avg_kadai_parses() -> None:
    root = Path(__file__).resolve().parents[1] / "examples" / "kadai"
    paths = [
        root / "delay_line.v",
        root / "moving_avg_core.v",
        root / "moving_avg_filter.v",
        root / "tb_moving_avg_filter.v",
    ]
    if not all(p.is_file() for p in paths):
        return
    loaded = load_design_with_meta(paths)
    assert "moving_avg_filter" in loaded.design.modules
    assert "tb_moving_avg_filter" in loaded.design.modules
