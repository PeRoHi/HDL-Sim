"""Four-state logic helpers for case statement matching."""

from __future__ import annotations

from dataclasses import dataclass

from hdl_sim.parser.ast import Expr, IntLiteral


@dataclass(frozen=True, slots=True)
class FourStateValue:
    """Bit vector with separate unknown (x) and high-impedance (z) masks."""

    value: int
    width: int
    x_mask: int = 0
    z_mask: int = 0

    def __post_init__(self) -> None:
        mask = (1 << self.width) - 1 if self.width else 0
        object.__setattr__(self, "value", self.value & mask)
        object.__setattr__(self, "x_mask", self.x_mask & mask)
        object.__setattr__(self, "z_mask", self.z_mask & mask)

    @classmethod
    def from_int(cls, value: int, *, width: int = 32) -> FourStateValue:
        mask = (1 << width) - 1
        return cls(value=value & mask, width=width)

    @classmethod
    def from_literal(cls, literal: IntLiteral) -> FourStateValue:
        width = literal.width or 32
        return cls(
            value=literal.value,
            width=width,
            x_mask=literal.x_mask,
            z_mask=literal.z_mask,
        )


def case_match(selector: FourStateValue, pattern: FourStateValue, style: str) -> bool:
    """Return whether ``pattern`` matches ``selector`` for the given case style."""

    width = max(selector.width, pattern.width)
    mask = (1 << width) - 1
    sel_v = selector.value & mask
    sel_x = selector.x_mask & mask
    pat_v = pattern.value & mask
    pat_x = pattern.x_mask & mask
    pat_z = pattern.z_mask & mask

    if style == "case":
        if (sel_x | pat_x) & mask:
            return False
        return sel_v == pat_v

    if style == "casex":
        care = (pat_x | pat_z) & mask
        compare_mask = (~care) & mask
        return (sel_v & compare_mask) == (pat_v & compare_mask)

    if style == "casez":
        care = pat_z & mask
        compare_mask = (~care) & mask
        return (sel_v & compare_mask) == (pat_v & compare_mask)

    return sel_v == pat_v


def eval_four_state(expr: Expr, eval_int: callable[[Expr], int]) -> FourStateValue:
    """Evaluate ``expr`` for use in case statements."""

    from hdl_sim.parser.ast import StringLiteral

    if isinstance(expr, IntLiteral):
        return FourStateValue.from_literal(expr)
    if isinstance(expr, StringLiteral):
        return FourStateValue.from_int(eval_int(expr))
    return FourStateValue.from_int(eval_int(expr))


def _align(a: FourStateValue, b: FourStateValue) -> tuple[int, int, int, int, int]:
    width = max(a.width, b.width)
    mask = (1 << width) - 1
    return (
        width,
        mask,
        a.value & mask,
        b.value & mask,
        (a.x_mask | a.z_mask) & mask,
    )


def bitwise_and(a: FourStateValue, b: FourStateValue) -> FourStateValue:
    width, mask, av, bv, _ = _align(a, b)
    ax, az = a.x_mask & mask, a.z_mask & mask
    bx, bz = b.x_mask & mask, b.z_mask & mask
    result_x = (ax | bx | az | bz) & mask
    return FourStateValue(value=av & bv, width=width, x_mask=result_x, z_mask=(az | bz) & mask)


def bitwise_or(a: FourStateValue, b: FourStateValue) -> FourStateValue:
    width, mask, av, bv, _ = _align(a, b)
    ax, az = a.x_mask & mask, a.z_mask & mask
    bx, bz = b.x_mask & mask, b.z_mask & mask
    known_mask = (~(ax | bx | az | bz)) & mask
    value = (av | bv) & known_mask
    result_x = ((ax | bx) & ~(av | bv)) & mask
    return FourStateValue(value=value, width=width, x_mask=result_x | ((ax | bx) & mask), z_mask=(az | bz) & mask)


def bitwise_xor(a: FourStateValue, b: FourStateValue) -> FourStateValue:
    width, mask, av, bv, _ = _align(a, b)
    ax, az = a.x_mask & mask, a.z_mask & mask
    bx, bz = b.x_mask & mask, b.z_mask & mask
    if (ax | bx | az | bz) & mask:
        return FourStateValue(value=0, width=width, x_mask=mask, z_mask=0)
    return FourStateValue(value=(av ^ bv) & mask, width=width)


def bitwise_not(a: FourStateValue) -> FourStateValue:
    mask = (1 << a.width) - 1
    known = (~(a.x_mask | a.z_mask)) & mask
    return FourStateValue(
        value=(~a.value) & known,
        width=a.width,
        x_mask=a.x_mask | (a.x_mask & ~known),
        z_mask=a.z_mask,
    )


def to_int(value: FourStateValue) -> int:
    return value.value
