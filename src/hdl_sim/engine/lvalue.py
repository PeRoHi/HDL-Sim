"""Read and write Verilog lvalues including bit/part selects and memory words."""

from __future__ import annotations

from collections.abc import Callable

from hdl_sim.core.events import SimTime
from hdl_sim.engine.nets import SimNet
from hdl_sim.parser.ast import ConcatLvalue, Expr, Lvalue

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
            x_bit = x_mask & 1
            z_bit = z_mask & 1
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
        x_bit = x_mask & 1
        z_bit = z_mask & 1
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


def lvalue_width(lvalue: Lvalue, nets: dict[str, SimNet], eval_fn: EvalFn) -> int:
    net = _require_net(lvalue.base, nets)
    if lvalue.word is not None:
        if lvalue.bit is not None:
            return 1
        if lvalue.msb is not None and lvalue.lsb is not None:
            return abs(eval_fn(lvalue.msb) - eval_fn(lvalue.lsb)) + 1
        return net.width
    if lvalue.msb is not None and lvalue.lsb is not None:
        return abs(eval_fn(lvalue.msb) - eval_fn(lvalue.lsb)) + 1
    if lvalue.bit is not None:
        if net.is_memory:
            return net.width
        return 1
    return net.width


def _fit_rhs(state, total_width: int):
    from hdl_sim.engine.four_state import FourStateValue

    mask = (1 << total_width) - 1 if total_width else 0
    return FourStateValue(
        value=state.value & mask,
        width=total_width,
        x_mask=state.x_mask & mask,
        z_mask=state.z_mask & mask,
    )


def concat_part_states(concat: ConcatLvalue, state, nets: dict[str, SimNet], eval_fn: EvalFn):
    """Split an RHS vector into MSB-first concat lvalue parts (Verilog assignment)."""

    from hdl_sim.engine.four_state import FourStateValue

    widths = [lvalue_width(part, nets, eval_fn) for part in concat.parts]
    total = sum(widths)
    fitted = _fit_rhs(state, total)
    shift = total
    pieces: list[tuple[Lvalue, FourStateValue]] = []
    for part, width in zip(concat.parts, widths):
        shift -= width
        mask = (1 << width) - 1 if width else 0
        pieces.append(
            (
                part,
                FourStateValue(
                    value=(fitted.value >> shift) & mask,
                    width=width,
                    x_mask=(fitted.x_mask >> shift) & mask,
                    z_mask=(fitted.z_mask >> shift) & mask,
                ),
            )
        )
    return pieces


def write_concat_lvalue_logic(
    concat: ConcatLvalue,
    state,
    *,
    nets: dict[str, SimNet],
    eval_fn: EvalFn,
    time: SimTime,
    on_update,
) -> bool:
    changed = False
    for part, piece in concat_part_states(concat, state, nets, eval_fn):
        if write_lvalue_logic(
            part,
            piece,
            nets=nets,
            eval_fn=eval_fn,
            time=time,
            on_update=on_update,
        ):
            changed = True
    return changed


def write_assign_target_logic(
    target: Lvalue | ConcatLvalue,
    state,
    *,
    nets: dict[str, SimNet],
    eval_fn: EvalFn,
    time: SimTime,
    on_update,
) -> bool:
    if isinstance(target, ConcatLvalue):
        return write_concat_lvalue_logic(
            target,
            state,
            nets=nets,
            eval_fn=eval_fn,
            time=time,
            on_update=on_update,
        )
    return write_lvalue_logic(
        target,
        state,
        nets=nets,
        eval_fn=eval_fn,
        time=time,
        on_update=on_update,
    )
