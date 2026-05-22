"""Non-blocking assignment (NBA) region management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from hdl_sim.core.events import SimTime
from hdl_sim.engine.lvalue import EvalFn
from hdl_sim.engine.lvalue import write_lvalue
from hdl_sim.engine.nets import SimNet
from hdl_sim.parser.ast import Lvalue

NetUpdateCallback = Callable[[SimNet, SimTime], None]


@dataclass
class NBARegion:
    """Collect non-blocking updates and apply them at the end of a time step."""

    nets: dict[str, SimNet]
    on_update: NetUpdateCallback
    pending: dict[str, int] = field(default_factory=dict)

    def schedule(self, target: str, value: int) -> None:
        self.pending[target] = value

    def schedule_lvalue(
        self,
        target: Lvalue,
        value: int,
        *,
        eval_fn: EvalFn,
    ) -> None:
        if target.bit is None and target.msb is None and target.lsb is None:
            self.schedule(target.base, value)
            return

        net = self.nets[target.base]
        current = net.value if target.base not in self.pending else self.pending[target.base]
        scratch = {
            target.base: SimNet(name=target.base, width=net.width, kind=net.kind, value=current)
        }
        write_lvalue(
            target,
            value,
            nets=scratch,
            eval_fn=eval_fn,
            time=0,
            on_update=lambda *_args: None,
        )
        self.pending[target.base] = scratch[target.base].value

    def flush(self, time: SimTime) -> bool:
        if not self.pending:
            return False

        changed = False
        items = list(self.pending.items())
        self.pending.clear()
        for target, value in items:
            net = self.nets[target]
            if net.update(value, time=time):
                self.on_update(net, time)
                changed = True
        return changed

    def clear(self) -> None:
        self.pending.clear()
