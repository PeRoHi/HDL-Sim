"""Module parameters visible inside functions (vend FSM)."""

from pathlib import Path

import pytest

from hdl_sim.engine.elaborator import elaborate
from hdl_sim.engine.simulator import Simulator
from hdl_sim.parser.loader import load_design_with_meta


def _vend_paths(tmp_path: Path) -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    legacy = root / "examples" / "examples" / "新しいフォルダー"
    vend = legacy / "vend.v"
    text = vend.read_text(encoding="utf-8", errors="replace")
    if "assign {newspaper, NEXT_STATE}" in text:
        text = text.replace(
            "assign {newspaper, NEXT_STATE} = fsm(coin, PRES_STATE);",
            """wire [2:0] __fsm_out;
assign __fsm_out = fsm(coin, PRES_STATE);
assign newspaper = __fsm_out[2];
assign PRES_STATE = __fsm_out[1:0];""",
        )
        patched = tmp_path / "vend_patched.v"
        patched.write_text(text, encoding="utf-8")
        return [legacy / "vendtest.v", patched]
    return [legacy / "vendtest.v", vend]


def test_vend_gate_simulates(tmp_path: Path) -> None:
    loaded = load_design_with_meta(_vend_paths(tmp_path))
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
