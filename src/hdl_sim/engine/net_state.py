"""Apply four-state values to simulation nets."""

from __future__ import annotations

from hdl_sim.core.events import SimTime
from hdl_sim.engine.four_state import FourStateValue
from hdl_sim.engine.nets import SimNet

NetUpdateCallback = __import__("collections.abc", fromlist=["Callable"]).Callable[[SimNet, SimTime], None]


def apply_four_state(
    net: SimNet,
    state: FourStateValue,
    *,
    time: SimTime,
    on_update: NetUpdateCallback,
) -> bool:
    """Update ``net`` from a four-state value and notify on change."""

    if net.update(
        state.value,
        time=time,
        x_mask=state.x_mask,
        z_mask=state.z_mask,
    ):
        on_update(net, time)
        return True
    return False
