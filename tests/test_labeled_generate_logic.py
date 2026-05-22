from hdl_sim.engine.simulator import Simulator, simulate_source


def test_generate_labeled_block() -> None:
    sim = Simulator.from_source(
        """
        module m;
          parameter N = 2;
          generate
            for (i = 0; i < N; i = i + 1) begin : gen
              wire w;
            end
          endgenerate
        endmodule
        """
    )
    assert any(name.startswith("gen_") and name.endswith("w") for name in sim._nets)


def test_four_state_assign_to_reg() -> None:
    sim = Simulator.from_source(
        """
        module m;
          reg [3:0] y;
          initial y = 4'b1x0z;
        endmodule
        """
    )
    sim.run(until=0, max_events=10)
    net = sim._nets["y"]
    assert net.x_mask != 0 or net.z_mask != 0


def test_fork_with_delay() -> None:
    sim = Simulator.from_source(
        """
        module m;
          reg a;
          reg b;
          initial begin
            a = 0;
            b = 0;
            fork
              begin
                begin #1 a = 1; end
                begin #1 b = 1; end
              end
            join
          end
        endmodule
        """
    )
    sim.run(until=2, max_events=100)
    assert sim._nets["a"].value == 1
    assert sim._nets["b"].value == 1


def test_vcd_emits_x_state(tmp_path) -> None:
    vcd_path = tmp_path / "x.vcd"
    simulate_source(
        """
        module m;
          reg [1:0] y;
          initial begin
            y = 2'b1x;
            $dumpfile("WAVE");
            $dumpvars(y);
          end
        endmodule
        """.replace("WAVE", str(vcd_path)),
        until=0,
        max_events=15,
    )
    text = vcd_path.read_text(encoding="utf-8")
    assert "x" in text.lower() or "b1x" in text
