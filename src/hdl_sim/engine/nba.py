"""Non-blocking assignment (NBA) region management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from hdl_sim.core.events import SimTime
from hdl_sim.engine.nets import SimNet

NetUpdateCallback = Callable[[SimNet, SimTime], None]


@dataclass
class NBARegion:
    """Collect non-blocking updates and apply them at the end of a time step."""

    nets: dict[str, SimNet]
    on_update: NetUpdateCallback
    pending: dict[str, int] = field(default_factory=dict)

    def schedule(self, target: str, value: int) -> None:
        self.pending[target] = value

    def flush(self, time: SimTime) -> bool:
        """Apply pending updates. Returns True when at least one net changed."""

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
