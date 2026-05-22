"""Verilog parsing for the supported subset."""

from hdl_sim.parser.ast import Design, Module
from hdl_sim.parser.loader import load_design
from hdl_sim.parser.parser import parse_design, parse_module

__all__ = ["Design", "Module", "load_design", "parse_design", "parse_module"]
