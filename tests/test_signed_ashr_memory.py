"""Tests for signed, arithmetic shift (>>>), and unpacked memory declarations."""

from hdl_sim.engine.simulator import Simulator


def test_signed_arithmetic_shift() -> None:
    source = """
    module m;
      reg signed [7:0] a;
      reg [7:0] b;
      initial begin
        a = -8;
        b = a >>> 2;
      end
    endmodule
    """
    sim = Simulator.from_source(source)
    sim.run(until=0, max_events=20)
    assert sim._nets["a"].value == 0xF8
    assert sim._nets["b"].value == 0xFE


def test_unsigned_logical_ashr() -> None:
    source = """
    module m;
      reg [7:0] u;
      reg [7:0] v;
      initial begin
        u = 8'hF8;
        v = u >>> 2;
      end
    endmodule
    """
    sim = Simulator.from_source(source)
    sim.run(until=0, max_events=20)
    assert sim._nets["v"].value == 0x3E


def test_signed_comparison() -> None:
    source = """
    module m;
      reg signed [7:0] a, b;
      reg ok;
      initial begin
        a = -1;
        b = 8'hFF;
        ok = (a < 0);
      end
    endmodule
    """
    sim = Simulator.from_source(source)
    sim.run(until=0, max_events=20)
    assert sim._nets["ok"].value == 1


def test_memory_word_access() -> None:
    source = """
    module m;
      reg [7:0] mem [0:3];
      reg [7:0] x;
      initial begin
        mem[0] = 8'h11;
        mem[1] = 8'h22;
        mem[3] = 8'h44;
        x = mem[2];
      end
    endmodule
    """
    sim = Simulator.from_source(source)
    sim.run(until=0, max_events=30)
    mem = sim._nets["mem"]
    assert mem.is_memory
    assert len(mem.memory) == 4
    assert mem.read_word(0) == 0x11
    assert mem.read_word(1) == 0x22
    assert mem.read_word(3) == 0x44
    assert sim._nets["x"].value == 0


def test_signed_shift_in_initial() -> None:
    source = """
    module m;
      reg signed [3:0] s;
      reg [3:0] y;
      initial begin
        s = -2;
        y = s >>> 1;
      end
    endmodule
    """
    sim = Simulator.from_source(source)
    sim.run(until=0, max_events=30)
    assert sim._nets["y"].value == 0xF
