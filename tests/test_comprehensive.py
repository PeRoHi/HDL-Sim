from pathlib import Path

from hdl_sim.engine.simulator import Simulator
from hdl_sim.parser import parse_module
from hdl_sim.parser.ast import BitSelect, BlockingAssign, CaseStmt, IdentRef, Lvalue, WhileStmt

ROOT = Path(__file__).resolve().parents[1]


def test_bit_select_assign() -> None:
    source = """
    module m;
      reg [3:0] bus;
      initial begin
        bus = 4'b1010;
        bus[1] = 1'b0;
      end
    endmodule
    """
    sim = Simulator.from_source(source)
    sim.run(until=0, max_events=20)
    assert sim._nets["bus"].value == 0b1000


def test_case_statement() -> None:
    source = """
    module m;
      reg [1:0] sel;
      reg [3:0] out;
      initial begin
        sel = 2;
        case (sel)
          0: out = 4'h1;
          2: out = 4'hA;
          default: out = 4'hF;
        endcase
      end
    endmodule
    """
    sim = Simulator.from_source(source)
    sim.run(until=0, max_events=20)
    assert sim._nets["out"].value == 0xA


def test_while_loop() -> None:
    source = """
    module m;
      reg [3:0] i;
      reg [3:0] sum;
      initial begin
        i = 0;
        sum = 0;
        while (i < 4) begin
          sum = sum + i;
          i = i + 1;
        end
      end
    endmodule
    """
    sim = Simulator.from_source(source)
    sim.run(until=0, max_events=200)
    assert sim._nets["sum"].value == 6


def test_finish_stops_simulation() -> None:
    source = """
    module m;
      reg clk;
      initial begin
        clk = 0;
        #5 clk = 1;
        $finish;
        #100 clk = 0;
      end
    endmodule
    """
    result = Simulator.from_source(source).run(until=200, max_events=500)
    assert result.stop_time == 5


def test_comb_always() -> None:
    source = """
    module m;
      wire a;
      wire b;
      wire y;
      assign a = 1;
      assign b = 0;
      always @(*) y = a & b;
    endmodule
    """
    sim = Simulator.from_source(source)
    sim.run(until=0, max_events=50)
    assert sim._nets["y"].value == 0


def test_parse_lvalue_and_case() -> None:
    module = parse_module(
        """
        module m;
          reg [3:0] x;
          initial case (x[1])
            1: x[0] = 1;
          endcase
        endmodule
        """
    )
    initial = module.initial_blocks[0].body
    assert isinstance(initial, CaseStmt)
    assert isinstance(initial.expression, BitSelect)
    item = initial.items[0]
    assert item.expressions[0].value == 1
    assert isinstance(item.body, BlockingAssign)
    assert isinstance(item.body.target, Lvalue)
