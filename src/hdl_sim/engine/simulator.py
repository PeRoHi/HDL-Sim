"""Top-level event-driven simulator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from hdl_sim.core.events import EventQueue, SimTime
from hdl_sim.engine.delta import DeltaRegion
from hdl_sim.engine.elaborator import ElaboratedDesign, ScopedContinuousAssign, ScopedProcess, elaborate
from hdl_sim.engine.evaluator import ExpressionEvaluator
from hdl_sim.engine.executor import ProcessContext, ProcessState, render_display_args
from hdl_sim.engine.nba import NBARegion
from hdl_sim.engine.nets import SimNet
from hdl_sim.engine.trace import SimulationTracer
from hdl_sim.parser.ast import AlwaysBlock, Design, DisplayArg, EdgeKind, Forever, Module
from hdl_sim.parser.loader import load_design, load_design_with_meta, read_verilog_text
from hdl_sim.parser.parser import parse_design, parse_module
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
        top: str | None = None,
    ) -> None:
        if isinstance(design, Module):
            design = Design(modules=(design,))
        if isinstance(design, Design):
            elaborated = elaborate(design, top=top)
        else:
            elaborated = design

        self._elaborated = elaborated
        self._functions = {func.name: func for func in elaborated.functions}
        self._tasks = {task.name: task for task in elaborated.tasks}
        self._queue = EventQueue()
        self._nets = elaborated.nets
        self._delta = DeltaRegion()
        self._in_delta = False
        self._nba = NBARegion(self._nets, on_update=self._record_net)
        self._timescale = timescale

        def regions_flush() -> None:
            time = self._queue.now
            if self._tracer is not None:
                self._tracer.on_nba_flush(time)
            self._nba.flush(time)
            self._in_delta = True
            try:
                self._delta.flush(time)
            finally:
                self._in_delta = False

        self._queue.set_nba_flush(regions_flush)
        self._vcd_path = vcd_path
        self._vcd = (
            VCDWriter(elaborated.top_module, self._nets, timescale=timescale) if vcd_path else None
        )
        self._tracer = tracer
        self._monitors: list[tuple[tuple[DisplayArg, ...], dict[str, SimNet]]] = []

    @classmethod
    def from_source(
        cls,
        source: str,
        *,
        timescale: str = "1ns",
        vcd_path: Path | None = None,
        top: str | None = None,
    ) -> Simulator:
        return cls(parse_design(source), timescale=timescale, vcd_path=vcd_path, top=top)

    @classmethod
    def from_file(
        cls,
        path: Path,
        *,
        timescale: str = "1ns",
        vcd_path: Path | None = None,
        top: str | None = None,
    ) -> Simulator:
        return cls.from_source(
            read_verilog_text(path),
            timescale=timescale,
            vcd_path=vcd_path,
            top=top,
        )

    def _ensure_vcd(self) -> None:
        if self._vcd is None:
            self._vcd = VCDWriter(
                self._elaborated.top_module,
                self._nets,
                timescale=self._timescale,
            )

    def _register_continuous_updates(self) -> None:
        for assign in self._elaborated.continuous_assigns:
            evaluator = ExpressionEvaluator(assign.locals, functions=self._functions, queue=self._queue, nba=self._nba, on_net_update=self._record_net)

            def recompute(time: SimTime, scoped: ScopedContinuousAssign = assign) -> bool:
                from hdl_sim.engine.net_state import apply_four_state

                state = evaluator.eval_logic(scoped.expr)
                net = self._nets[scoped.target]
                return apply_four_state(net, state, time=time, on_update=self._record_net)

            self._delta.add_continuous(recompute)
            recompute(0)

    def _register_monitor(self, args: tuple[DisplayArg, ...], locals: dict[str, SimNet]) -> None:
        merged = {**self._nets, **locals}
        self._monitors.append((args, merged))

    def _check_monitors(self) -> None:
        for args, locals in self._monitors:
            evaluator = ExpressionEvaluator(locals, queue=self._queue)
            message = render_display_args(args, evaluator)
            print(message, flush=True)
            if self._tracer is not None:
                self._tracer.log(f"#{self._queue.now} $monitor {message}")

    def _on_display(self, message: str, time: SimTime) -> None:
        if self._tracer is not None:
            self._tracer.log(f"#{time} $display {message}")

    def _on_dumpfile(self, path: str) -> None:
        self._vcd_path = Path(path)
        self._ensure_vcd()
        if self._tracer is not None:
            self._tracer.log(f"$dumpfile {path}")

    def _on_dumpvars(self, args: tuple[DisplayArg, ...]) -> None:
        self._ensure_vcd()
        time = self._queue.now
        active = self._resolve_dump_nets(args)
        self._vcd.set_active_nets(active)
        self._vcd.dump_initial(time)
        for name in active:
            self._vcd.change(self._nets[name], time)
        if self._tracer is not None:
            self._tracer.log(f"#{time} $dumpvars ({len(active)} nets)")

    def _resolve_dump_nets(self, args: tuple[DisplayArg, ...]) -> frozenset[str]:
        from hdl_sim.parser.ast import BitSelect, IdentRef, PartSelect

        if not args:
            return frozenset(self._nets)

        evaluator = ExpressionEvaluator(self._nets)
        explicit: list[str] = []
        for arg in args:
            if arg.expr is None:
                continue
            if isinstance(arg.expr, IdentRef):
                name = arg.expr.name
                if name in self._nets:
                    explicit.append(name)
                else:
                    explicit.extend(n for n in self._nets if n.endswith(f".{name}") or n == name)
            elif isinstance(arg.expr, (BitSelect, PartSelect)):
                signal = arg.expr.signal
                if signal in self._nets:
                    explicit.append(signal)
        if explicit:
            return frozenset(dict.fromkeys(explicit))

        level = 0
        scope: str | None = None
        if args[0].expr is not None:
            level = evaluator.eval(args[0].expr)
        if len(args) > 1:
            second = args[1]
            if second.text is not None:
                scope = second.text.strip('"')
            elif isinstance(second.expr, IdentRef):
                scope = second.expr.name
        selected: list[str] = []
        for name in self._nets:
            if scope is not None and not (name == scope or name.startswith(f"{scope}.")):
                continue
            if level > 0:
                if scope and name.startswith(f"{scope}."):
                    relative = name[len(scope) + 1 :]
                elif scope and name == scope:
                    relative = ""
                else:
                    relative = name
                parts = relative.split(".") if relative else []
                subscopes = max(0, len(parts) - 1)
                if subscopes >= level:
                    continue
            selected.append(name)
        return frozenset(selected if selected else list(self._nets))

    def _record_net(self, net: SimNet, time: SimTime) -> None:
        if net.previous is not None and self._tracer is not None:
            self._tracer.on_net_change(net, net.previous, net.value, time)
        self._check_monitors()
        if self._vcd is not None:
            self._vcd.change(net, time)

    def _spawn_process(self, process: ScopedProcess, *, time: SimTime = 0) -> None:
        evaluator = ExpressionEvaluator(
            process.locals,
            functions=self._functions,
            tasks=self._tasks,
            queue=self._queue,
            nba=self._nba,
            on_net_update=self._record_net,
            caller_nets=process.locals,
        )

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
                on_monitor=lambda args, loc=process.locals: self._register_monitor(args, loc),
                on_dumpfile=self._on_dumpfile,
                on_dumpvars=self._on_dumpvars,
            )
            ProcessState(context).run(process.body)

        self._queue.schedule_at(time, run_process)

    def _start_initial_blocks(self) -> None:
        for process in self._elaborated.initial_blocks:
            self._spawn_process(process, time=0)

    def _start_always_blocks(self) -> None:
        for block, local_nets in self._elaborated.always_blocks:
            if isinstance(block.body, Forever) and block.sensitivity == ():
                self._spawn_process(ScopedProcess(body=block.body, locals=local_nets), time=self._queue.now)
                continue
            if not block.sensitivity:
                self._register_combinational_always(block, local_nets)
                continue
            self._start_sensitive_always(block, local_nets)

    def _register_combinational_always(self, block: AlwaysBlock, local_nets: dict[str, SimNet]) -> None:
        def run_comb() -> bool:
            if self._queue.stopped:
                return False
            before = {name: net.value for name, net in local_nets.items()}
            evaluator = ExpressionEvaluator(
                local_nets,
                functions=self._functions,
                tasks=self._tasks,
                queue=self._queue,
                nba=self._nba,
                on_net_update=self._record_net,
                caller_nets=local_nets,
            )

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
                on_monitor=lambda args, loc=local_nets: self._register_monitor(args, loc),
                on_dumpfile=self._on_dumpfile,
                on_dumpvars=self._on_dumpvars,
            )
            ProcessState(context).run(block.body)
            return any(before[name] != local_nets[name].value for name in before)

        self._delta.add_comb(run_comb)
        run_comb()

    def _start_sensitive_always(self, block: AlwaysBlock, local_nets: dict[str, SimNet]) -> None:
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
        self._start_initial_blocks()
        self._start_always_blocks()

        if self._vcd is not None:
            self._vcd.dump_initial(0)
            for net in self._nets.values():
                self._vcd.change(net, 0)

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
    top: str | None = None,
    vcd_path: Path | None = None,
    until: SimTime | None = None,
    max_events: int | None = None,
    timescale: str = "1ns",
    tracer: SimulationTracer | None = None,
) -> SimulationResult:
    simulator = Simulator(design, timescale=timescale, vcd_path=vcd_path, tracer=tracer, top=top)
    return simulator.run(until=until, max_events=max_events)


def simulate_files(
    paths: list[Path],
    *,
    top: str | None = None,
    defines: dict[str, str] | None = None,
    include_paths: list[Path] | None = None,
    vcd_path: Path | None = None,
    until: SimTime | None = None,
    max_events: int | None = None,
    timescale: str = "1ns",
    tracer: SimulationTracer | None = None,
) -> SimulationResult:
    loaded = load_design_with_meta(paths, defines=defines, include_paths=include_paths)
    return simulate_design(
        loaded.design,
        top=top,
        timescale=timescale if timescale != "1ns" else (loaded.timescale or timescale),
        vcd_path=vcd_path,
        until=until,
        max_events=max_events,
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
