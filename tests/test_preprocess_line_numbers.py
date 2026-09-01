"""Preprocessing must not shift line numbers, or syntax-error locations
reported to the user point at the wrong line (see docs/architecture.md
error-reporting notes)."""

from __future__ import annotations

from hdl_sim.parser.preprocess import preprocess


def test_leading_comment_and_timescale_preserve_line_count() -> None:
    source = (
        "// header comment\n"
        "`timescale 1ns/1ps\n"
        "\n"
        "module m;\n"
        "endmodule\n"
    )
    result = preprocess(source)
    lines = result.source.split("\n")
    assert lines[3].strip() == "module m;"


def test_block_comment_spanning_lines_preserves_line_count() -> None:
    source = "module m;\n/* line a\nline b\nline c */\nreg x;\nendmodule\n"
    result = preprocess(source)
    lines = result.source.split("\n")
    assert lines[4].strip() == "reg x;"


def test_define_and_undef_preserve_line_count() -> None:
    source = "`define WIDTH 4\nmodule m;\n`undef WIDTH\nendmodule\n"
    result = preprocess(source)
    lines = result.source.split("\n")
    assert lines[1].strip() == "module m;"
