"""Collect identifier dependencies from expressions and statements."""

from __future__ import annotations

from hdl_sim.parser.ast import (
    BinaryExpr,
    BitSelect,
    Block,
    BlockingAssign,
    CaseStmt,
    DelayControl,
    EventControl,
    Expr,
    Forever,
    IdentRef,
    IfStmt,
    IntLiteral,
    Lvalue,
    NonBlockingAssign,
    PartSelect,
    Repeat,
    Stmt,
    UnaryExpr,
    WhileStmt,
    ForStmt,
    ConcatExpr,
)


def identifiers_in_expr(expr: Expr) -> set[str]:
    if isinstance(expr, IntLiteral):
        return set()
    if isinstance(expr, ConcatExpr):
        names: set[str] = set()
        for part in expr.parts:
            names |= identifiers_in_expr(part)
        return names
    if isinstance(expr, IdentRef):
        return {expr.name}
    if isinstance(expr, BitSelect):
        return {expr.signal} | identifiers_in_expr(expr.index)
    if isinstance(expr, PartSelect):
        return {expr.signal} | identifiers_in_expr(expr.msb) | identifiers_in_expr(expr.lsb)
    if isinstance(expr, UnaryExpr):
        return identifiers_in_expr(expr.operand)
    if isinstance(expr, BinaryExpr):
        if expr.op == "?:":
            return (
                identifiers_in_expr(expr.left)
                | identifiers_in_expr(expr.right.left)
                | identifiers_in_expr(expr.right.right)
            )
        return identifiers_in_expr(expr.left) | identifiers_in_expr(expr.right)
    return set()


def identifiers_in_lvalue(lvalue: Lvalue) -> set[str]:
    names = {lvalue.base}
    if lvalue.bit is not None:
        names |= identifiers_in_expr(lvalue.bit)
    if lvalue.msb is not None and lvalue.lsb is not None:
        names |= identifiers_in_expr(lvalue.msb) | identifiers_in_expr(lvalue.lsb)
    return names


def identifiers_in_stmt(stmt: Stmt) -> set[str]:
    if isinstance(stmt, Block):
        result: set[str] = set()
        for child in stmt.statements:
            result |= identifiers_in_stmt(child)
        return result
    if isinstance(stmt, (BlockingAssign, NonBlockingAssign)):
        return identifiers_in_lvalue(stmt.target) | identifiers_in_expr(stmt.expr)
    if isinstance(stmt, DelayControl):
        return identifiers_in_stmt(stmt.body)
    if isinstance(stmt, Forever):
        return identifiers_in_stmt(stmt.body)
    if isinstance(stmt, Repeat):
        return identifiers_in_stmt(stmt.body)
    if isinstance(stmt, ForStmt):
        names: set[str] = set()
        if stmt.init is not None:
            names |= identifiers_in_lvalue(stmt.init.target) | identifiers_in_expr(stmt.init.expr)
        if stmt.condition is not None:
            names |= identifiers_in_expr(stmt.condition)
        if stmt.step is not None:
            names |= identifiers_in_lvalue(stmt.step.target) | identifiers_in_expr(stmt.step.expr)
        return names | identifiers_in_stmt(stmt.body)
    if isinstance(stmt, WhileStmt):
        return identifiers_in_expr(stmt.condition) | identifiers_in_stmt(stmt.body)
    if isinstance(stmt, IfStmt):
        names = identifiers_in_expr(stmt.condition) | identifiers_in_stmt(stmt.then_branch)
        if stmt.else_branch is not None:
            names |= identifiers_in_stmt(stmt.else_branch)
        return names
    if isinstance(stmt, CaseStmt):
        names = identifiers_in_expr(stmt.expression)
        for item in stmt.items:
            for pattern in item.expressions:
                names |= identifiers_in_expr(pattern)
            names |= identifiers_in_stmt(item.body)
        return names
    if isinstance(stmt, EventControl):
        result = set()
        for event in stmt.events:
            result |= identifiers_in_expr(event)
        return result | identifiers_in_stmt(stmt.body)
    return set()
