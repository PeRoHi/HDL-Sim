"""Verilog task execution (no delays)."""

from __future__ import annotations

from collections.abc import Callable

from hdl_sim.core.events import EventQueue, SimTime
from hdl_sim.engine.evaluator import ExpressionEvaluator
from hdl_sim.engine.executor import ProcessContext, ProcessState
from hdl_sim.engine.nba import NBARegion
from hdl_sim.engine.nets import SimNet
from hdl_sim.parser.ast import Block, DeclKind, IdentRef, Stmt, TaskDef, TaskPortKind


def call_task(
    task: TaskDef,
    arg_exprs: tuple,
    *,
    caller_nets: dict[str, SimNet],
    queue: EventQueue,
    nba: NBARegion,
    on_net_update: Callable[[SimNet, SimTime], None],
) -> None:
    """Execute a task; output ports alias nets in ``caller_nets``."""

    if len(arg_exprs) != len(task.ports):
        msg = f"task {task.name} expects {len(task.ports)} arguments, got {len(arg_exprs)}"
        raise RuntimeError(msg)

    locals: dict[str, SimNet] = {}
    evaluator = ExpressionEvaluator(caller_nets)

    for port, arg_expr in zip(task.ports, arg_exprs):
        if port.kind is TaskPortKind.INPUT:
            value = evaluator.eval(arg_expr)
            width = 32
            locals[port.name] = SimNet(name=port.name, width=width, kind=DeclKind.REG, value=value)
        elif port.kind is TaskPortKind.OUTPUT:
            if not isinstance(arg_expr, IdentRef):
                msg = f"task {task.name} output port {port.name} requires an identifier argument"
                raise RuntimeError(msg)
            try:
                locals[port.name] = caller_nets[arg_expr.name]
            except KeyError as exc:
                msg = f"unknown net for task output: {arg_expr.name}"
                raise RuntimeError(msg) from exc
        else:
            msg = f"unsupported task port kind: {port.kind}"
            raise RuntimeError(msg)

    for decl in task.declarations:
        if decl.name not in locals:
            locals[decl.name] = SimNet.from_declaration(decl.name, decl.kind, None)

    task_evaluator = ExpressionEvaluator(locals)

    def run_stmt(stmt: Stmt) -> None:
        context = ProcessContext(
            queue=queue,
            nets=locals,
            evaluator=task_evaluator,
            nba=nba,
            schedule=lambda at, cb: queue.schedule_at(at, cb),
            on_net_update=on_net_update,
        )
        ProcessState(context).run(stmt)

    for item in task.body_statements:
        if isinstance(item, Block):
            for stmt in item.statements:
                run_stmt(stmt)
        else:
            run_stmt(item)
