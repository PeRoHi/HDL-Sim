"""Signed wire values must sign-extend in integer arithmetic (TB roughness etc.)."""

from hdl_sim.engine.simulator import Simulator


def test_signed_wire_subtract_integer() -> None:
    source = """
    module m;
      reg signed [11:0] x;
      integer prev;
      integer diff;
      initial begin
        x = -12'd142;
        prev = -400;
        diff = x - prev;
      end
    endmodule
    """
    sim = Simulator.from_source(source)
    sim.run(until=0, max_events=20)
    assert sim._nets["diff"].value == 258


def test_moving_avg_roughness_not_overflow() -> None:
    from pathlib import Path

    from hdl_sim.engine.elaborator import elaborate
    from hdl_sim.parser.loader import load_design_with_meta

    root = Path(__file__).resolve().parents[1] / "examples" / "kadai"
    paths = [
        root / "delay_line.v",
        root / "moving_avg_core.v",
        root / "moving_avg_filter.v",
        root / "tb_moving_avg_filter.v",
    ]
    if not all(p.is_file() for p in paths):
        return
    loaded = load_design_with_meta(paths)
    elaborated = elaborate(loaded.design, top="tb_moving_avg_filter")
    sim = Simulator(elaborated)
    sim.run(until=50_000, max_events=50_000)
    rough_single = sim._nets["rough_single"].value
    rough_cascade = sim._nets["rough_cascade"].value
    # 符号なし扱いのバグでは 2^32 付近に張り付く
    assert rough_single < 1_000_000
    assert rough_cascade < 1_000_000
    assert rough_single > 0
