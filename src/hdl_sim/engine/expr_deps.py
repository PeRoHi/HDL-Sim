"""Collect identifier dependencies from expressions."""

from __future__ import annotations

from hdl_sim.parser.ast import BinaryExpr, Expr, IdentRef, IntLiteral, UnaryExpr


def identifiers_in_expr(expr: Expr) -> set[str]:
    if isinstance(expr, IntLiteral):
        return set()
    if isinstance(expr, IdentRef):
        return {expr.name}
    if isinstance(expr, UnaryExpr):
        return identifiers_in_expr(expr.operand)
    if isinstance(expr, BinaryExpr):
        if expr.op == "?:":
            return identifiers_in_expr(expr.left) | identifiers_in_expr(expr.right.left) | identifiers_in_expr(
                expr.right.right
            )
        return identifiers_in_expr(expr.left) | identifiers_in_expr(expr.right)
    return set()
