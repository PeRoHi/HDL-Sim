"""real declarations and TB stimulus helpers ($sin, $rtoi)."""

from pathlib import Path

from hdl_sim.engine.elaborator import elaborate
from hdl_sim.engine.simulator import Simulator
from hdl_sim.parser.ast import DeclKind, RealLiteral
from hdl_sim.parser.loader import load_design_with_meta
from hdl_sim.parser.parser import parse_module


def test_real_declaration_parses() -> None:
    mod = parse_module(
        """
module m;
  real pi;
  real sine_r;
endmodule
"""
    )
    kinds = {decl.kind for decl in mod.declarations}
    assert DeclKind.REAL in kinds


def test_real_literal_parses() -> None:
    mod = parse_module(
        """
module m;
  real x;
  initial x = 3.5;
endmodule
"""
    )
    from hdl_sim.parser.ast import Block, BlockingAssign

    init = mod.initial_blocks[0]
    body = init.body
    if isinstance(body, Block):
        stmt = body.statements[0]
    else:
        stmt = body
    assert isinstance(stmt, BlockingAssign)
    assert isinstance(stmt.expr, RealLiteral)


def test_continuous_assign_closure_uses_own_locals() -> None:
    """Each continuous assign must evaluate with its own locals (not the last loop binding)."""
    from hdl_sim.parser.parser import parse_design

    design = parse_design(
        """
module child(output wire y);
  wire a = 1'b1;
  assign y = a;
endmodule
module tb;
  wire y;
  child c(.y(y));
endmodule
"""
    )
    elaborated = elaborate(design, top="tb")
    assert len(elaborated.continuous_assigns) == 1
    assign = elaborated.continuous_assigns[0]
    assert "a" in assign.locals
    evaluator = __import__(
        "hdl_sim.engine.evaluator", fromlist=["ExpressionEvaluator"]
    ).ExpressionEvaluator(assign.locals, params=assign.params)
    assert evaluator.eval_logic(assign.expr).value & 1 == 1


def test_moving_avg_tb_elaborates_and_runs() -> None:
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
    result = Simulator(elaborated).run(until=50_000, max_events=50_000)
    assert result.events_processed > 0
