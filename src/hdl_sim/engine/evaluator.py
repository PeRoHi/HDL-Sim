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
    TaskDef,
    Expr,
    IdentRef,
    IntLiteral,
    Lvalue,
    PartSelect,
    StringLiteral,
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
        tasks: dict[str, TaskDef] | None = None,
        queue: EventQueue | None = None,
        nba: NBARegion | None = None,
        on_net_update=None,
        caller_nets: dict[str, SimNet] | None = None,
        params: dict[str, int] | None = None,
        global_nets: dict[str, SimNet] | None = None,
        sim_time: int | None = None,
    ) -> None:
        self._nets = nets
        self._params = params or {}
        self._global_nets = global_nets or {}
        self._sim_time = sim_time
        self._functions = functions or {}
        self._tasks = tasks or {}
        self._queue = queue
        self._nba = nba
        self._on_net_update = on_net_update
        self._caller_nets = caller_nets or nets

    def call_task(self, name: str, args: tuple) -> None:
        from hdl_sim.engine.tasks import call_task

        task = self._tasks[name]
        call_task(
            task,
            args,
            caller_nets=self._caller_nets,
            queue=self._queue or EventQueue(),
            nba=self._nba or NBARegion(self._nets, on_update=lambda *_: None),
            on_net_update=self._on_net_update or (lambda *_: None),
        )

    def eval_logic(self, expr: Expr):
        from hdl_sim.engine.logic_eval import eval_logic

        return eval_logic(expr, self.eval, self._nets)

    def eval_four_state(self, expr: Expr):
        from hdl_sim.engine.four_state import (
            FourStateValue,
            bitwise_and,
            bitwise_not,
            bitwise_or,
            bitwise_xor,
            to_int,
        )
        from hdl_sim.parser.ast import IntLiteral

        if isinstance(expr, IntLiteral):
            return FourStateValue.from_literal(expr)
        if isinstance(expr, IdentRef):
            return FourStateValue.from_int(self._nets[expr.name].value, width=self._nets[expr.name].width)
        if isinstance(expr, UnaryExpr) and expr.op == "~":
            return bitwise_not(self.eval_four_state(expr.operand))
        if isinstance(expr, BinaryExpr) and expr.op in {"&", "|", "^"}:
            left = self.eval_four_state(expr.left)
            right = self.eval_four_state(expr.right)
            if expr.op == "&":
                return bitwise_and(left, right)
            if expr.op == "|":
                return bitwise_or(left, right)
            return bitwise_xor(left, right)
        return FourStateValue.from_int(self.eval(expr))

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
                params=self._params,
            )
        if isinstance(expr, IntLiteral):
            return expr.value
        if isinstance(expr, StringLiteral):
            value = 0
            for ch in expr.value.encode("utf-8"):
                value = (value << 8) | ch
            return value
        if isinstance(expr, IdentRef):
            if expr.name in ("$stime", "$time") and self._sim_time is not None:
                return self._sim_time
            if expr.name in self._params:
                return self._params[expr.name]
            if expr.name in self._nets:
                return self._nets[expr.name].value
            if expr.name in self._global_nets:
                return self._global_nets[expr.name].value
            msg = f"unknown identifier: {expr.name}"
            raise EvaluationError(msg)
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
            if expr.op in {"&", "|", "^"} and self._expr_has_unknown(expr):
                from hdl_sim.engine.four_state import to_int

                return to_int(self.eval_four_state(expr))
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
            if expr.op in {"==", "!=", "<", "<=", ">", ">="}:
                from hdl_sim.engine.signed_ops import compare_signed, expr_is_signed, operand_width

                lwidth = operand_width(expr.left, self._nets)
                rwidth = operand_width(expr.right, self._nets)
                if expr_is_signed(expr.left, self._nets) or expr_is_signed(expr.right, self._nets):
                    return compare_signed(left, right, lwidth, rwidth, expr.op)
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
                return 1 if left >= right else 0
            if expr.op == "<<":
                return left << right
            if expr.op == ">>":
                from hdl_sim.engine.signed_ops import (
                    expr_is_signed,
                    operand_width,
                    shift_right_arithmetic,
                    shift_right_logical,
                )

                width = operand_width(expr.left, self._nets)
                if expr_is_signed(expr.left, self._nets):
                    return shift_right_arithmetic(left, right, width)
                return shift_right_logical(left, right, width)
            if expr.op == ">>>":
                from hdl_sim.engine.signed_ops import (
                    expr_is_signed,
                    operand_width,
                    shift_right_arithmetic,
                    shift_right_logical,
                )

                width = operand_width(expr.left, self._nets)
                if expr_is_signed(expr.left, self._nets):
                    return shift_right_arithmetic(left, right, width)
                return shift_right_logical(left, right, width)
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

    def _expr_has_unknown(self, expr: Expr) -> bool:
        from hdl_sim.parser.ast import BinaryExpr, IntLiteral, UnaryExpr

        if isinstance(expr, IntLiteral):
            return bool(expr.x_mask or expr.z_mask)
        if isinstance(expr, BinaryExpr):
            return self._expr_has_unknown(expr.left) or self._expr_has_unknown(expr.right)
        if isinstance(expr, UnaryExpr):
            return self._expr_has_unknown(expr.operand)
        return False

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
