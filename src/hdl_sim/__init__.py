"""HDL-Sim: lightweight event-driven Verilog simulator."""

from hdl_sim.engine import SimulationResult, Simulator
from hdl_sim.parser import parse_design, parse_module

__version__ = "1.1.0"

__all__ = [
    "SimulationResult",
    "Simulator",
    "__version__",
    "parse_design",
    "parse_module",
]
