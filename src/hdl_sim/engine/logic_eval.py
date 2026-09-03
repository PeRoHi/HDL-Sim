"""Full four-state expression evaluation."""

from __future__ import annotations

from hdl_sim.engine.four_state import (
    FourStateValue,
    bitwise_and,
    bitwise_not,
    bitwise_or,
    bitwise_xor,
)
from hdl_sim.parser.ast import (
    BinaryExpr,
    BitSelect,
    ConcatExpr,
    DeclKind,
    ReplicationExpr,
    Expr,
    IdentRef,
    IntLiteral,
    PartSelect,
    RealLiteral,
    StringLiteral,
    UnaryExpr,
)


def to_int(value: FourStateValue) -> int:
    return value.value


def has_unknown(value: FourStateValue) -> bool:
    mask = (1 << value.width) - 1 if value.width else 0
    return bool((value.x_mask | value.z_mask) & mask)


def eval_logic(expr: Expr, eval_int, nets: dict) -> FourStateValue:
    """Evaluate an expression into a four-state bit vector."""

    if isinstance(expr, IntLiteral):
        return FourStateValue.from_literal(expr)
    if isinstance(expr, RealLiteral):
        return FourStateValue.from_int(int(expr.value), width=32)
    if isinstance(expr, StringLiteral):
        value = 0
        for ch in expr.value.encode("utf-8"):
            value = (value << 8) | ch
        width = max(32, value.bit_length())
        return FourStateValue(value=value, width=width)
    if isinstance(expr, IdentRef):
        net = nets.get(expr.name)
        if net is not None:
            if net.kind is DeclKind.REAL:
                return FourStateValue.from_int(int(net.real_value), width=32)
            return FourStateValue(
                value=net.value,
                width=net.width,
                x_mask=getattr(net, "x_mask", 0),
                z_mask=getattr(net, "z_mask", 0),
            )
        value = eval_int(expr)
        width = max(1, value.bit_length())
        return FourStateValue(value=value, width=width)
    if isinstance(expr, BitSelect):
        from hdl_sim.engine.lvalue import read_lvalue
        from hdl_sim.parser.ast import Lvalue

        value = read_lvalue(
            Lvalue(base=expr.signal, word=expr.word, bit=expr.index),
            nets,
            eval_int,
        )
        from hdl_sim.engine.signed_ops import operand_width

        net = nets.get(expr.signal)
        if expr.word is not None:
            # mem[word][bit] — bit select within one memory word
            width = 1
        elif net is not None and net.is_memory:
            # mem[index] — unpacked memory word (full word width)
            width = net.width
        elif net is not None:
            width = 1
        else:
            width = operand_width(expr, nets, default=1)
        return FourStateValue.from_int(value, width=width)
    if isinstance(expr, PartSelect):
        from hdl_sim.engine.lvalue import read_lvalue
        from hdl_sim.engine.signed_ops import operand_width
        from hdl_sim.parser.ast import Lvalue

        value = read_lvalue(
            Lvalue(base=expr.signal, word=expr.word, msb=expr.msb, lsb=expr.lsb),
            nets,
            eval_int,
        )
        width = abs(eval_int(expr.msb) - eval_int(expr.lsb)) + 1
        return FourStateValue.from_int(value, width=width)
    if isinstance(expr, UnaryExpr):
        if expr.op in {"$signed", "$unsigned"}:
            return eval_logic(expr.operand, eval_int, nets)
        operand = eval_logic(expr.operand, eval_int, nets)
        if expr.op == "~":
            return bitwise_not(operand)
        value = to_int(operand)
        if expr.op == "!":
            known = not has_unknown(operand)
            return FourStateValue(value=1 if known and value == 0 else 0, width=1, x_mask=0 if known else 1)
        if expr.op == "-":
            if has_unknown(operand):
                return FourStateValue(value=0, width=operand.width, x_mask=(1 << operand.width) - 1)
            return FourStateValue.from_int(-value, width=operand.width)
        if expr.op in {"uand", "uor", "uxor"}:
            mask = (1 << operand.width) - 1
            bits = operand.value & mask
            if has_unknown(operand):
                return FourStateValue(value=0, width=1, x_mask=1)
            if expr.op == "uand":
                return FourStateValue(value=1 if bits == mask else 0, width=1)
            if expr.op == "uor":
                return FourStateValue(value=1 if bits else 0, width=1)
            parity = 0
            while bits:
                parity ^= bits & 1
                bits >>= 1
            return FourStateValue(value=parity, width=1)
        msg = f"unsupported unary operator: {expr.op}"
        raise ValueError(msg)
    if isinstance(expr, BinaryExpr):
        if expr.op == "?:":
            condition, branches = expr.left, expr.right
            cond = eval_logic(condition, eval_int, nets)
            if has_unknown(cond):
                return FourStateValue(value=0, width=32, x_mask=1)
            branch = branches.left if cond.value else branches.right
            return eval_logic(branch, eval_int, nets)
        left = eval_logic(expr.left, eval_int, nets)
        right = eval_logic(expr.right, eval_int, nets)
        if expr.op == "&":
            return bitwise_and(left, right)
        if expr.op == "|":
            return bitwise_or(left, right)
        if expr.op == "^":
            return bitwise_xor(left, right)
        if expr.op in {"&&", "||"}:
            lv, rv = to_int(left), to_int(right)
            if has_unknown(left) or has_unknown(right):
                return FourStateValue(value=0, width=1, x_mask=1)
            if expr.op == "&&":
                return FourStateValue(value=1 if lv and rv else 0, width=1)
            return FourStateValue(value=1 if lv or rv else 0, width=1)
        if has_unknown(left) or has_unknown(right):
            width = max(left.width, right.width)
            return FourStateValue(value=0, width=width, x_mask=(1 << width) - 1)
        lv, rv = to_int(left), to_int(right)
        width = max(left.width, right.width)
        mask = (1 << width) - 1
        if expr.op in {"+", "-", "*", "/"}:
            from hdl_sim.engine.signed_ops import prepare_signed_arith_operands

            lv, rv = prepare_signed_arith_operands(expr.left, expr.right, lv, rv, nets)
            if expr.op == "+":
                result = lv + rv
            elif expr.op == "-":
                result = lv - rv
            elif expr.op == "*":
                result = lv * rv
            else:
                result = 0 if rv == 0 else int(lv / rv)
            return FourStateValue.from_int(result & mask, width=width)
        if expr.op == "<<":
            return FourStateValue.from_int((lv << rv) & mask, width=width)
        if expr.op in {">>", ">>>"}:
            from hdl_sim.engine.signed_ops import (
                expr_is_signed,
                operand_width,
                shift_right_arithmetic,
                shift_right_logical,
            )

            lwidth = operand_width(expr.left, nets)
            if expr_is_signed(expr.left, nets):
                result = shift_right_arithmetic(lv, rv, lwidth)
            else:
                result = shift_right_logical(lv, rv, lwidth)
            return FourStateValue.from_int(result, width=lwidth)
        if expr.op in {"==", "!=", "<", "<=", ">", ">="}:
            from hdl_sim.engine.signed_ops import compare_signed, expr_is_signed, operand_width

            lwidth = operand_width(expr.left, nets)
            rwidth = operand_width(expr.right, nets)
            if expr_is_signed(expr.left, nets) or expr_is_signed(expr.right, nets):
                ok = compare_signed(lv, rv, lwidth, rwidth, expr.op)
                return FourStateValue(value=ok, width=1)
            if expr.op == "==":
                ok = lv == rv
            elif expr.op == "!=":
                ok = lv != rv
            elif expr.op == "<":
                ok = lv < rv
            elif expr.op == "<=":
                ok = lv <= rv
            elif expr.op == ">":
                ok = lv > rv
            else:
                ok = lv >= rv
            return FourStateValue(value=1 if ok else 0, width=1)
        msg = f"unsupported binary operator: {expr.op}"
        raise ValueError(msg)
    if isinstance(expr, ReplicationExpr):
        count = eval_int(expr.count)
        inner = eval_logic(expr.expr, eval_int, nets)
        total_width = inner.width * count
        value = x_mask = z_mask = 0
        inner_mask = (1 << inner.width) - 1 if inner.width else 0
        for index in range(count):
            shift = index * inner.width
            value |= (inner.value & inner_mask) << shift
            x_mask |= (inner.x_mask & inner_mask) << shift
            z_mask |= (inner.z_mask & inner_mask) << shift
        mask = (1 << total_width) - 1 if total_width else 0
        return FourStateValue(
            value=value & mask,
            width=total_width,
            x_mask=x_mask & mask,
            z_mask=z_mask & mask,
        )
    if isinstance(expr, ConcatExpr):
        parts = [eval_logic(part, eval_int, nets) for part in expr.parts]
        total_width = sum(part.width for part in parts)
        value = x_mask = z_mask = 0
        shift = 0
        for part in reversed(parts):
            value |= part.value << shift
            x_mask |= part.x_mask << shift
            z_mask |= part.z_mask << shift
            shift += part.width
        mask = (1 << total_width) - 1
        return FourStateValue(value=value & mask, width=total_width, x_mask=x_mask & mask, z_mask=z_mask & mask)
    from hdl_sim.parser.ast import FunctionCall

    if isinstance(expr, FunctionCall):
        return FourStateValue.from_int(eval_int(expr), width=32)
    return FourStateValue.from_int(eval_int(expr), width=32)
