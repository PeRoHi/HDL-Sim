"""$monitor formatting and once-per-timestep behavior."""

import io
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

from hdl_sim.engine.elaborator import elaborate
from hdl_sim.engine.simulator import Simulator
from hdl_sim.parser.loader import load_design_with_meta


def test_sai_monitor_prints_once_per_time() -> None:
    root = Path(__file__).resolve().parents[1] / "examples" / "examples"
    loaded = load_design_with_meta([root / "sai.v", root / "saitest.v"])
    elaborated = elaborate(loaded.design, top="sai_test")
    buf = io.StringIO()
    with redirect_stdout(buf):
        Simulator(elaborated).run(until=5000, max_events=5000)
    lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    times = [line.split()[0] for line in lines]
    counts = Counter(times)
    assert all(count == 1 for count in counts.values())
    assert any("lamp=1000001" in line for line in lines)
