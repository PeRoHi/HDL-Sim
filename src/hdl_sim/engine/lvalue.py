"""Read and write Verilog lvalues including bit/part selects."""

from __future__ import annotations

from collections.abc import Callable

from hdl_sim.core.events import SimTime
from hdl_sim.engine.nets import SimNet
from hdl_sim.parser.ast import Expr, Lvalue

EvalFn = Callable[[Expr], int]


def read_lvalue(lvalue: Lvalue, nets: dict[str, SimNet], eval_fn: EvalFn) -> int:
    net = _require_net(lvalue.base, nets)
    if lvalue.bit is not None:
        index = eval_fn(lvalue.bit)
        return net.bit(index)
    if lvalue.msb is not None and lvalue.lsb is not None:
        msb = eval_fn(lvalue.msb)
        lsb = eval_fn(lvalue.lsb)
        return _extract_part(net.value, msb, lsb)
    return net.value


def write_lvalue(
    lvalue: Lvalue,
    value: int,
    *,
    nets: dict[str, SimNet],
    eval_fn: EvalFn,
    time: SimTime,
    on_update,
) -> bool:
    net = _require_net(lvalue.base, nets)
    if lvalue.bit is not None:
        index = eval_fn(lvalue.bit)
        bit_value = value & 1
        next_value = (net.value & ~(1 << index)) | (bit_value << index)
        if net.update(next_value, time=time):
            on_update(net, time)
            return True
        return False
    if lvalue.msb is not None and lvalue.lsb is not None:
        msb = eval_fn(lvalue.msb)
        lsb = eval_fn(lvalue.lsb)
        next_value = _insert_part(net.value, msb, lsb, value, net.width)
        if net.update(next_value, time=time):
            on_update(net, time)
            return True
        return False
    if net.update(value, time=time):
        on_update(net, time)
        return True
    return False


def _require_net(name: str, nets: dict[str, SimNet]) -> SimNet:
    try:
        return nets[name]
    except KeyError as exc:
        msg = f"unknown net: {name}"
        raise RuntimeError(msg) from exc


def _extract_part(value: int, msb: int, lsb: int) -> int:
    if msb < lsb:
        msb, lsb = lsb, msb
    width = msb - lsb + 1
    return (value >> lsb) & ((1 << width) - 1)


def _insert_part(value: int, msb: int, lsb: int, part: int, total_width: int) -> int:
    if msb < lsb:
        msb, lsb = lsb, msb
    width = msb - lsb + 1
    mask = ((1 << width) - 1) << lsb
    total_mask = (1 << total_width) - 1
    return ((value & ~mask) | ((part << lsb) & mask)) & total_mask
