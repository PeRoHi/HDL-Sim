"""Parameter expression evaluation during elaboration."""

from __future__ import annotations

from hdl_sim.parser.ast import (
    BinaryExpr,
    Expr,
    IdentRef,
    IntLiteral,
    ParameterDecl,
    ParameterOverride,
    Range,
    UnaryExpr,
    ValueRange,
)


class ParameterEvaluationError(RuntimeError):
    pass


class ParameterEvaluator:
    """Evaluate parameter expressions to integer constants."""

    def __init__(self, values: dict[str, int] | None = None) -> None:
        self._values: dict[str, int] = dict(values or {})

    def eval(self, expr: Expr) -> int:
        if isinstance(expr, IntLiteral):
            return expr.value
        if isinstance(expr, IdentRef):
            try:
                return self._values[expr.name]
            except KeyError as exc:
                msg = f"unknown parameter: {expr.name}"
                raise ParameterEvaluationError(msg) from exc
        if isinstance(expr, UnaryExpr):
            value = self.eval(expr.operand)
            if expr.op == "-":
                return -value
            if expr.op == "~":
                return ~value
            msg = f"unsupported unary operator in parameter: {expr.op}"
            raise ParameterEvaluationError(msg)
        if isinstance(expr, BinaryExpr):
            if expr.op == "?:":
                condition = self.eval(expr.left)
                true_expr, false_expr = expr.right.left, expr.right.right
                return self.eval(true_expr if condition else false_expr)
            left = self.eval(expr.left)
            right = self.eval(expr.right)
            if expr.op == "+":
                return left + right
            if expr.op == "-":
                return left - right
            if expr.op == "*":
                return left * right
            if expr.op == "<<":
                return left << right
            if expr.op == ">>":
                return left >> right
            msg = f"unsupported binary operator in parameter: {expr.op}"
            raise ParameterEvaluationError(msg)
        msg = f"unsupported parameter expression: {type(expr).__name__}"
        raise ParameterEvaluationError(msg)

    def snapshot(self) -> dict[str, int]:
        return dict(self._values)

    def resolve_module_params(
        self,
        defaults: tuple[ParameterDecl, ...],
        overrides: tuple[ParameterOverride, ...] = (),
    ) -> dict[str, int]:
        for decl in defaults:
            if decl.name not in self._values:
                self._values[decl.name] = self.eval(decl.expr)
        for override in overrides:
            self._values[override.name] = self.eval(override.expr)
        return dict(self._values)

    def resolve_range(self, value_range: ValueRange | None) -> Range | None:
        if value_range is None:
            return None
        return Range(msb=self.eval(value_range.msb), lsb=self.eval(value_range.lsb))
