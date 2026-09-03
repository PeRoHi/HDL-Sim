"""Read and write Verilog lvalues including bit/part selects and memory words."""

from __future__ import annotations

from collections.abc import Callable

from hdl_sim.core.events import SimTime
from hdl_sim.engine.nets import SimNet
from hdl_sim.parser.ast import Expr, Lvalue

EvalFn = Callable[[Expr], int]


def read_lvalue(lvalue: Lvalue, nets: dict[str, SimNet], eval_fn: EvalFn) -> int:
    net = _require_net(lvalue.base, nets)
    if lvalue.word is not None:
        word_index = eval_fn(lvalue.word)
        word_value = net.read_word(word_index)
        if lvalue.bit is not None:
            bit_index = eval_fn(lvalue.bit)
            return (word_value >> bit_index) & 1
        if lvalue.msb is not None and lvalue.lsb is not None:
            msb = eval_fn(lvalue.msb)
            lsb = eval_fn(lvalue.lsb)
            return _extract_part(word_value, msb, lsb)
        return word_value
    if lvalue.bit is not None:
        index = eval_fn(lvalue.bit)
        if net.is_memory:
            return net.read_word(index)
        return net.bit(index)
    if lvalue.msb is not None and lvalue.lsb is not None:
        msb = eval_fn(lvalue.msb)
        lsb = eval_fn(lvalue.lsb)
        base_value = net.read_word(0) if net.is_memory else net.value
        return _extract_part(base_value, msb, lsb)
    return net.value if not net.is_memory else net.read_word(0)


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
    if lvalue.word is not None:
        word_index = eval_fn(lvalue.word)
        current = net.read_word(word_index)
        if lvalue.bit is not None:
            bit_index = eval_fn(lvalue.bit)
            bit_value = value & 1
            next_value = (current & ~(1 << bit_index)) | (bit_value << bit_index)
        elif lvalue.msb is not None and lvalue.lsb is not None:
            msb = eval_fn(lvalue.msb)
            lsb = eval_fn(lvalue.lsb)
            next_value = _insert_part(current, msb, lsb, value, net.width)
        else:
            next_value = value
        if net.update_word(word_index, next_value, time=time):
            on_update(net, time)
            return True
        return False
    if lvalue.bit is not None:
        index = eval_fn(lvalue.bit)
        if net.is_memory:
            if net.update_word(index, value, time=time):
                on_update(net, time)
                return True
            return False
        bit_value = value & 1
        next_value = (net.value & ~(1 << index)) | (bit_value << index)
        if net.update(next_value, time=time):
            on_update(net, time)
            return True
        return False
    if lvalue.msb is not None and lvalue.lsb is not None:
        msb = eval_fn(lvalue.msb)
        lsb = eval_fn(lvalue.lsb)
        base_value = net.read_word(0) if net.is_memory else net.value
        next_value = _insert_part(base_value, msb, lsb, value, net.width)
        if net.is_memory:
            if net.update_word(0, next_value, time=time):
                on_update(net, time)
                return True
            return False
        if net.update(next_value, time=time):
            on_update(net, time)
            return True
        return False
    if net.is_memory:
        if net.update_word(0, value, time=time):
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


def write_lvalue_logic(
    lvalue: Lvalue,
    state,
    *,
    nets: dict[str, SimNet],
    eval_fn: EvalFn,
    time: SimTime,
    on_update,
) -> bool:
    from hdl_sim.engine.logic_eval import to_int

    value = to_int(state)
    x_mask = state.x_mask
    z_mask = state.z_mask
    net = _require_net(lvalue.base, nets)
    if lvalue.word is not None:
        word_index = eval_fn(lvalue.word)
        current = net.read_word(word_index)
        if lvalue.bit is not None:
            bit_index = eval_fn(lvalue.bit)
            bit_value = value & 1
            x_bit = (x_mask >> bit_index) & 1
            z_bit = (z_mask >> bit_index) & 1
            next_value = (current & ~(1 << bit_index)) | (bit_value << bit_index)
            next_x = (net.memory_x_mask[word_index] & ~(1 << bit_index)) | (x_bit << bit_index)
            next_z = (net.memory_z_mask[word_index] & ~(1 << bit_index)) | (z_bit << bit_index)
            if net.update_word(word_index, next_value, time=time, x_mask=next_x, z_mask=next_z):
                on_update(net, time)
                return True
            return False
        if lvalue.msb is not None and lvalue.lsb is not None:
            msb = eval_fn(lvalue.msb)
            lsb = eval_fn(lvalue.lsb)
            next_value = _insert_part(current, msb, lsb, value, net.width)
            if net.update_word(word_index, next_value, time=time):
                on_update(net, time)
                return True
            return False
        if net.update_word(word_index, value, time=time, x_mask=x_mask, z_mask=z_mask):
            on_update(net, time)
            return True
        return False
    if lvalue.bit is not None:
        index = eval_fn(lvalue.bit)
        if net.is_memory:
            if net.update_word(index, value, time=time, x_mask=x_mask, z_mask=z_mask):
                on_update(net, time)
                return True
            return False
        bit_value = value & 1
        x_bit = (x_mask >> index) & 1
        z_bit = (z_mask >> index) & 1
        next_value = (net.value & ~(1 << index)) | (bit_value << index)
        next_x = (net.x_mask & ~(1 << index)) | (x_bit << index)
        next_z = (net.z_mask & ~(1 << index)) | (z_bit << index)
        if (
            next_value == net.value
            and next_x == net.x_mask
            and next_z == net.z_mask
        ):
            return False
        net.previous = net.value
        net.value = next_value
        net.x_mask = next_x
        net.z_mask = next_z
        on_update(net, time)
        return True
    if lvalue.msb is not None and lvalue.lsb is not None:
        msb = eval_fn(lvalue.msb)
        lsb = eval_fn(lvalue.lsb)
        base_value = net.read_word(0) if net.is_memory else net.value
        next_value = _insert_part(base_value, msb, lsb, value, net.width)
        if net.is_memory:
            if net.update_word(0, next_value, time=time):
                on_update(net, time)
                return True
            return False
        if net.update(next_value, time=time, x_mask=net.x_mask, z_mask=net.z_mask):
            on_update(net, time)
            return True
        return False
    if net.is_memory:
        changed = net.update_word(0, value, time=time, x_mask=x_mask, z_mask=z_mask)
        if changed:
            on_update(net, time)
        return changed
    changed = net.update(value, time=time, x_mask=x_mask, z_mask=z_mask)
    if changed:
        on_update(net, time)
    return changed
