"""Simulation tracing helpers for CLI debugging."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import TextIO

from hdl_sim.core.events import SimTime
from hdl_sim.engine.nets import SimNet


@dataclass
class SimulationTracer:
    """Optional verbose logging and text trace output."""

    verbose: bool = False
    trace_path: str | None = None
    _trace_file: TextIO | None = field(default=None, repr=False)
    _event_count: int = field(default=0, repr=False)

    def open(self) -> None:
        if self.trace_path is not None:
            self._trace_file = open(self.trace_path, "w", encoding="utf-8")  # noqa: SIM115

    def close(self) -> None:
        if self._trace_file is not None:
            self._trace_file.close()
            self._trace_file = None

    def log(self, message: str) -> None:
        if self.verbose:
            print(message, file=sys.stderr)
        if self._trace_file is not None:
            self._trace_file.write(message + "\n")

    def on_net_change(self, net: SimNet, previous: int, current: int, time: SimTime) -> None:
        self.log(f"#{time} {net.name} {previous} -> {current}")

    def on_time_step(self, time: SimTime) -> None:
        self.log(f"--- time {time} ---")

    def on_nba_flush(self, time: SimTime) -> None:
        self.log(f"#{time} [NBA]")

    def on_event(self, time: SimTime, detail: str) -> None:
        self._event_count += 1
        self.log(f"#{time} event {detail}")
