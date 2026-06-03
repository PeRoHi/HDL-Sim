"""Parameter expression evaluation during elaboration."""

from __future__ import annotations

from hdl_sim.parser.ast import (
    BinaryExpr,
    ConcatExpr,
    Expr,
    FunctionCall,
    IdentRef,
    IntLiteral,
    ParameterDecl,
    ParameterOverride,
    Range,
    ReplicationExpr,
    UnaryExpr,
    ValueRange,
)


def _builtin_clog2(value: int) -> int:
    if value <= 0:
        return 0
    return (value - 1).bit_length()


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
        if isinstance(expr, ConcatExpr):
            value = 0
            shift = 0
            for part in expr.parts:
                part_value = self.eval(part)
                part_width = self._bit_width(part)
                mask = (1 << part_width) - 1 if part_width else 0
                value |= (part_value & mask) << shift
                shift += part_width
            return value
        if isinstance(expr, ReplicationExpr):
            count = self.eval(expr.count)
            inner_value = self.eval(expr.expr)
            inner_width = self._bit_width(expr.expr)
            mask = (1 << inner_width) - 1 if inner_width else 0
            value = 0
            for index in range(count):
                value |= (inner_value & mask) << (index * inner_width)
            return value
        if isinstance(expr, FunctionCall):
            if expr.name == "$clog2":
                if len(expr.args) != 1:
                    msg = "$clog2 expects one argument"
                    raise ParameterEvaluationError(msg)
                return _builtin_clog2(self.eval(expr.args[0]))
            msg = f"unsupported function in parameter: {expr.name}"
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
            if expr.op == "/":
                return left // right
            if expr.op == "<<":
                return left << right
            if expr.op == ">>":
                return left >> right
            if expr.op == ">>>":
                return left >> right if left >= 0 else -((-left) >> right)
            if expr.op == "==":
                return 1 if left == right else 0
            if expr.op == "!=":
                return 1 if left != right else 0
            if expr.op == "<":
                return 1 if left < right else 0
            if expr.op == "<=":
                return 1 if left <= right else 0
            if expr.op == ">":
                return 1 if left > right else 0
            if expr.op == ">=":
                return 1 if left >= right else 0
            msg = f"unsupported binary operator in parameter: {expr.op}"
            raise ParameterEvaluationError(msg)
        msg = f"unsupported parameter expression: {type(expr).__name__}"
        raise ParameterEvaluationError(msg)

    def snapshot(self) -> dict[str, int]:
        return dict(self._values)

    def _bit_width(self, expr: Expr) -> int:
        if isinstance(expr, IntLiteral) and expr.width is not None:
            return expr.width
        if isinstance(expr, ConcatExpr):
            return sum(self._bit_width(part) for part in expr.parts)
        if isinstance(expr, ReplicationExpr):
            return self.eval(expr.count) * self._bit_width(expr.expr)
        msg = f"cannot infer width for parameter expression: {type(expr).__name__}"
        raise ParameterEvaluationError(msg)

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
