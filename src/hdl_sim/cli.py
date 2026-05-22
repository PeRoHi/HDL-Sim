"""Command-line interface for HDL-Sim."""

from __future__ import annotations

import argparse
from pathlib import Path

from hdl_sim.engine.simulator import SimulationResult, simulate_design
from hdl_sim.engine.trace import SimulationTracer
from hdl_sim.parser.loader import load_design_with_meta


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
    parser.add_argument("--top", default=None, help="Top module name (default: auto-detect)")
    parser.add_argument("-D", "--define", action="append", default=[], metavar="NAME=VAL", help="Preprocessor macro")
    parser.add_argument("-I", "--include-dir", action="append", type=Path, default=[], help="Include search path")
    parser.add_argument("--timescale", default=None, help="VCD timescale (overrides `timescale`)")
    parser.add_argument("--verbose", action="store_true", help="Log simulation activity to stderr")
    parser.add_argument("--trace", type=Path, default=None, help="Write text trace log to this file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    vcd_path = args.vcd or args.verilog[0].with_suffix(".vcd")

    tracer = SimulationTracer(verbose=args.verbose, trace_path=str(args.trace) if args.trace else None)
    tracer.open()
    try:
        defines: dict[str, str] = {}
        for item in args.define:
            if "=" in item:
                name, value = item.split("=", 1)
            else:
                name, value = item, "1"
            defines[name] = value
        loaded = load_design_with_meta(
            args.verilog,
            defines=defines or None,
            include_paths=args.include_dir or None,
        )
        timescale = args.timescale or loaded.timescale or "1ns"
        result = simulate_design(
            loaded.design,
            top=args.top,
            timescale=timescale,
            vcd_path=vcd_path,
            until=args.until,
            max_events=args.max_events,
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
