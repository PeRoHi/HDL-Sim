"""Command-line interface for HDL-Sim."""

from __future__ import annotations

import argparse
from pathlib import Path

from hdl_sim.engine.simulator import simulate_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lightweight event-driven Verilog simulator")
    parser.add_argument("verilog", type=Path, help="Path to a Verilog source file")
    parser.add_argument(
        "-o",
        "--vcd",
        type=Path,
        default=None,
        help="Output VCD path (default: <verilog_stem>.vcd)",
    )
    parser.add_argument("--until", type=int, default=None, help="Stop simulation at this time")
    parser.add_argument("--max-events", type=int, default=None, help="Maximum scheduled events to process")
    parser.add_argument("--timescale", default="1ns", help="VCD timescale annotation")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    vcd_path = args.vcd or args.verilog.with_suffix(".vcd")
    result = simulate_file(
        args.verilog,
        vcd_path=vcd_path,
        until=args.until,
        max_events=args.max_events,
        timescale=args.timescale,
    )
    print(
        f"module={result.top_module} time={result.stop_time} "
        f"events={result.events_processed} vcd={result.vcd_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
