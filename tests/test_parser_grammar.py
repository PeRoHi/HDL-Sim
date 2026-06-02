"""Tests for parser grammar loading."""

from pathlib import Path

from hdl_sim.parser.parser import _grammar_text, parse_design


def test_verilog_grammar_loads() -> None:
    text = _grammar_text()
    assert "module" in text
    assert "endmodule" in text


def test_verilog_grammar_file_exists_in_source_tree() -> None:
    path = Path(__file__).resolve().parents[1] / "src" / "hdl_sim" / "parser" / "verilog.lark"
    assert path.is_file()


def test_parse_simple_module() -> None:
    design = parse_design(
        """
        module tb;
          initial $display("ok");
        endmodule
        """
    )
    assert design.top.name == "tb"
