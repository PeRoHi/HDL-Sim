"""Top module resolution when UI sends a stale name (e.g. tb)."""

from hdl_sim.parser.parser import parse_design
from hdl_sim.web.app import resolve_top_module


def test_resolve_top_ignores_missing_tb_prefers_tp() -> None:
    design = parse_design(
        """
        module reflex_game(input clk);
        endmodule
        module reflex_game_tp;
          reflex_game uut(.clk(1'b0));
        endmodule
        """
    )
    assert resolve_top_module(design, "tb") == "reflex_game_tp"
    assert resolve_top_module(design, None) == "reflex_game_tp"
    assert resolve_top_module(design, "reflex_game_tp") == "reflex_game_tp"
