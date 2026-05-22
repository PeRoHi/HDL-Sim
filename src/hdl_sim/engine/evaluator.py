"""Expression evaluation for the supported Verilog subset."""

from __future__ import annotations

from hdl_sim.core.events import EventQueue
from hdl_sim.engine.lvalue import read_lvalue
from hdl_sim.engine.nba import NBARegion
from hdl_sim.engine.nets import SimNet
from hdl_sim.parser.ast import (
    BinaryExpr,
    BitSelect,
    ConcatExpr,
    FunctionCall,
    FunctionDef,
    Expr,
    IdentRef,
    IntLiteral,
    Lvalue,
    PartSelect,
    UnaryExpr,
)


class EvaluationError(RuntimeError):
    pass


class ExpressionEvaluator:
    """Evaluate AST expressions against the current net values."""

    def __init__(
        self,
        nets: dict[str, SimNet],
        *,
        functions: dict[str, FunctionDef] | None = None,
        queue: EventQueue | None = None,
        nba: NBARegion | None = None,
        on_net_update=None,
    ) -> None:
        self._nets = nets
        self._functions = functions or {}
        self._queue = queue
        self._nba = nba
        self._on_net_update = on_net_update

    def eval(self, expr: Expr) -> int:
        if isinstance(expr, FunctionCall):
            args = tuple(self.eval(arg) for arg in expr.args)
            from hdl_sim.engine.functions import call_function

            func = self._functions[expr.name]
            return call_function(
                func,
                args,
                functions=self._functions,
                queue=self._queue or EventQueue(),
                nba=self._nba or NBARegion(self._nets, on_update=lambda *_: None),
                on_net_update=self._on_net_update or (lambda *_: None),
            )
        if isinstance(expr, IntLiteral):
            return expr.value
        if isinstance(expr, IdentRef):
            try:
                return self._nets[expr.name].value
            except KeyError as exc:
                msg = f"unknown identifier: {expr.name}"
                raise EvaluationError(msg) from exc
        if isinstance(expr, BitSelect):
            return read_lvalue(Lvalue(base=expr.signal, bit=expr.index), self._nets, self.eval)
        if isinstance(expr, PartSelect):
            return read_lvalue(
                Lvalue(base=expr.signal, msb=expr.msb, lsb=expr.lsb),
                self._nets,
                self.eval,
            )
        if isinstance(expr, UnaryExpr):
            value = self.eval(expr.operand)
            if expr.op == "~":
                net = self._operand_net(expr.operand)
                width = net.width if net is not None else 32
                mask = (1 << width) - 1
                return (~value) & mask
            if expr.op == "!":
                return 1 if value == 0 else 0
            if expr.op == "-":
                return -value
            if expr.op in {"uand", "uor", "uxor"}:
                return self._reduction(value, self._width_of(expr.operand), expr.op)
            if expr.op in {"posedge", "negedge"}:
                return value
            msg = f"unsupported unary operator: {expr.op}"
            raise EvaluationError(msg)
        if isinstance(expr, BinaryExpr):
            if expr.op == "?:":
                condition, branches = expr.left, expr.right
                cond_value = self.eval(condition)
                true_expr, false_expr = branches.left, branches.right
                return self.eval(true_expr if cond_value else false_expr)
            left = self.eval(expr.left)
            right = self.eval(expr.right)
            if expr.op == "||":
                return 1 if (left != 0 or right != 0) else 0
            if expr.op == "&&":
                return 1 if (left != 0 and right != 0) else 0
            if expr.op == "|":
                return left | right
            if expr.op == "&":
                return left & right
            if expr.op == "^":
                return left ^ right
            if expr.op == "+":
                return left + right
            if expr.op == "-":
                return left - right
            if expr.op == "*":
                return left * right
            if expr.op == "/":
                return 0 if right == 0 else left // right
            if expr.op == "%":
                return 0 if right == 0 else left % right
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
            if expr.op == "<<":
                return left << right
            if expr.op == ">>":
                return left >> right
            msg = f"unsupported binary operator: {expr.op}"
            raise EvaluationError(msg)
        if isinstance(expr, ConcatExpr):
            value = 0
            shift = 0
            for part in reversed(expr.parts):
                part_value = self.eval(part)
                value |= part_value << shift
                shift += self._width_of(part)
            return value
        msg = f"unsupported expression node: {type(expr).__name__}"
        raise EvaluationError(msg)

    def _operand_net(self, expr: Expr) -> SimNet | None:
        if isinstance(expr, IdentRef):
            return self._nets.get(expr.name)
        if isinstance(expr, BitSelect):
            return self._nets.get(expr.signal)
        if isinstance(expr, PartSelect):
            return self._nets.get(expr.signal)
        return None

    def _width_of(self, expr: Expr) -> int:
        net = self._operand_net(expr)
        if net is not None:
            return net.width
        if isinstance(expr, IntLiteral) and expr.width is not None:
            return expr.width
        return 32

    def _reduction(self, value: int, width: int, op: str) -> int:
        mask = (1 << width) - 1
        bits = value & mask
        if op == "uand":
            return 1 if bits == mask else 0
        if op == "uor":
            return 1 if bits != 0 else 0
        parity = 0
        while bits:
            parity ^= bits & 1
            bits >>= 1
        return parity
