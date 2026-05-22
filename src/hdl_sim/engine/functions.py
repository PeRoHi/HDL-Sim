"""Verilog function execution (no delays)."""

from __future__ import annotations

from collections.abc import Callable

from hdl_sim.core.events import EventQueue, SimTime
from hdl_sim.engine.evaluator import ExpressionEvaluator
from hdl_sim.engine.executor import ProcessContext, ProcessState
from hdl_sim.engine.nba import NBARegion
from hdl_sim.engine.nets import SimNet
from hdl_sim.parser.ast import Block, DeclKind, FunctionDef, Stmt


def call_function(
    func: FunctionDef,
    arg_values: tuple[int, ...],
    *,
    functions: dict[str, FunctionDef],
    queue: EventQueue,
    nba: NBARegion,
    on_net_update: Callable[[SimNet, SimTime], None],
) -> int:
    """Execute a function and return its integer result."""

    if len(arg_values) != len(func.inputs):
        msg = f"function {func.name} expects {len(func.inputs)} arguments, got {len(arg_values)}"
        raise RuntimeError(msg)

    return_width = 8

    locals: dict[str, SimNet] = {}
    return_net = SimNet(name=func.name, width=return_width, kind=DeclKind.REG)
    locals[func.name] = return_net

    for port, value in zip(func.inputs, arg_values):
        input_net = SimNet(name=port.name, width=return_width, kind=DeclKind.REG, value=value)
        locals[port.name] = input_net

    for decl in func.declarations:
        width = 32 if decl.kind is DeclKind.INTEGER else (1 if decl.range is None else 32)
        if decl.name not in locals:
            locals[decl.name] = SimNet.from_declaration(decl.name, decl.kind, None)

    evaluator = ExpressionEvaluator(locals, functions=functions)

    def run_stmt(stmt: Stmt) -> None:
        context = ProcessContext(
            queue=queue,
            nets=locals,
            evaluator=evaluator,
            nba=nba,
            schedule=lambda at, cb: queue.schedule_at(at, cb),
            on_net_update=on_net_update,
        )
        ProcessState(context).run(stmt)

    for item in func.body_statements:
        if isinstance(item, Block):
            for stmt in item.statements:
                run_stmt(stmt)
        else:
            run_stmt(item)

    return return_net.value
