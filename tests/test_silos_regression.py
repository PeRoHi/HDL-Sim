"""Integration tests aimed at Silos-replacement confidence."""

from __future__ import annotations

import subprocess
from pathlib import Path

from hdl_sim.engine.simulator import Simulator, simulate_files

ROOT = Path(__file__).resolve().parents[1]
SILOS_TB = ROOT / "examples" / "silos_regression.v"
PARAM_COUNTER = ROOT / "examples" / "param_counter.v"
TB_MULTI = ROOT / "examples" / "tb_multi.v"
AND2 = ROOT / "examples" / "lib" / "and2.v"


def test_silos_regression_hierarchy(capsys) -> None:
    source = SILOS_TB.read_text(encoding="utf-8")
    sim = Simulator.from_source(source, top="silos_regression_tb")
    sim.run(until=50, max_events=500)
    captured = capsys.readouterr().out
    assert "SILOS_REGRESSION PASS" in captured
    assert "count" in sim._nets
    count_net = "count"
    assert sim._nets[count_net].value >= 4


def test_param_counter_nba_until_25() -> None:
    sim = Simulator.from_file(PARAM_COUNTER)
    sim.run(until=25, max_events=500)
    count_net = next(n for n in sim._nets if n.endswith("count"))
    assert sim._nets[count_net].value >= 2


def test_tb_multi_and_gate() -> None:
    result = simulate_files([TB_MULTI, AND2], top="tb_multi", until=5, max_events=100)
    assert result.events_processed > 0
    sim = Simulator.from_source(
        TB_MULTI.read_text(encoding="utf-8") + "\n" + AND2.read_text(encoding="utf-8"),
        top="tb_multi",
    )
    sim.run(until=5, max_events=100)
    assert sim._nets["ry"].value == 1


def test_continuous_assign_propagates_x() -> None:
    sim = Simulator.from_source(
        """
        module m;
          reg [1:0] a;
          wire [1:0] y;
          assign y = a;
          initial a = 2'b1x;
        endmodule
        """
    )
    sim.run(until=0, max_events=30)
    y = next(n for n in sim._nets if n.endswith("y"))
    assert sim._nets[y].x_mask != 0


def test_nba_preserves_x_on_nonblocking() -> None:
    sim = Simulator.from_source(
        """
        module m;
          reg [1:0] q;
          initial q <= 2'b1x;
        endmodule
        """
    )
    sim.run(until=0, max_events=20)
    assert sim._nets["q"].x_mask != 0


def test_cli_runs_silos_example() -> None:
    result = subprocess.run(
        [
            "python3",
            "-m",
            "hdl_sim",
            str(SILOS_TB),
            "--top",
            "silos_regression_tb",
            "--until",
            "50",
            "--max-events",
            "500",
        ],
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "SILOS_REGRESSION PASS" in result.stdout
