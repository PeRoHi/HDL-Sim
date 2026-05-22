"""Parse a Verilog subset into an AST."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from typing import Any

from lark import Lark, Token, Transformer, v_args

from hdl_sim.parser.ast import (
    Stmt,
    AlwaysBlock,
    BinaryExpr,
    Block,
    BlockingAssign,
    ContinuousAssign,
    Declaration,
    DeclKind,
    DelayControl,
    Design,
    EdgeKind,
    EventControl,
    Expr,
    Forever,
    IdentRef,
    IfStmt,
    InitialBlock,
    IntLiteral,
    Module,
    ModuleInstance,
    NonBlockingAssign,
    Port,
    PortConnection,
    PortDirection,
    ParameterDecl,
    ParameterOverride,
    Display,
    DisplayArg,
    StringLiteral,
    ValueRange,
    Range,
    Repeat,
    UnaryExpr,
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
    if base == "b":
        value = int(digits.replace("x", "0").replace("z", "0"), 2)
    elif base == "h":
        value = int(digits.replace("x", "0").replace("z", "0"), 16)
    elif base == "d":
        value = int(digits)
    else:
        msg = f"unsupported sized literal base: {base}"
        raise ValueError(msg)
    return IntLiteral(value=value, width=width)




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


class VerilogTransformer(Transformer):
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
        )

    def port_list(self, ports: list[Port]) -> list[Port]:
        return ports

    @v_args(inline=True)
    def port_decl(self, direction: Token, *rest: Any) -> Port:
        port_dir = PortDirection.INPUT if str(direction).lower() == "input" else PortDirection.OUTPUT
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
            kind = DeclKind.REG if isinstance(decl_type, Token) and str(decl_type.type) == "REG" else DeclKind.WIRE
            return Declaration(kind=kind, name=str(name), range=range_node)
        decl_type, name = rest
        kind = DeclKind.REG if isinstance(decl_type, Token) and str(decl_type.type) == "REG" else DeclKind.WIRE
        return Declaration(kind=kind, name=str(name))

    @v_args(inline=True)
    def range(self, msb: Expr, lsb: Expr) -> ValueRange:
        return ValueRange(msb=msb, lsb=lsb)

    @v_args(inline=True)
    def continuous_assign(self, target: Token, expr: Expr) -> ContinuousAssign:
        return ContinuousAssign(target=str(target), expr=expr)

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
    def display_stmt(self, args: list[DisplayArg] | None = None) -> Display:
        return Display(args=tuple(args or []))

    @v_args(inline=True)
    def STRING(self, token: Token) -> StringLiteral:
        raw = str(token)
        return StringLiteral(value=raw[1:-1])

    @v_args(inline=True)
    def blocking_assign(self, target: Token, expr: Expr) -> BlockingAssign:
        return BlockingAssign(target=str(target), expr=expr)

    @v_args(inline=True)
    def nonblocking_assign(self, target: Token, expr: Expr) -> NonBlockingAssign:
        return NonBlockingAssign(target=str(target), expr=expr)

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

    @v_args(inline=True)
    def if_stmt(self, condition: Expr, then_branch: Stmt, else_branch: Stmt | None = None) -> IfStmt:
        return IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch)

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

    def ternary_expr(self, *children: Expr) -> Expr:
        if len(children) == 1:
            return children[0]
        condition, true_expr, false_expr = children
        return BinaryExpr("?:", condition, BinaryExpr("?:", true_expr, false_expr))

    def lor_expr(self, children: list[Expr]) -> Expr:
        return _fold_binary("||", tuple(children))

    def land_expr(self, children: list[Expr]) -> Expr:
        return _fold_binary("&&", tuple(children))

    def bor_expr(self, children: list[Expr]) -> Expr:
        return _fold_binary("|", tuple(children))

    def bxor_expr(self, children: list[Expr]) -> Expr:
        return _fold_binary("^", tuple(children))

    def band_expr(self, children: list[Expr]) -> Expr:
        return _fold_binary("&", tuple(children))

    def eq_expr(self, *children: Any) -> Expr:
        if len(children) == 1:
            return children[0]
        result = children[0]
        index = 1
        while index < len(children):
            op = str(children[index])
            right = children[index + 1]
            result = BinaryExpr(op, result, right)
            index += 2
        return result

    def rel_expr(self, *children: Any) -> Expr:
        if len(children) == 1:
            return children[0]
        result = children[0]
        index = 1
        while index < len(children):
            op = str(children[index])
            right = children[index + 1]
            result = BinaryExpr(op, result, right)
            index += 2
        return result

    def shift_expr(self, *children: Any) -> Expr:
        return self.rel_expr(*children)

    def add_expr(self, children: list[Any]) -> Expr:
        if len(children) == 1 and isinstance(children[0], list):
            children = children[0]
        if len(children) == 1:
            return children[0]
        if all(not isinstance(child, Token) for child in children):
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
        return self.add_expr(*children)

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
    def NUMBER(self, token: Token) -> IntLiteral:
        return IntLiteral(value=_int(token))

    @v_args(inline=True)
    def sized_number(self, token: Token) -> IntLiteral:
        return _parse_sized_number(str(token))

    @v_args(inline=True)
    def ident_ref(self, token: Token) -> IdentRef:
        return IdentRef(str(token))


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
