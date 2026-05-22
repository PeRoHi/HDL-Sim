"""Top-level event-driven simulator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hdl_sim.core.events import EventQueue, SimTime
from hdl_sim.engine.evaluator import ExpressionEvaluator
from hdl_sim.engine.executor import ProcessContext, ProcessState
from hdl_sim.engine.nets import SimNet
from hdl_sim.parser.ast import (
    AlwaysBlock,
    ContinuousAssign,
    DeclKind,
    InitialBlock,
    Module,
)
from hdl_sim.parser.parser import parse_module
from hdl_sim.engine.expr_deps import identifiers_in_expr
from hdl_sim.vcd.writer import VCDWriter


@dataclass(frozen=True, slots=True)
class SimulationResult:
    top_module: str
    stop_time: SimTime
    events_processed: int
    vcd_path: Path | None


class Simulator:
    """Compile and run a single-module Verilog design."""

    def __init__(
        self,
        module: Module,
        *,
        timescale: str = "1ns",
        vcd_path: Path | None = None,
    ) -> None:
        self._module = module
        self._queue = EventQueue()
        self._nets = self._build_nets(module)
        self._evaluator = ExpressionEvaluator(self._nets)
        self._vcd = VCDWriter(module.name, self._nets, timescale=timescale) if vcd_path else None
        self._vcd_path = vcd_path
        self._continuous: list[ContinuousAssign] = list(module.continuous_assigns)
        self._register_continuous_updates()

    @classmethod
    def from_source(
        cls,
        source: str,
        *,
        timescale: str = "1ns",
        vcd_path: Path | None = None,
    ) -> Simulator:
        return cls(parse_module(source), timescale=timescale, vcd_path=vcd_path)

    @classmethod
    def from_file(
        cls,
        path: Path,
        *,
        timescale: str = "1ns",
        vcd_path: Path | None = None,
    ) -> Simulator:
        return cls.from_source(path.read_text(encoding="utf-8"), timescale=timescale, vcd_path=vcd_path)

    def _build_nets(self, module: Module) -> dict[str, SimNet]:
        nets: dict[str, SimNet] = {}
        for decl in module.declarations:
            if decl.name in nets:
                msg = f"duplicate declaration: {decl.name}"
                raise ValueError(msg)
            nets[decl.name] = SimNet.from_declaration(decl.name, decl.kind, decl.range)
        for assign in module.continuous_assigns:
            if assign.target not in nets:
                nets[assign.target] = SimNet(name=assign.target, width=1, kind=DeclKind.WIRE)
        return nets

    def _register_continuous_updates(self) -> None:
        for assign in self._continuous:
            dependencies = identifiers_in_expr(assign.expr)

            def recompute(time: SimTime, assignment: ContinuousAssign = assign) -> None:
                value = self._evaluator.eval(assignment.expr)
                net = self._nets[assignment.target]
                if net.update(value, time=time):
                    self._record_net(net, time)

            for name in dependencies:
                if name in self._nets:
                    self._nets[name].subscribe(
                        lambda _net, _prev, _curr, time, cb=recompute: cb(time)
                    )
            recompute(0)

    def _record_net(self, net: SimNet, time: SimTime) -> None:
        if self._vcd is not None:
            self._vcd.change(net, time)

    def _spawn_process(self, body, *, time: SimTime = 0) -> None:
        def run_process() -> None:
            context = ProcessContext(
                queue=self._queue,
                nets=self._nets,
                evaluator=self._evaluator,
                schedule=lambda at, cb: self._queue.schedule_at(at, cb),
                on_net_update=self._record_net,
            )
            ProcessState(context).run(body)

        self._queue.schedule_at(time, run_process)

    def _start_initial_blocks(self) -> None:
        for block in self._module.initial_blocks:
            self._spawn_process(block.body, time=0)

    def _start_always_blocks(self) -> None:
        for block in self._module.always_blocks:
            if block.sensitivity is None:
                self._spawn_process(block.body, time=0)
                continue
            self._start_sensitive_always(block)

    def _start_sensitive_always(self, block: AlwaysBlock) -> None:
        watched = [name for _edge, name in block.sensitivity]

        def trigger() -> None:
            context = ProcessContext(
                queue=self._queue,
                nets=self._nets,
                evaluator=self._evaluator,
                schedule=lambda at, cb: self._queue.schedule_at(at, cb),
                on_net_update=self._record_net,
            )
            ProcessState(context).run(block.body)

        def on_change(_net: SimNet, _prev: int, _curr: int, time: SimTime) -> None:
            self._queue.schedule_at(time, trigger)

        for name in watched:
            if name in self._nets:
                self._nets[name].subscribe(on_change)

    def run(self, *, until: SimTime | None = None, max_events: int | None = None) -> SimulationResult:
        if self._vcd is not None:
            self._vcd.dump_initial(0)
            for net in self._nets.values():
                self._vcd.change(net, 0)

        self._start_initial_blocks()
        self._start_always_blocks()

        processed = self._queue.run(until=until, max_events=max_events)
        stop_time = self._queue.now

        if self._vcd_path is not None and self._vcd is not None:
            self._vcd.write(self._vcd_path)

        return SimulationResult(
            top_module=self._module.name,
            stop_time=stop_time,
            events_processed=processed,
            vcd_path=self._vcd_path,
        )


def simulate_file(
    verilog_path: Path,
    *,
    vcd_path: Path | None = None,
    until: SimTime | None = None,
    max_events: int | None = None,
    timescale: str = "1ns",
) -> SimulationResult:
    simulator = Simulator.from_file(verilog_path, timescale=timescale, vcd_path=vcd_path)
    return simulator.run(until=until, max_events=max_events)


def simulate_source(
    source: str,
    *,
    vcd_path: Path | None = None,
    until: SimTime | None = None,
    max_events: int | None = None,
    timescale: str = "1ns",
) -> SimulationResult:
    simulator = Simulator.from_source(source, timescale=timescale, vcd_path=vcd_path)
    return simulator.run(until=until, max_events=max_events)
