"""Command-line interface for HDL-Sim."""

from __future__ import annotations

import argparse
from pathlib import Path

from hdl_sim.engine.simulator import SimulationResult, simulate_design
from hdl_sim.engine.trace import SimulationTracer
from hdl_sim.parser.loader import load_design


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lightweight event-driven Verilog simulator")
    parser.add_argument(
        "verilog",
        nargs="+",
        type=Path,
        help="Verilog source file(s); top module is auto-detected",
    )
    parser.add_argument(
        "-o",
        "--vcd",
        type=Path,
        default=None,
        help="Output VCD path (default: <first_verilog_stem>.vcd)",
    )
    parser.add_argument("--until", type=int, default=None, help="Stop simulation at this time")
    parser.add_argument("--max-events", type=int, default=None, help="Maximum scheduled events to process")
    parser.add_argument("--timescale", default="1ns", help="VCD timescale annotation")
    parser.add_argument("--verbose", action="store_true", help="Log simulation activity to stderr")
    parser.add_argument("--trace", type=Path, default=None, help="Write text trace log to this file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    vcd_path = args.vcd or args.verilog[0].with_suffix(".vcd")

    tracer = SimulationTracer(verbose=args.verbose, trace_path=str(args.trace) if args.trace else None)
    tracer.open()
    try:
        design = load_design(args.verilog)
        result = simulate_design(
            design,
            vcd_path=vcd_path,
            until=args.until,
            max_events=args.max_events,
            timescale=args.timescale,
            tracer=tracer,
        )
    finally:
        tracer.close()

    print(
        f"module={result.top_module} time={result.stop_time} "
        f"events={result.events_processed} vcd={result.vcd_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
