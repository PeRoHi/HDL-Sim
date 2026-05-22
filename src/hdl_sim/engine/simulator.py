"""Top-level event-driven simulator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from hdl_sim.core.events import EventQueue, SimTime
from hdl_sim.engine.elaborator import ElaboratedDesign, ScopedContinuousAssign, ScopedProcess, elaborate
from hdl_sim.engine.evaluator import ExpressionEvaluator
from hdl_sim.engine.executor import ProcessContext, ProcessState
from hdl_sim.engine.expr_deps import identifiers_in_expr, identifiers_in_stmt
from hdl_sim.engine.nba import NBARegion
from hdl_sim.engine.nets import SimNet
from hdl_sim.parser.ast import AlwaysBlock, Design, EdgeKind, Module
from hdl_sim.parser.loader import load_design
from hdl_sim.parser.parser import parse_design, parse_module
from hdl_sim.engine.trace import SimulationTracer
from hdl_sim.vcd.writer import VCDWriter


@dataclass(frozen=True, slots=True)
class SimulationResult:
    top_module: str
    stop_time: SimTime
    events_processed: int
    vcd_path: Path | None


class Simulator:
    """Compile and run a Verilog design."""

    def __init__(
        self,
        design: Design | Module | ElaboratedDesign,
        *,
        timescale: str = "1ns",
        vcd_path: Path | None = None,
        tracer: SimulationTracer | None = None,
    ) -> None:
        if isinstance(design, Module):
            design = Design(modules=(design,))
        if isinstance(design, Design):
            elaborated = elaborate(design)
        else:
            elaborated = design

        self._elaborated = elaborated
        self._queue = EventQueue()
        self._nets = elaborated.nets
        self._nba = NBARegion(self._nets, on_update=self._record_net)
        def nba_flush() -> None:
            if self._tracer is not None:
                self._tracer.on_nba_flush(self._queue.now)
            self._nba.flush(self._queue.now)

        self._queue.set_nba_flush(nba_flush)
        self._vcd = (
            VCDWriter(elaborated.top_module, self._nets, timescale=timescale) if vcd_path else None
        )
        self._vcd_path = vcd_path
        self._tracer = tracer

    @classmethod
    def from_source(
        cls,
        source: str,
        *,
        timescale: str = "1ns",
        vcd_path: Path | None = None,
    ) -> Simulator:
        return cls(parse_design(source), timescale=timescale, vcd_path=vcd_path)

    @classmethod
    def from_file(
        cls,
        path: Path,
        *,
        timescale: str = "1ns",
        vcd_path: Path | None = None,
    ) -> Simulator:
        return cls.from_source(path.read_text(encoding="utf-8"), timescale=timescale, vcd_path=vcd_path)

    def _register_continuous_updates(self) -> None:
        for assign in self._elaborated.continuous_assigns:
            evaluator = ExpressionEvaluator(assign.locals)
            dependencies = identifiers_in_expr(assign.expr)

            def recompute(time: SimTime, scoped: ScopedContinuousAssign = assign) -> None:
                value = evaluator.eval(scoped.expr)
                net = self._nets[scoped.target]
                if net.update(value, time=time):
                    self._record_net(net, time)

            for name in dependencies:
                if name in assign.locals:
                    assign.locals[name].subscribe(
                        lambda _net, _prev, _curr, time, cb=recompute: cb(time)
                    )
            recompute(0)

    def _on_display(self, message: str, time: SimTime) -> None:
        if self._tracer is not None:
            self._tracer.log(f"#{time} $display {message}")

    def _record_net(self, net: SimNet, time: SimTime) -> None:
        if net.previous is not None and self._tracer is not None:
            self._tracer.on_net_change(net, net.previous, net.value, time)
        if self._vcd is not None:
            self._vcd.change(net, time)

    def _spawn_process(self, process: ScopedProcess, *, time: SimTime = 0) -> None:
        evaluator = ExpressionEvaluator(process.locals)

        def run_process() -> None:
            def on_finish() -> None:
                self._queue.stop()

            context = ProcessContext(
                queue=self._queue,
                nets=process.locals,
                evaluator=evaluator,
                nba=self._nba,
                schedule=lambda at, cb: self._queue.schedule_at(at, cb),
                on_net_update=self._record_net,
                on_display=self._on_display,
                on_finish=on_finish,
            )
            ProcessState(context).run(process.body)

        self._queue.schedule_at(time, run_process)

    def _start_initial_blocks(self) -> None:
        for process in self._elaborated.initial_blocks:
            self._spawn_process(process, time=0)

    def _start_always_blocks(self) -> None:
        for block, local_nets in self._elaborated.always_blocks:
            if block.sensitivity is None:
                self._start_combinational_always(block, local_nets)
                continue
            self._start_sensitive_always(block, local_nets)

    def _start_combinational_always(self, block: AlwaysBlock, local_nets: dict[str, SimNet]) -> None:
        dependencies = identifiers_in_stmt(block.body)

        def run_comb(time: SimTime = 0) -> None:
            if self._queue.stopped:
                return
            evaluator = ExpressionEvaluator(local_nets)

            def on_finish() -> None:
                self._queue.stop()

            context = ProcessContext(
                queue=self._queue,
                nets=local_nets,
                evaluator=evaluator,
                nba=self._nba,
                schedule=lambda at, cb: self._queue.schedule_at(at, cb),
                on_net_update=self._record_net,
                on_display=self._on_display,
                on_finish=on_finish,
            )
            ProcessState(context).run(block.body)

        def subscribe(name: str) -> None:
            if name not in local_nets:
                return
            local_nets[name].subscribe(
                lambda _net, _prev, _curr, time, cb=run_comb: cb(time)
            )

        for name in dependencies:
            subscribe(name)
        run_comb(0)

    def _start_sensitive_always(self, block: AlwaysBlock, local_nets: dict[str, SimNet]) -> None:
        evaluator = ExpressionEvaluator(local_nets)

        def trigger() -> None:
            self._spawn_process(ScopedProcess(body=block.body, locals=local_nets), time=self._queue.now)

        for edge_kind, name in block.sensitivity:
            if name not in local_nets:
                continue
            net = local_nets[name]

            def on_change(
                _net: SimNet,
                prev: int,
                curr: int,
                time: SimTime,
                *,
                edge: EdgeKind | None = edge_kind,
                fire: Callable[[], None] = trigger,
            ) -> None:
                if edge is EdgeKind.POSEDGE:
                    if (prev & 1) == 0 and (curr & 1) == 1:
                        fire()
                elif edge is EdgeKind.NEGEDGE:
                    if (prev & 1) == 1 and (curr & 1) == 0:
                        fire()
                else:
                    fire()

            net.subscribe(on_change)

    def run(self, *, until: SimTime | None = None, max_events: int | None = None) -> SimulationResult:
        self._register_continuous_updates()

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
            top_module=self._elaborated.top_module,
            stop_time=stop_time,
            events_processed=processed,
            vcd_path=self._vcd_path,
        )





def simulate_design(
    design: Design,
    *,
    vcd_path: Path | None = None,
    until: SimTime | None = None,
    max_events: int | None = None,
    timescale: str = "1ns",
    tracer: SimulationTracer | None = None,
) -> SimulationResult:
    simulator = Simulator(design, timescale=timescale, vcd_path=vcd_path, tracer=tracer)
    return simulator.run(until=until, max_events=max_events)


def simulate_files(
    paths: list[Path],
    *,
    vcd_path: Path | None = None,
    until: SimTime | None = None,
    max_events: int | None = None,
    timescale: str = "1ns",
    tracer: SimulationTracer | None = None,
) -> SimulationResult:
    return simulate_design(
        load_design(paths),
        vcd_path=vcd_path,
        until=until,
        max_events=max_events,
        timescale=timescale,
        tracer=tracer,
    )

def simulate_file(
    verilog_path: Path,
    *,
    vcd_path: Path | None = None,
    until: SimTime | None = None,
    max_events: int | None = None,
    timescale: str = "1ns",
) -> SimulationResult:
    simulator = Simulator.from_file(verilog_path, timescale=timescale, vcd_path=vcd_path, tracer=None)
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
