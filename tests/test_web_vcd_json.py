"""Tests for VCD JSON conversion used by the web UI."""

from hdl_sim.web.vcd_json import parse_vcd_timeline, timeline_to_json


SAMPLE = """$timescale 1ns $end
$scope module tb $end
$var wire 1 ! clk $end
$upscope $end
$enddefinitions $end
#0
0!
#5
1!
#10
0!
"""


def test_parse_vcd_timeline() -> None:
    tl = parse_vcd_timeline(SAMPLE)
    assert tl.timescale == "1ns"
    assert len(tl.signals) == 1
    assert tl.signals[0].name == "clk"
    assert tl.changes["!"] == [(0, "0"), (5, "1"), (10, "0")]


def test_timeline_to_json() -> None:
    data = timeline_to_json(parse_vcd_timeline(SAMPLE))
    assert data["timescale"] == "1ns"
    assert data["signals"][0]["changes"][1] == (5, "1")


def test_parse_bus_values_without_space() -> None:
    sample = """$timescale 1ns $end
$scope module tb $end
$var wire 4 " count $end
$upscope $end
$enddefinitions $end
#0
b0000"
#10
b0100"
"""
    tl = parse_vcd_timeline(sample)
    assert tl.changes['"'] == [(0, "0000"), (10, "0100")]
