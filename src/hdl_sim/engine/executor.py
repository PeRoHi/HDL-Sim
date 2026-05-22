"""Procedural statement execution with delay and event controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from hdl_sim.core.events import EventQueue, SimTime
from hdl_sim.engine.evaluator import ExpressionEvaluator
from hdl_sim.engine.lvalue import write_lvalue
from hdl_sim.engine.nba import NBARegion
from hdl_sim.engine.nets import SimNet
from hdl_sim.parser.ast import (
    Block,
    CaseStmt,
    Display,
    DisplayArg,
    BlockingAssign,
    DelayControl,
    EventControl,
    Expr,
    Forever,
    IdentRef,
    IfStmt,
    Lvalue,
    NonBlockingAssign,
    Repeat,
    Stmt,
    SystemTask,
    UnaryExpr,
    WhileStmt,
    ForStmt,
    ForkJoin,
    TaskEnable,
)


ContinueCallback = Callable[[], None]
NetUpdateCallback = Callable[[SimNet, SimTime], None]
FinishCallback = Callable[[], None]


@dataclass(slots=True)
class ProcessContext:
    queue: EventQueue
    nets: dict[str, SimNet]
    evaluator: ExpressionEvaluator
    nba: NBARegion
    schedule: Callable[[SimTime, ContinueCallback], None]
    on_net_update: NetUpdateCallback
    on_display: Callable[[str, SimTime], None] | None = None
    on_finish: FinishCallback | None = None
    on_monitor: Callable[[tuple[DisplayArg, ...]], None] | None = None
    on_dumpfile: Callable[[str], None] | None = None
    on_dumpvars: Callable[[tuple[DisplayArg, ...]], None] | None = None


@dataclass(slots=True)
class ProcessState:
    context: ProcessContext

    def run(self, stmt: Stmt) -> None:
        StatementRunner(self).execute(stmt)

    def assign_lvalue(self, target: Lvalue, value: int, *, blocking: bool, time: SimTime) -> None:
        if blocking:
            write_lvalue(
                target,
                value,
                nets=self.context.nets,
                eval_fn=self.context.evaluator.eval,
                time=time,
                on_update=self.context.on_net_update,
            )
            return
        self.context.nba.schedule_lvalue(target, value, eval_fn=self.context.evaluator.eval)

    def _require_net(self, name: str) -> SimNet:
        try:
            return self.context.nets[name]
        except KeyError as exc:
            msg = f"unknown net: {name}"
            raise RuntimeError(msg) from exc


class StatementRunner:
    def __init__(self, state: ProcessState) -> None:
        self._state = state
        self._ctx = state.context

    def execute(self, stmt: Stmt, *, on_complete: ContinueCallback | None = None) -> None:
        if isinstance(stmt, Block):
            self._execute_statement_list(stmt.statements, on_complete=on_complete)
            return

        if isinstance(stmt, (BlockingAssign, NonBlockingAssign)):
            value = self._ctx.evaluator.eval(stmt.expr)
            self._state.assign_lvalue(
                stmt.target,
                value,
                blocking=isinstance(stmt, BlockingAssign),
                time=self._now(),
            )
            if on_complete is not None:
                on_complete()
            return

        if isinstance(stmt, DelayControl):
            target_time = self._now() + stmt.delay

            def resume() -> None:
                self.execute(stmt.body, on_complete=on_complete)

            self._ctx.schedule(target_time, resume)
            return

        if isinstance(stmt, Forever):
            self._execute_forever(stmt.body)
            return

        if isinstance(stmt, Repeat):
            self._execute_repeat(stmt.count, stmt.body, on_complete=on_complete)
            return

        if isinstance(stmt, WhileStmt):
            self._execute_while(stmt, on_complete=on_complete)
            return

        if isinstance(stmt, ForStmt):
            self._execute_for(stmt, on_complete=on_complete)
            return

        if isinstance(stmt, IfStmt):
            condition = self._ctx.evaluator.eval(stmt.condition)
            branch = stmt.then_branch if condition else stmt.else_branch
            if branch is not None:
                self.execute(branch, on_complete=on_complete)
            elif on_complete is not None:
                on_complete()
            return

        if isinstance(stmt, CaseStmt):
            self._execute_case(stmt, on_complete=on_complete)
            return

        if isinstance(stmt, Display):
            self._execute_display(stmt)
            if on_complete is not None:
                on_complete()
            return

        if isinstance(stmt, SystemTask):
            self._execute_system_task(stmt)
            if on_complete is not None:
                on_complete()
            return

        if isinstance(stmt, TaskEnable):
            self._ctx.evaluator.call_task(stmt.name, stmt.args)
            if on_complete is not None:
                on_complete()
            return

        if isinstance(stmt, ForkJoin):
            self._execute_fork_join(stmt, on_complete=on_complete)
            return


        if isinstance(stmt, EventControl):
            self._execute_event_control(stmt)
            return

        msg = f"unsupported statement: {type(stmt).__name__}"
        raise RuntimeError(msg)


    def _execute_for(self, stmt: ForStmt, *, on_complete: ContinueCallback | None = None) -> None:
        if stmt.init is not None:
            value = self._ctx.evaluator.eval(stmt.init.expr)
            self._state.assign_lvalue(stmt.init.target, value, blocking=True, time=self._now())

        iterations = 0
        while stmt.condition is None or self._ctx.evaluator.eval(stmt.condition):
            iterations += 1
            if iterations > 10_000:
                msg = "for loop iteration limit exceeded"
                raise RuntimeError(msg)
            StatementRunner(self._state).execute(stmt.body)
            if stmt.step is None:
                break
            value = self._ctx.evaluator.eval(stmt.step.expr)
            self._state.assign_lvalue(stmt.step.target, value, blocking=True, time=self._now())

        if on_complete is not None:
            on_complete()

    def _execute_while(self, stmt: WhileStmt, *, on_complete: ContinueCallback | None = None) -> None:
        if self._ctx.evaluator.eval(stmt.condition):
            self.execute(stmt.body, on_complete=lambda: self._execute_while(stmt, on_complete=on_complete))
            return
        if on_complete is not None:
            on_complete()

    def _execute_fork_join(self, stmt: ForkJoin, *, on_complete: ContinueCallback | None = None) -> None:
        if not isinstance(stmt.body, Block):
            self.execute(stmt.body, on_complete=on_complete)
            return

        branches = stmt.body.statements
        if stmt.join_mode == "join_none":
            for branch in branches:
                self.execute(branch)
            if on_complete is not None:
                on_complete()
            return

        finished = [False]
        remaining = [len(branches)]

        def branch_done() -> None:
            if finished[0]:
                return
            if stmt.join_mode == "join_any":
                finished[0] = True
                if on_complete is not None:
                    on_complete()
                return
            remaining[0] -= 1
            if remaining[0] == 0:
                finished[0] = True
                if on_complete is not None:
                    on_complete()

        for branch in branches:
            self.execute(branch, on_complete=branch_done)


    def _execute_case(self, stmt: CaseStmt, *, on_complete: ContinueCallback | None = None) -> None:
        from hdl_sim.engine.four_state import case_match, eval_four_state

        selector = eval_four_state(stmt.expression, self._ctx.evaluator.eval)
        for item in stmt.items:
            if not item.expressions:
                self.execute(item.body, on_complete=on_complete)
                return
            for pattern in item.expressions:
                pat_val = eval_four_state(pattern, self._ctx.evaluator.eval)
                if case_match(selector, pat_val, stmt.case_style):
                    self.execute(item.body, on_complete=on_complete)
                    return
        if on_complete is not None:
            on_complete()

    def _execute_system_task(self, stmt: SystemTask) -> None:
        if stmt.name == "finish":
            if self._ctx.on_finish is not None:
                self._ctx.on_finish()
            return
        if stmt.name == "stop":
            return
        if stmt.name == "dumpfile":
            if stmt.args and stmt.args[0].text is not None and self._ctx.on_dumpfile is not None:
                self._ctx.on_dumpfile(stmt.args[0].text)
            return
        if stmt.name == "monitor":
            if self._ctx.on_monitor is not None:
                self._ctx.on_monitor(stmt.args)
            return
        if stmt.name == "dumpvars":
            if self._ctx.on_dumpvars is not None:
                self._ctx.on_dumpvars(stmt.args)
            return
        msg = f"unsupported system task: {stmt.name}"
        raise RuntimeError(msg)

    def _execute_statement_list(
        self,
        statements: tuple[Stmt, ...],
        index: int = 0,
        *,
        on_complete: ContinueCallback | None = None,
    ) -> None:
        if index >= len(statements):
            if on_complete is not None:
                on_complete()
            return

        stmt = statements[index]

        if isinstance(stmt, DelayControl):
            target_time = self._now() + stmt.delay

            def resume_after_delay() -> None:
                runner = StatementRunner(self._state)
                runner.execute(stmt.body)
                runner._execute_statement_list(statements, index + 1, on_complete=on_complete)

            self._ctx.schedule(target_time, resume_after_delay)
            return

        if isinstance(stmt, (BlockingAssign, NonBlockingAssign, IfStmt, WhileStmt, ForStmt, CaseStmt)):
            self.execute(stmt)
            self._execute_statement_list(statements, index + 1, on_complete=on_complete)
            return

        if isinstance(stmt, Block):
            nested_runner = StatementRunner(self._state)

            def after_nested() -> None:
                self._execute_statement_list(statements, index + 1, on_complete=on_complete)

            nested_runner.execute(stmt, on_complete=after_nested)
            return

        nested_runner = StatementRunner(self._state)

        def after_stmt() -> None:
            self._execute_statement_list(statements, index + 1, on_complete=on_complete)

        nested_runner.execute(stmt, on_complete=after_stmt)

    def _execute_display(self, stmt: Display) -> None:
        parts: list[str] = []
        format_values: list[int] = []
        for arg in stmt.args:
            if arg.text is not None:
                parts.append(arg.text)
            elif arg.expr is not None:
                format_values.append(self._ctx.evaluator.eval(arg.expr))
        if parts and format_values:
            message = parts[0] % tuple(format_values)
        elif parts:
            message = "".join(parts)
        elif format_values:
            message = " ".join(str(value) for value in format_values)
        else:
            message = ""
        print(message, flush=True)
        if self._ctx.on_display is not None:
            self._ctx.on_display(message, self._now())

    def _execute_forever(self, body: Stmt) -> None:
        def loop() -> None:
            self.execute(body, on_complete=loop)

        loop()

    def _execute_repeat(
        self,
        count: int,
        body: Stmt,
        *,
        on_complete: ContinueCallback | None = None,
    ) -> None:
        def step(remaining: int) -> None:
            if remaining <= 0:
                if on_complete is not None:
                    on_complete()
                return
            self.execute(body, on_complete=lambda: step(remaining - 1))

        step(count)

    def _execute_event_control(self, stmt: EventControl) -> None:
        trigger = self._await_events(stmt.events)

        def arm() -> None:
            if trigger():
                StatementRunner(self._state).execute(stmt.body)
            arm()

        for net in self._nets_in_events(stmt.events):
            net.subscribe(lambda *_args, arm_cb=arm: arm_cb())

        arm()

    def _await_events(self, events: tuple[Expr, ...]) -> Callable[[], bool]:
        if not events:
            return lambda: True

        def trigger() -> bool:
            for event in events:
                if isinstance(event, UnaryExpr) and event.op in {"posedge", "negedge"}:
                    if not isinstance(event.operand, IdentRef):
                        continue
                    net = self._state.context.nets.get(event.operand.name)
                    if net is None or net.previous is None:
                        continue
                    prev_bit = (net.previous >> 0) & 1
                    curr_bit = (net.value >> 0) & 1
                    if event.op == "posedge" and prev_bit == 0 and curr_bit == 1:
                        return True
                    if event.op == "negedge" and prev_bit == 1 and curr_bit == 0:
                        return True
                elif self._ctx.evaluator.eval(event):
                    return True
            return False

        return trigger

    def _nets_in_events(self, events: tuple[Expr, ...]) -> list[SimNet]:
        names: set[str] = set()
        for event in events:
            if isinstance(event, UnaryExpr) and isinstance(event.operand, IdentRef):
                names.add(event.operand.name)
            elif isinstance(event, IdentRef):
                names.add(event.name)
        return [self._state.context.nets[name] for name in names if name in self._state.context.nets]

    def _now(self) -> SimTime:
        return self._ctx.queue.now
