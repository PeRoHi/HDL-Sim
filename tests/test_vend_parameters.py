"""Module parameters visible inside functions (vend FSM)."""

from pathlib import Path

from hdl_sim.engine.elaborator import elaborate
from hdl_sim.engine.simulator import Simulator
from hdl_sim.parser.loader import load_design_with_meta


def _vend_paths() -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    legacy = root / "examples" / "examples" / "新しいフォルダー"
    return [legacy / "vendtest.v", legacy / "vend.v"]


def test_vend_gate_simulates() -> None:
    loaded = load_design_with_meta(_vend_paths())
    elaborated = elaborate(loaded.design, top="stimulus")
    result = Simulator(elaborated).run(until=500, max_events=2000)
    assert result.events_processed > 0


def test_event_control_parses_negedge_wait() -> None:
    from hdl_sim.parser.parser import parse_module

    mod = parse_module(
        """
module m;
reg clock;
initial begin
  @(negedge clock);
  clock = 1;
end
endmodule
"""
    )
    init = mod.initial_blocks[0]
    assert len(init.body.statements) == 2
    ev = init.body.statements[0]
    from hdl_sim.parser.ast import EventControl, Block

    assert isinstance(ev, EventControl)
    assert len(ev.events) == 1
    assert isinstance(ev.body, Block)
    assert ev.body.statements == ()
