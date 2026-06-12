"""Signed value helpers and Verilog shift semantics."""

from __future__ import annotations

from hdl_sim.engine.nets import SimNet
from hdl_sim.parser.ast import (
    BinaryExpr,
    BitSelect,
    Expr,
    IdentRef,
    IntLiteral,
    PartSelect,
    UnaryExpr,
)


def mask_width(width: int) -> int:
    return (1 << width) - 1 if width > 0 else 0


def to_signed(value: int, width: int) -> int:
    mask = mask_width(width)
    value &= mask
    if width <= 0:
        return value
    if value & (1 << (width - 1)):
        return value - (1 << width)
    return value


def shift_right_logical(value: int, amount: int, width: int) -> int:
    if amount <= 0:
        return value & mask_width(width)
    if amount >= width:
        return 0
    return (value & mask_width(width)) >> amount


def shift_right_arithmetic(value: int, amount: int, width: int) -> int:
    if amount <= 0:
        return value & mask_width(width)
    if amount >= width:
        return mask_width(width) if to_signed(value, width) < 0 else 0
    signed = to_signed(value, width)
    return signed >> amount & mask_width(width)


def sign_extend(value: int, from_width: int, to_width: int) -> int:
    if to_width <= from_width:
        return value & mask_width(from_width)
    value &= mask_width(from_width)
    if from_width > 0 and value & (1 << (from_width - 1)):
        high_fill = mask_width(to_width) ^ mask_width(from_width)
        return value | high_fill
    return value


def compare_signed(left: int, right: int, left_width: int, right_width: int, op: str) -> int:
    width = max(left_width, right_width)
    left_ext = sign_extend(left, left_width, width)
    right_ext = sign_extend(right, right_width, width)
    sl = to_signed(left_ext, width)
    sr = to_signed(right_ext, width)
    if op == "==":
        ok = sl == sr
    elif op == "!=":
        ok = sl != sr
    elif op == "<":
        ok = sl < sr
    elif op == "<=":
        ok = sl <= sr
    elif op == ">":
        ok = sl > sr
    else:
        ok = sl >= sr
    return 1 if ok else 0


def expr_is_signed(expr: Expr, nets: dict[str, SimNet]) -> bool:
    if isinstance(expr, IdentRef):
        net = nets.get(expr.name)
        return bool(net and net.is_signed)
    if isinstance(expr, BitSelect):
        net = nets.get(expr.signal)
        return bool(net and net.is_signed)
    if isinstance(expr, PartSelect):
        net = nets.get(expr.signal)
        return bool(net and net.is_signed)
    if isinstance(expr, UnaryExpr):
        if expr.op == "$signed":
            return True
        if expr.op == "$unsigned":
            return False
        return expr_is_signed(expr.operand, nets)
    if isinstance(expr, BinaryExpr):
        if expr.op == "?:":
            return expr_is_signed(expr.right.left, nets) or expr_is_signed(expr.right.right, nets)
        return expr_is_signed(expr.left, nets) or expr_is_signed(expr.right, nets)
    if isinstance(expr, IntLiteral):
        return False
    return False


def extend_state_for_assign(state, expr: Expr, nets: dict[str, SimNet], target_width: int):
    """Sign-extend an evaluated rvalue to the assignment target width.

    `$signed(x)` や signed 宣言された信号を、より広い変数へ代入するとき
    MSB で上位ビットを埋める（Verilog の符号拡張）。unsigned はゼロ拡張のまま。
    """

    from hdl_sim.engine.four_state import FourStateValue

    if target_width <= state.width or not expr_is_signed(expr, nets):
        return state
    msb = 1 << (state.width - 1)
    high_fill = mask_width(target_width) ^ mask_width(state.width)
    value = state.value
    x_mask = state.x_mask
    z_mask = state.z_mask
    if x_mask & msb:
        x_mask |= high_fill
    elif z_mask & msb:
        z_mask |= high_fill
    elif value & msb:
        value |= high_fill
    return FourStateValue(value=value, width=target_width, x_mask=x_mask, z_mask=z_mask)


def extend_int_for_assign(
    value: int,
    expr: Expr,
    nets: dict[str, SimNet],
    target_width: int,
) -> int:
    """Integer-path variant of :func:`extend_state_for_assign`."""

    width = operand_width(expr, nets)
    if target_width <= width or not expr_is_signed(expr, nets):
        return value
    return sign_extend(value, width, target_width)


def prepare_signed_arith_operands(
    left_expr: Expr,
    right_expr: Expr,
    left: int,
    right: int,
    nets: dict[str, SimNet],
) -> tuple[int, int]:
    from hdl_sim.parser.ast import DeclKind, IdentRef

    lwidth = operand_width(left_expr, nets)
    rwidth = operand_width(right_expr, nets)
    width = max(lwidth, rwidth)
    for expr in (left_expr, right_expr):
        if isinstance(expr, IdentRef):
            net = nets.get(expr.name)
            if net is not None and net.kind is DeclKind.INTEGER:
                width = max(width, net.width)
    if expr_is_signed(left_expr, nets) or expr_is_signed(right_expr, nets):
        if expr_is_signed(left_expr, nets):
            left = sign_extend(left, lwidth, width)
        if expr_is_signed(right_expr, nets):
            right = sign_extend(right, rwidth, width)
    return left, right


def operand_width(expr: Expr, nets: dict[str, SimNet], default: int = 32) -> int:
    if isinstance(expr, IdentRef):
        net = nets.get(expr.name)
        return net.width if net is not None else default
    if isinstance(expr, BitSelect):
        net = nets.get(expr.signal)
        if expr.word is not None:
            return 1
        return net.width if net is not None else 1
    if isinstance(expr, PartSelect):
        net = nets.get(expr.signal)
        if expr.word is not None:
            msb_w = operand_width(expr.msb, nets, default)
            lsb_w = operand_width(expr.lsb, nets, default)
            return max(msb_w, lsb_w)
        return net.width if net is not None else default
    if isinstance(expr, IntLiteral) and expr.width is not None:
        return expr.width
    if isinstance(expr, UnaryExpr):
        if expr.op in {"$signed", "$unsigned"}:
            return operand_width(expr.operand, nets, default)
        return operand_width(expr.operand, nets, default)
    if isinstance(expr, BinaryExpr):
        return max(operand_width(expr.left, nets, default), operand_width(expr.right, nets, default))
    return default
