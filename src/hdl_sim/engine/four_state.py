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

    if isinstance(expr, IntLiteral):
        return FourStateValue.from_literal(expr)
    return FourStateValue.from_int(eval_int(expr))
