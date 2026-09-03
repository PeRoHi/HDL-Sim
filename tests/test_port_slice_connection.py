"""Port connections with bit/part selects (e.g. .DIN(bus[3:0]))."""

from pathlib import Path

from hdl_sim.engine.elaborator import elaborate
from hdl_sim.parser.loader import load_design_with_meta


def test_reflex_game_elaborates_with_slice_port() -> None:
    root = Path(__file__).resolve().parents[1] / "examples"
    paths = [
        root / "lfsr8.v",
        root / "main_controller.v",
        root / "reflex_game_tp.v",
        root / "reflex_game.v",
        root / "seg7_decoder.v",
        root / "timer16.v",
    ]
    loaded = load_design_with_meta(paths)
    elaborated = elaborate(loaded.design, top="reflex_game_tp")
    assert elaborated.top_module == "reflex_game_tp"
    din_targets = [a.target for a in elaborated.continuous_assigns if a.target.endswith(".DIN")]
    assert din_targets
