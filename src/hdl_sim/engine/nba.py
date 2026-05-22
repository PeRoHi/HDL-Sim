"""Non-blocking assignment (NBA) region management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from hdl_sim.core.events import SimTime
from hdl_sim.engine.four_state import FourStateValue
from hdl_sim.engine.lvalue import EvalFn, write_lvalue, write_lvalue_logic
from hdl_sim.engine.nets import SimNet
from hdl_sim.parser.ast import Lvalue

NetUpdateCallback = Callable[[SimNet, SimTime], None]


def _global_net_name(base: str, locals: dict[str, SimNet] | None) -> str:
    if locals is not None and base in locals:
        return locals[base].name
    return base


@dataclass(frozen=True, slots=True)
class PendingState:
    value: int
    x_mask: int = 0
    z_mask: int = 0


@dataclass
class NBARegion:
    """Collect non-blocking updates and apply them at the end of a time step."""

    nets: dict[str, SimNet]
    on_update: NetUpdateCallback
    pending: dict[str, PendingState] = field(default_factory=dict)

    def schedule_state(self, target: str, state: FourStateValue) -> None:
        self.pending[target] = PendingState(
            value=state.value,
            x_mask=state.x_mask,
            z_mask=state.z_mask,
        )

    def schedule(self, target: str, value: int) -> None:
        net = self.nets[target]
        self.schedule_state(target, FourStateValue.from_int(value, width=net.width))

    def schedule_lvalue_logic(
        self,
        target: Lvalue,
        state: FourStateValue,
        *,
        eval_fn: EvalFn,
        locals: dict[str, SimNet] | None = None,
    ) -> None:
        if target.bit is None and target.msb is None and target.lsb is None:
            self.schedule_state(_global_net_name(target.base, locals), state)
            return

        from hdl_sim.engine.logic_eval import to_int

        self.schedule_lvalue(target, to_int(state), eval_fn=eval_fn, locals=locals)

    def schedule_lvalue(
        self,
        target: Lvalue,
        value: int,
        *,
        eval_fn: EvalFn,
        locals: dict[str, SimNet] | None = None,
    ) -> None:
        global_name = _global_net_name(target.base, locals)
        if target.bit is None and target.msb is None and target.lsb is None:
            self.schedule(global_name, value)
            return

        net = self.nets[global_name]
        pending = self.pending.get(global_name)
        current = pending.value if pending else net.value
        cur_x = pending.x_mask if pending else net.x_mask
        cur_z = pending.z_mask if pending else net.z_mask
        scratch = {
            target.base: SimNet(
                name=global_name,
                width=net.width,
                kind=net.kind,
                value=current,
                x_mask=cur_x,
                z_mask=cur_z,
            )
        }
        write_lvalue(
            target,
            value,
            nets=scratch,
            eval_fn=eval_fn,
            time=0,
            on_update=lambda *_args: None,
        )
        sn = scratch[target.base]
        self.pending[global_name] = PendingState(value=sn.value, x_mask=sn.x_mask, z_mask=sn.z_mask)

    def flush(self, time: SimTime) -> bool:
        if not self.pending:
            return False

        changed = False
        items = list(self.pending.items())
        self.pending.clear()
        for target, pending in items:
            net = self.nets[target]
            if net.update(
                pending.value,
                time=time,
                x_mask=pending.x_mask,
                z_mask=pending.z_mask,
            ):
                self.on_update(net, time)
                changed = True
        return changed

    def clear(self) -> None:
        self.pending.clear()
