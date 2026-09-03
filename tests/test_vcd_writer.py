"""VCD writer edge cases."""

from hdl_sim.core.events import SimTime
from hdl_sim.engine.nets import DeclKind, SimNet
from hdl_sim.vcd.writer import VCDWriter


def test_change_ignores_nets_not_in_dump_list() -> None:
    """Function-local return regs (e.g. dec) must not crash waveform capture."""

    nets = {"ck": SimNet(name="ck", width=1, kind=DeclKind.REG)}
    writer = VCDWriter("tb", nets)
    local = SimNet(name="dec", width=7, kind=DeclKind.REG, value=3)
    writer.change(local, SimTime(0))
    assert writer._changes == []
