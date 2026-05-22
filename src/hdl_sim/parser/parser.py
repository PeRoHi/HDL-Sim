"""Parse a Verilog subset into an AST."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from typing import Any

from lark import Lark, Token, Transformer, v_args

from hdl_sim.parser.ast import (
    Stmt,
    AlwaysBlock,
    AssignStmt,
    BinaryExpr,
    Block,
    BlockingAssign,
    ConcatExpr,
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
    NonBlockingAssign,
    Range,
    Repeat,
    SourceLocation,
    UnaryExpr,
)
from hdl_sim.parser.preprocess import normalize_source


def _int(token: Token | str) -> int:
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


@v_args(inline=True)
class VerilogTransformer(Transformer):
    def decl_or_stmt(self, item: Any) -> Any:
        return item

    def module(self, name: Token, *items: Any) -> Module:
        declarations: list[Declaration] = []
        continuous_assigns: list[ContinuousAssign] = []
        initial_blocks: list[InitialBlock] = []
        always_blocks: list[AlwaysBlock] = []
        for item in items:
            if isinstance(item, Declaration):
                declarations.append(item)
            elif isinstance(item, ContinuousAssign):
                continuous_assigns.append(item)
            elif isinstance(item, InitialBlock):
                initial_blocks.append(item)
            elif isinstance(item, AlwaysBlock):
                always_blocks.append(item)
        return Module(
            name=str(name),
            declarations=tuple(declarations),
            continuous_assigns=tuple(continuous_assigns),
            initial_blocks=tuple(initial_blocks),
            always_blocks=tuple(always_blocks),
        )

    def declaration(self, decl_type: Token, *rest: Any) -> Declaration:
        if len(rest) == 2:
            range_node, name = rest
            return Declaration(
                kind=DeclKind.REG if str(decl_type).lower() == "reg" else DeclKind.WIRE,
                name=str(name),
                range=range_node,
            )
        (name,) = rest
        return Declaration(
            kind=DeclKind.REG if str(decl_type).lower() == "reg" else DeclKind.WIRE,
            name=str(name),
        )

    def range(self, msb: Token, lsb: Token) -> Range:
        return Range(msb=_int(msb), lsb=_int(lsb))

    def continuous_assign(self, target: Token, expr: Expr) -> ContinuousAssign:
        return ContinuousAssign(target=str(target), expr=expr)

    def initial_block(self, body: Stmt) -> InitialBlock:
        return InitialBlock(body=body)

    def always_block(self, sensitivity: Any, body: Stmt) -> AlwaysBlock:
        return AlwaysBlock(sensitivity=sensitivity, body=body)

    def posedge(self, name: Token) -> tuple[EdgeKind, str]:
        return (EdgeKind.POSEDGE, str(name))

    def negedge(self, name: Token) -> tuple[EdgeKind, str]:
        return (EdgeKind.NEGEDGE, str(name))

    def level(self, name: Token) -> tuple[None, str]:
        return (None, str(name))

    def sensitivity(self, *items: Any) -> tuple[tuple[EdgeKind | None, str], ...] | None:
        if len(items) == 1 and str(items[0]) == "*":
            return None
        return tuple(items)

    def block(self, stmt_list: list[Stmt]) -> Block:
        return Block(statements=tuple(stmt_list))

    def stmt_list(self, *stmts: Stmt) -> list[Stmt]:
        return list(stmts)

    def blocking_assign(self, target: Token, expr: Expr) -> BlockingAssign:
        return BlockingAssign(target=str(target), expr=expr)

    def nonblocking_assign(self, target: Token, expr: Expr) -> NonBlockingAssign:
        return NonBlockingAssign(target=str(target), expr=expr)

    def delay_control(self, delay: Token | IntLiteral, body: Stmt) -> DelayControl:
        value = delay.value if isinstance(delay, IntLiteral) else _int(delay)
        return DelayControl(delay=value, body=body)

    def forever_stmt(self, body: Stmt) -> Forever:
        return Forever(body=body)

    def repeat_stmt(self, count: Token | IntLiteral, body: Stmt) -> Repeat:
        value = count.value if isinstance(count, IntLiteral) else _int(count)
        return Repeat(count=value, body=body)

    def if_stmt(self, condition: Expr, then_branch: Stmt, else_branch: Stmt | None = None) -> IfStmt:
        return IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch)

    def ev_posedge(self, name: Token) -> Expr:
        return UnaryExpr("posedge", IdentRef(str(name)))

    def ev_negedge(self, name: Token) -> Expr:
        return UnaryExpr("negedge", IdentRef(str(name)))

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

    def lor_expr(self, *children: Expr) -> Expr:
        return _fold_binary("||", children)

    def land_expr(self, *children: Expr) -> Expr:
        return _fold_binary("&&", children)

    def bor_expr(self, *children: Expr) -> Expr:
        return _fold_binary("|", children)

    def bxor_expr(self, *children: Expr) -> Expr:
        return _fold_binary("^", children)

    def band_expr(self, *children: Expr) -> Expr:
        return _fold_binary("&", children)

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

    def add_expr(self, *children: Any) -> Expr:
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

    def mul_expr(self, *children: Any) -> Expr:
        return self.add_expr(*children)

    def not_(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("!", operand)

    def invert(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("~", operand)

    def neg(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("-", operand)

    def NUMBER(self, token: Token) -> IntLiteral:
        return IntLiteral(value=_int(token))

    def sized_number(self, token: Token) -> IntLiteral:
        return _parse_sized_number(str(token))

    def ident_ref(self, token: Token) -> IdentRef:
        return IdentRef(str(token))


def _fold_binary(op: str, children: tuple[Expr, ...]) -> Expr:
    if len(children) == 1:
        return children[0]
    result = children[0]
    for child in children[1:]:
        result = BinaryExpr(op, result, child)
    return result




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
    """Parse Verilog source into a single-module design."""

    normalized = normalize_source(source)
    tree = _build_parser().parse(normalized)
    module = VerilogTransformer().transform(tree)
    if not isinstance(module, Module):
        msg = "expected a module as the parse result"
        raise TypeError(msg)
    return Design(modules=(module,))


def parse_module(source: str) -> Module:
    """Parse Verilog source and return the top module."""

    return parse_design(source).top
