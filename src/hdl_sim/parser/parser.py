"""Parse a Verilog subset into an AST."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from typing import Any

from lark import Lark, Token, Transformer, Tree, v_args

from hdl_sim.parser.ast import (
    Stmt,
    AlwaysBlock,
    BinaryExpr,
    BitSelect,
    Block,
    BlockingAssign,
    CaseItem,
    CaseStmt,
    ContinuousAssign,
    Declaration,
    DeclKind,
    DelayControl,
    Design,
    EdgeKind,
    EventControl,
    Expr,
    Forever,
    FunctionCall,
    FunctionDef,
    FunctionInput,
    TaskEnable,
    TaskPortKind,
    TaskPort,
    TaskDef,
    IdentRef,
    IfStmt,
    InitialBlock,
    IntLiteral,
    Lvalue,
    Module,
    ModuleInstance,
    NonBlockingAssign,
    PartSelect,
    Port,
    PortConnection,
    PortDirection,
    ParameterDecl,
    ParameterOverride,
    Display,
    DisplayArg,
    StringLiteral,
    SystemTask,
    ValueRange,
    Repeat,
    ForStmt,
    ForkJoin,
    GenerateIf,
    GenerateFor,
    GenerateBlock,
    ConcatExpr,
    UnaryExpr,
    WhileStmt,
)
from hdl_sim.parser.preprocess import normalize_source


def _int(token: Token | str | IntLiteral) -> int:
    if isinstance(token, IntLiteral):
        return token.value
    return int(str(token))


def _parse_sized_number(text: str) -> IntLiteral:
    width_text, base_and_digits = text.split("'", 1)
    width = int(width_text.strip())
    base = base_and_digits[0].lower()
    digits = base_and_digits[1:].replace("_", "")
    value = 0
    x_mask = 0
    z_mask = 0

    def consume_binary() -> None:
        nonlocal value, x_mask, z_mask
        for index, char in enumerate(reversed(digits)):
            bit = 1 << index
            lower = char.lower()
            if lower in {"0", "1"}:
                if lower == "1":
                    value |= bit
            elif lower == "x":
                x_mask |= bit
            elif lower == "z":
                z_mask |= bit
                x_mask |= bit
            else:
                msg = f"invalid digit in sized literal: {char}"
                raise ValueError(msg)

    if base == "b":
        consume_binary()
    elif base == "h":
        expanded = ""
        for char in digits:
            lower = char.lower()
            if lower in "0123456789abcdef":
                expanded += f"{int(lower, 16):04b}"
            elif lower == "x":
                expanded += "xxxx"
            elif lower == "z":
                expanded += "zzzz"
            else:
                msg = f"invalid hex digit: {char}"
                raise ValueError(msg)
        digits = expanded
        consume_binary()
    elif base == "d":
        value = int(digits)
    else:
        msg = f"unsupported sized literal base: {base}"
        raise ValueError(msg)
    mask = (1 << width) - 1
    return IntLiteral(value=value & mask, width=width, x_mask=x_mask & mask, z_mask=z_mask & mask)


def _flatten(values: list[Any]) -> list[Any]:
    flattened: list[Any] = []
    for value in values:
        if isinstance(value, list):
            flattened.extend(_flatten(value))
        else:
            flattened.append(value)
    return flattened


def _fold_binary(op: str, children: tuple[Expr, ...]) -> Expr:
    if len(children) == 1:
        return children[0]
    result = children[0]
    for child in children[1:]:
        result = BinaryExpr(op, result, child)
    return result


SelectInfo = tuple[str, Expr, Expr | None] | None


def _select_info(select: Any | None) -> SelectInfo:
    if select is None:
        return None
    return select


def _lvalue_from_signal(name: str, select: SelectInfo) -> Lvalue:
    if select is None:
        return Lvalue(base=name)
    kind, first, second = select
    if kind == "bit":
        return Lvalue(base=name, bit=first)
    return Lvalue(base=name, msb=first, lsb=second)


def _expr_from_signal(name: str, select: SelectInfo) -> Expr:
    if select is None:
        return IdentRef(name)
    kind, first, second = select
    if kind == "bit":
        return BitSelect(signal=name, index=first)
    assert second is not None
    return PartSelect(signal=name, msb=first, lsb=second)


class VerilogTransformer(Transformer):
    def _child_args(self, children: tuple[Any, ...] | list[Any]) -> list[Any]:
        if len(children) == 1 and isinstance(children[0], list):
            return list(children[0])
        return list(children)

    def _resolve_expr(self, value: Any) -> Any:
        if isinstance(value, Tree):
            return self.transform(value)
        return value

    def _normalize_generate_if(self, genif: GenerateIf) -> GenerateIf:
        return GenerateIf(
            condition=genif.condition,
            then_items=tuple(self._resolve_generate_item(i) for i in _flatten(genif.then_items)),
            else_items=tuple(self._resolve_generate_item(i) for i in _flatten(genif.else_items)),
        )

    def _resolve_generate_item(self, item: Any) -> Any:
        if isinstance(item, Tree):
            if item.data == "generate_item" and item.children:
                return self._resolve_generate_item(item.children[0])
            item = self.transform(item)
        if isinstance(item, GenerateIf):
            return self._normalize_generate_if(item)
        if isinstance(item, GenerateFor):
            return GenerateFor(
                genvar=item.genvar,
                init=item.init,
                condition=item.condition,
                step=item.step,
                body=tuple(self._resolve_generate_item(i) for i in _flatten(item.body)),
                label=item.label,
            )
        if isinstance(item, tuple):
            return self._resolve_generate_items(item)
        return item

    def _resolve_generate_items(self, items: Any) -> tuple[Any, ...]:
        if isinstance(items, tuple):
            raw = list(items)
        elif isinstance(items, list):
            raw = items
        else:
            raw = [items]
        resolved: list[Any] = []
        for item in _flatten(raw):
            if isinstance(item, Tree):
                item = self.transform(item)
            if isinstance(item, tuple):
                resolved.extend(item)
            else:
                resolved.append(item)
        return tuple(resolved)

    def design(self, modules: list[Module]) -> Design:
        return Design(modules=tuple(modules))

    def decl_or_stmt(self, item: Any) -> Any:
        return item

    def module(self, items: list[Any]) -> Module:
        name = str(items[0])
        parameters: list[ParameterDecl] = []
        ports: list[Port] = []
        declarations: list[Declaration] = []
        continuous_assigns: list[ContinuousAssign] = []
        initial_blocks: list[InitialBlock] = []
        always_blocks: list[AlwaysBlock] = []
        instances: list[ModuleInstance] = []
        functions: list[FunctionDef] = []
        tasks: list[TaskDef] = []
        generate_blocks: list[GenerateBlock] = []

        index = 1
        if index < len(items) and isinstance(items[index], list) and items[index]:
            if isinstance(items[index][0], ParameterDecl):
                parameters.extend(items[index])
                index += 1
            elif isinstance(items[index][0], Port):
                ports.extend(items[index])
                index += 1
        for item in items[index:]:
            candidates = item if isinstance(item, list) else [item]
            for candidate in candidates:
                if isinstance(candidate, Port):
                    ports.append(candidate)
                elif isinstance(candidate, ParameterDecl):
                    parameters.append(candidate)
                elif isinstance(candidate, Declaration):
                    declarations.append(candidate)
                elif isinstance(candidate, ContinuousAssign):
                    continuous_assigns.append(candidate)
                elif isinstance(candidate, InitialBlock):
                    initial_blocks.append(candidate)
                elif isinstance(candidate, AlwaysBlock):
                    always_blocks.append(candidate)
                elif isinstance(candidate, FunctionDef):
                    functions.append(candidate)
                elif isinstance(candidate, TaskDef):
                    tasks.append(candidate)
                elif isinstance(candidate, GenerateBlock):
                    generate_blocks.append(candidate)
                elif isinstance(candidate, ModuleInstance):
                    instances.append(candidate)

        return Module(
            name=name,
            parameters=tuple(parameters),
            ports=tuple(ports),
            declarations=tuple(declarations),
            continuous_assigns=tuple(continuous_assigns),
            initial_blocks=tuple(initial_blocks),
            always_blocks=tuple(always_blocks),
            instances=tuple(instances),
            functions=tuple(functions),
            tasks=tuple(tasks),
            generate_blocks=tuple(generate_blocks),
        )

    def port_list(self, ports: list[Port]) -> list[Port]:
        return ports

    @v_args(inline=True)
    def port_decl(self, direction: Token, *rest: Any) -> Port:
        dir_text = str(direction).lower()
        if dir_text == "input":
            port_dir = PortDirection.INPUT
        elif dir_text == "inout":
            port_dir = PortDirection.INOUT
        else:
            port_dir = PortDirection.OUTPUT
        if len(rest) == 2:
            value_range, name = rest
            return Port(direction=port_dir, name=str(name), range=value_range)
        (name,) = rest
        return Port(direction=port_dir, name=str(name))

    @v_args(inline=True)
    def module_instance(
        self,
        module_type: Token,
        *rest: Any,
    ) -> ModuleInstance:
        overrides: tuple[ParameterOverride, ...] = ()
        instance_name: Token
        connections: list[PortConnection] | None = None
        if len(rest) == 1:
            (instance_name,) = rest
        elif len(rest) == 2:
            first, second = rest
            if isinstance(first, list):
                overrides = tuple(first)
                instance_name = second
            else:
                instance_name, connections = first, second
        elif len(rest) == 3:
            overrides = tuple(rest[0])
            instance_name, connections = rest[1], rest[2]
        else:
            msg = "invalid module instance"
            raise ValueError(msg)
        return ModuleInstance(
            module_type=str(module_type),
            instance_name=str(instance_name),
            parameter_overrides=overrides,
            connections=tuple(connections or []),
        )

    def parameter_list(self, params: list[ParameterDecl]) -> list[ParameterDecl]:
        return params

    @v_args(inline=True)
    def parameter_decl(self, name: Token, expr: Expr) -> ParameterDecl:
        return ParameterDecl(name=str(name), expr=expr)

    @v_args(inline=True)
    def parameter_decl_stmt(self, name: Token, expr: Expr) -> ParameterDecl:
        return ParameterDecl(name=str(name), expr=expr)

    def param_instance(self, overrides: list[ParameterOverride]) -> list[ParameterOverride]:
        return overrides

    @v_args(inline=True)
    def param_override(self, name: Token, expr: Expr) -> ParameterOverride:
        return ParameterOverride(name=str(name), expr=expr)

    def port_connections(self, connections: list[PortConnection]) -> list[PortConnection]:
        return connections

    @v_args(inline=True)
    def port_connection(self, port: Token, expr: Expr) -> PortConnection:
        return PortConnection(port=str(port), expr=expr)

    @v_args(inline=True)
    def declaration(self, *rest: Any) -> Declaration:
        if len(rest) == 3:
            decl_type, range_node, name = rest
            if isinstance(decl_type, Token) and str(decl_type.type) == "REG":
                kind = DeclKind.REG
            elif isinstance(decl_type, Token) and str(decl_type.type) == "INTEGER":
                kind = DeclKind.INTEGER
            else:
                kind = DeclKind.WIRE
            return Declaration(kind=kind, name=str(name), range=range_node)
        decl_type, name = rest
        if isinstance(decl_type, Token) and str(decl_type.type) == "REG":
            kind = DeclKind.REG
        elif isinstance(decl_type, Token) and str(decl_type.type) == "INTEGER":
            kind = DeclKind.INTEGER
        else:
            kind = DeclKind.WIRE
        return Declaration(kind=kind, name=str(name))

    @v_args(inline=True)
    def range(self, msb: Expr, lsb: Expr) -> ValueRange:
        return ValueRange(msb=msb, lsb=lsb)

    @v_args(inline=True)
    def continuous_assign(self, target: Lvalue, expr: Expr) -> ContinuousAssign:
        return ContinuousAssign(target=target.base, expr=expr)

    @v_args(inline=True)
    def initial_block(self, body: Stmt) -> InitialBlock:
        return InitialBlock(body=body)

    @v_args(inline=True)
    def always_block(self, sensitivity: Any, body: Stmt) -> AlwaysBlock:
        return AlwaysBlock(sensitivity=sensitivity, body=body)

    @v_args(inline=True)
    def posedge(self, name: Token) -> tuple[EdgeKind, str]:
        return (EdgeKind.POSEDGE, str(name))

    @v_args(inline=True)
    def negedge(self, name: Token) -> tuple[EdgeKind, str]:
        return (EdgeKind.NEGEDGE, str(name))

    @v_args(inline=True)
    def level(self, name: Token) -> tuple[None, str]:
        return (None, str(name))

    def sensitivity(self, *items: Any) -> tuple[tuple[EdgeKind | None, str], ...] | None:
        if len(items) == 1 and str(items[0]) == "*":
            return None
        if len(items) == 1 and isinstance(items[0], list):
            return tuple(items[0])
        return tuple(items)

    @v_args(inline=True)
    def begin_labeled(self, label: Token, stmt_list: list[Stmt]) -> Block:
        return Block(statements=tuple(_flatten(stmt_list)), label=str(label))

    def begin_plain(self, stmt_list: list[Stmt]) -> Block:
        return Block(statements=tuple(_flatten(stmt_list)))

    def begin_end_block(self, stmt_list: list[Stmt]) -> Block:
        return Block(statements=tuple(_flatten(stmt_list)))

    def stmt_list(self, stmts: list[Stmt]) -> list[Stmt]:
        return stmts

    def display_args(self, args: list[DisplayArg]) -> list[DisplayArg]:
        return args

    @v_args(inline=True)
    def display_arg(self, value: Any) -> DisplayArg:
        if isinstance(value, StringLiteral):
            return DisplayArg(text=value.value)
        return DisplayArg(expr=value)

    @v_args(inline=True)
    def display(self, args: list[DisplayArg] | None = None) -> Display:
        return Display(args=tuple(args or []))

    @v_args(inline=True)
    def finish(self) -> SystemTask:
        return SystemTask(name="finish")

    @v_args(inline=True)
    def stop(self) -> SystemTask:
        return SystemTask(name="stop")

    @v_args(inline=True)
    def dumpfile(self, path: StringLiteral) -> SystemTask:
        return SystemTask(name="dumpfile", args=(DisplayArg(text=path.value),))

    @v_args(inline=True)
    def dumpvars(self, args: list[DisplayArg] | None = None) -> SystemTask:
        return SystemTask(name="dumpvars", args=tuple(args or []))

    @v_args(inline=True)
    def STRING(self, token: Token) -> StringLiteral:
        raw = str(token)
        return StringLiteral(value=raw[1:-1])

    @v_args(inline=True)
    def signal_ref(self, name: Token, select: SelectInfo = None) -> tuple[str, SelectInfo]:
        return (str(name), _select_info(select))

    @v_args(inline=True)
    def to_lvalue(self, ref: tuple[str, SelectInfo]) -> Lvalue:
        return _lvalue_from_signal(ref[0], ref[1])

    @v_args(inline=True)
    def signal_expr(self, ref: tuple[str, SelectInfo]) -> Expr:
        return _expr_from_signal(ref[0], ref[1])

    @v_args(inline=True)
    def bit_sel(self, index: Expr) -> SelectInfo:
        return ("bit", index, None)

    @v_args(inline=True)
    def part_sel(self, msb: Expr, lsb: Expr) -> SelectInfo:
        return ("part", msb, lsb)

    @v_args(inline=True)
    def blocking_assign(self, target: Lvalue, expr: Expr) -> BlockingAssign:
        return BlockingAssign(target=target, expr=expr)

    @v_args(inline=True)
    def nonblocking_assign(self, target: Lvalue, expr: Expr) -> NonBlockingAssign:
        return NonBlockingAssign(target=target, expr=expr)

    @v_args(inline=True)
    def delay_control(self, delay: Token | IntLiteral, body: Stmt) -> DelayControl:
        value = delay.value if isinstance(delay, IntLiteral) else _int(delay)
        return DelayControl(delay=value, body=body)

    @v_args(inline=True)
    def forever_stmt(self, body: Stmt) -> Forever:
        return Forever(body=body)

    @v_args(inline=True)
    def repeat_stmt(self, count: Token | IntLiteral, body: Stmt) -> Repeat:
        value = count.value if isinstance(count, IntLiteral) else _int(count)
        return Repeat(count=value, body=body)



    def generate_block(self, items: list[Any]) -> GenerateBlock:
        return GenerateBlock(items=tuple(self._resolve_generate_item(i) for i in _flatten(items)))

    @v_args(inline=True)
    def gen_begin_labeled(self, label: Token, items: list[Any]) -> tuple[str, Any]:
        return ("labeled", str(label), self._resolve_generate_items(items))

    def gen_begin(self, items: list[Any]) -> tuple[Any, ...]:
        return self._resolve_generate_items(items)

    def gen_single(self, item: Any) -> tuple[Any, ...]:
        return self._resolve_generate_items(item)

    @v_args(inline=True)
    def genvar_init(self, *items: Any) -> tuple[str, Expr]:
        if len(items) == 3:
            return str(items[1]), items[2]
        return str(items[0]), items[1]

    def gen_for(self, *children: Any) -> GenerateFor:
        flat = self._child_args(children)
        genvar, init = flat[0]
        condition = flat[1]
        step = flat[2]
        body_raw = flat[3]
        label = None
        if isinstance(body_raw, tuple) and len(body_raw) == 3 and body_raw[0] == "labeled":
            label = body_raw[1]
            body = body_raw[2]
        else:
            body = self._resolve_generate_items(body_raw)
        return GenerateFor(
            genvar=genvar,
            init=init,
            condition=condition,
            step=step,
            body=body,
            label=label,
        )

    def gen_if(self, *children: Any) -> GenerateIf:
        flat = self._child_args(children)
        condition = flat[0]
        then_items = self._resolve_generate_items(flat[1])
        else_items: tuple[Any, ...] = ()
        if len(flat) > 2:
            else_items = self._resolve_generate_items(flat[2])
        return self._normalize_generate_if(GenerateIf(condition=condition, then_items=then_items, else_items=else_items))

    @v_args(inline=True)
    def fork_join(self, body: Stmt) -> ForkJoin:
        return ForkJoin(body=body, join_mode="join")

    @v_args(inline=True)
    def fork_join_any(self, body: Stmt) -> ForkJoin:
        return ForkJoin(body=body, join_mode="join_any")

    @v_args(inline=True)
    def fork_join_none(self, body: Stmt) -> ForkJoin:
        return ForkJoin(body=body, join_mode="join_none")


    def task_decl(self, children: list[Any]) -> TaskDef:
        flat = self._child_args(tuple(children))
        name = str(flat[0])
        ports: list[TaskPort] = []
        declarations: list[Declaration] = []
        statements: list[Stmt] = []
        for item in flat[1:]:
            if isinstance(item, TaskPort):
                ports.append(item)
            elif isinstance(item, Declaration):
                declarations.append(item)
            elif isinstance(item, Block):
                statements.extend(item.statements)
            elif isinstance(item, Stmt):
                statements.append(item)
            elif hasattr(item, "data") and item.data == "task_item":
                resolved = self.transform(item)
                if isinstance(resolved, Block):
                    statements.extend(resolved.statements)
                elif isinstance(resolved, Stmt):
                    statements.append(resolved)
        return TaskDef(
            name=name,
            ports=tuple(ports),
            declarations=tuple(declarations),
            body_statements=tuple(statements),
        )

    def task_item(self, children: list[Any]) -> Stmt | Block:
        return self._resolve_expr(children[0])

    @v_args(inline=True)
    def task_input(self, *rest: Any) -> TaskPort:
        if len(rest) == 2:
            value_range, name = rest
            return TaskPort(kind=TaskPortKind.INPUT, name=str(name), range=value_range)
        (name,) = rest
        return TaskPort(kind=TaskPortKind.INPUT, name=str(name))

    @v_args(inline=True)
    def task_output(self, *rest: Any) -> TaskPort:
        if len(rest) == 2:
            value_range, name = rest
            return TaskPort(kind=TaskPortKind.OUTPUT, name=str(name), range=value_range)
        (name,) = rest
        return TaskPort(kind=TaskPortKind.OUTPUT, name=str(name))

    @v_args(inline=True)
    def task_call(self, name: Token, *args: Expr) -> TaskEnable:
        return TaskEnable(name=str(name), args=tuple(args))

    @v_args(inline=True)
    def task_call_empty(self, name: Token) -> TaskEnable:
        return TaskEnable(name=str(name), args=())


    def function_decl(self, children: list[Any]) -> FunctionDef:
        flat = self._child_args(tuple(children))
        index = 0
        return_range: ValueRange | None = None
        if index < len(flat) and isinstance(flat[index], ValueRange):
            return_range = flat[index]
            index += 1
        name = str(flat[index])
        index += 1
        inputs: list[FunctionInput] = []
        declarations: list[Declaration] = []
        statements: list[Stmt] = []
        for item in flat[index:]:
            if isinstance(item, FunctionInput):
                inputs.append(item)
            elif isinstance(item, Declaration):
                declarations.append(item)
            elif isinstance(item, Block):
                statements.extend(item.statements)
            elif isinstance(item, Stmt):
                statements.append(item)
            elif hasattr(item, 'data') and item.data == 'function_item':
                resolved = self.transform(item)
                if isinstance(resolved, Block):
                    statements.extend(resolved.statements)
                elif isinstance(resolved, Stmt):
                    statements.append(resolved)
        return FunctionDef(
            name=name,
            return_range=return_range,
            inputs=tuple(inputs),
            declarations=tuple(declarations),
            body_statements=tuple(statements),
        )

    def function_item(self, children: list[Any]) -> Stmt | Block:
        return self._resolve_expr(children[0])

    @v_args(inline=True)
    def func_input(self, *rest: Any) -> FunctionInput:
        if len(rest) == 2:
            value_range, name = rest
            return FunctionInput(name=str(name), range=value_range)
        (name,) = rest
        return FunctionInput(name=str(name))

    @v_args(inline=True)
    def func_call(self, name: Token, *args: Expr) -> FunctionCall:
        return FunctionCall(name=str(name), args=tuple(args))

    def concat_expr(self, children: list[Any]) -> ConcatExpr:
        return ConcatExpr(parts=tuple(self._child_args(tuple(children))))

    @v_args(inline=True)
    def for_init(self, target: Lvalue, expr: Expr) -> BlockingAssign:
        return BlockingAssign(target=target, expr=expr)

    @v_args(inline=True)
    def for_step(self, target: Lvalue, expr: Expr) -> BlockingAssign:
        return BlockingAssign(target=target, expr=expr)

    def for_stmt(self, children: list[Any]) -> ForStmt:
        flat = self._child_args(tuple(children))
        init: BlockingAssign | None = None
        condition: Expr | None = None
        step: BlockingAssign | None = None
        body: Stmt = flat[-1]
        index = 0
        if index < len(flat) - 1 and isinstance(flat[index], BlockingAssign):
            init = flat[index]
            index += 1
        if index < len(flat) - 1 and not isinstance(flat[index], BlockingAssign):
            condition = flat[index]
            index += 1
        if index < len(flat) - 1 and isinstance(flat[index], BlockingAssign):
            step = flat[index]
        return ForStmt(init=init, condition=condition, step=step, body=body)

    @v_args(inline=True)
    def monitor(self, args: list[DisplayArg] | None = None) -> SystemTask:
        return SystemTask(name="monitor", args=tuple(args or []))
    @v_args(inline=True)
    def while_stmt(self, condition: Expr, body: Stmt) -> WhileStmt:
        return WhileStmt(condition=condition, body=body)

    @v_args(inline=True)
    def if_stmt(self, condition: Expr, then_branch: Stmt, else_branch: Stmt | None = None) -> IfStmt:
        return IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch)

    def case(self, children: list[Any]) -> CaseStmt:
        flat = self._child_args(tuple(children))
        return CaseStmt(expression=flat[0], items=tuple(flat[1:]), case_style="case")

    def casex(self, children: list[Any]) -> CaseStmt:
        flat = self._child_args(tuple(children))
        return CaseStmt(expression=flat[0], items=tuple(flat[1:]), case_style="casex")

    def casez(self, children: list[Any]) -> CaseStmt:
        flat = self._child_args(tuple(children))
        return CaseStmt(expression=flat[0], items=tuple(flat[1:]), case_style="casez")

    @v_args(inline=True)
    def case_item(self, pattern: Any, body: Stmt) -> CaseItem:
        if pattern == "default":
            return CaseItem(expressions=(), body=body)
        if isinstance(pattern, tuple):
            return CaseItem(expressions=pattern, body=body)
        return CaseItem(expressions=(pattern,), body=body)

    @v_args(inline=True)
    def default_pat(self) -> str:
        return "default"

    def expr_pat(self, children: list[Any]) -> tuple[Expr, ...]:
        return tuple(self._child_args(tuple(children)))

    @v_args(inline=True)
    def ev_posedge(self, name: Token) -> Expr:
        return UnaryExpr("posedge", IdentRef(str(name)))

    @v_args(inline=True)
    def ev_negedge(self, name: Token) -> Expr:
        return UnaryExpr("negedge", IdentRef(str(name)))

    @v_args(inline=True)
    def ev_expr(self, expr: Expr) -> Expr:
        return expr

    def event_control(self, *events: Expr, body: Stmt | None = None) -> EventControl:
        if body is None:
            *event_nodes, body = events
            return EventControl(events=tuple(event_nodes), body=body)
        return EventControl(events=tuple(events), body=body)

    def ternary_expr(self, *children: Any) -> Expr:
        children = self._child_args(children)
        if len(children) == 1:
            return children[0]
        condition, true_expr, false_expr = children
        return BinaryExpr("?:", condition, BinaryExpr("?:", true_expr, false_expr))

    def lor_expr(self, children: list[Any]) -> Expr:
        resolved = [self._resolve_expr(c) for c in children]
        return _fold_binary("||", tuple(resolved))

    def land_expr(self, children: list[Any]) -> Expr:
        resolved = [self._resolve_expr(c) for c in children]
        return _fold_binary("&&", tuple(resolved))

    def bitor_expr(self, children: list[Any]) -> Expr:
        resolved = [self._resolve_expr(c) for c in children]
        return _fold_binary("|", tuple(resolved))

    def bitxor_expr(self, children: list[Any]) -> Expr:
        resolved = [self._resolve_expr(c) for c in children]
        return _fold_binary("^", tuple(resolved))

    def bitand_expr(self, children: list[Any]) -> Expr:
        resolved = [self._resolve_expr(c) for c in children]
        return _fold_binary("&", tuple(resolved))

    def eq_expr(self, *children: Any) -> Expr:
        children = self._child_args(children)
        if len(children) == 1:
            return self._resolve_expr(children[0])
        result = children[0]
        index = 1
        while index < len(children):
            op = str(children[index])
            right = children[index + 1]
            result = BinaryExpr(op, result, right)
            index += 2
        return result

    def rel_expr(self, *children: Any) -> Expr:
        children = self._child_args(children)
        resolved = [self._resolve_expr(child) for child in children]
        if len(resolved) == 1:
            return resolved[0]
        result = resolved[0]
        index = 1
        while index < len(resolved):
            op = str(resolved[index])
            if op in {"ADD_OP", "+"}:
                op = "+"
            elif op in {"SUB_OP", "-"}:
                op = "-"
            elif op.startswith("OP_"):
                op = op[3:].lower()
                if op == "lt":
                    op = "<"
                elif op == "le":
                    op = "<="
                elif op == "gt":
                    op = ">"
                elif op == "ge":
                    op = ">="
            right = resolved[index + 1]
            result = BinaryExpr(op, result, right)
            index += 2
        return result

    def shift_expr(self, *children: Any) -> Expr:
        children = self._child_args(children)
        resolved = [self._resolve_expr(child) for child in children]
        if len(resolved) == 1:
            return resolved[0]
        result = resolved[0]
        index =  1
        while index < len(resolved):
            op = str(resolved[index])
            if op.startswith("OP_"):
                op = "<<" if "SHL" in op else ">>"
            right = resolved[index + 1]
            result = BinaryExpr(op, result, right)
            index += 2
        return result

    def add_expr(self, children: list[Any]) -> Expr:
        if len(children) == 1 and isinstance(children[0], list):
            children = children[0]
        if len(children) == 1:
            return children[0]
        if len(children) >= 3 and all(not isinstance(child, Token) for child in children):
            return _fold_binary("+", tuple(children))
        result = children[0]
        index = 1
        while index < len(children):
            op = str(children[index])
            right = children[index + 1]
            result = BinaryExpr(op, result, right)
            index += 2
        return result

    def mul_expr(self, *children: Any) -> Expr:
        return self.add_expr(list(children))

    @v_args(inline=True)
    def not_(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("!", operand)

    @v_args(inline=True)
    def invert(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("~", operand)

    @v_args(inline=True)
    def neg(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("-", operand)

    @v_args(inline=True)
    def uand(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("uand", operand)

    @v_args(inline=True)
    def uor(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("uor", operand)

    @v_args(inline=True)
    def uxor(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("uxor", operand)

    @v_args(inline=True)
    def NUMBER(self, token: Token) -> IntLiteral:
        return IntLiteral(value=_int(token))

    @v_args(inline=True)
    def sized_number(self, token: Token) -> IntLiteral:
        return _parse_sized_number(str(token))


@lru_cache(maxsize=1)
def _build_parser() -> Lark:
    grammar = resources.files("hdl_sim.parser").joinpath("verilog.lark").read_text(encoding="utf-8")
    return Lark(
        grammar,
        parser="lalr",
        propagate_positions=False,
        maybe_placeholders=False,
    )


def parse_design(source: str) -> Design:
    """Parse Verilog source into a design with one or more modules."""

    normalized = normalize_source(source)
    tree = _build_parser().parse(normalized)
    design = VerilogTransformer().transform(tree)
    if not isinstance(design, Design):
        msg = "expected a design as the parse result"
        raise TypeError(msg)
    return design


def parse_module(source: str) -> Module:
    """Parse Verilog source and return the top module."""

    return parse_design(source).top
