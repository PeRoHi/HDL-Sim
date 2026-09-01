"""Tests for parser grammar loading."""

from pathlib import Path

from hdl_sim.parser.parser import _grammar_text, describe_expected, parse_design


def test_verilog_grammar_loads() -> None:
    text = _grammar_text()
    assert "module" in text
    assert "endmodule" in text


def test_verilog_grammar_file_exists_in_source_tree() -> None:
    path = Path(__file__).resolve().parents[1] / "src" / "hdl_sim" / "parser" / "verilog.lark"
    assert path.is_file()


def test_describe_expected_maps_terminals_to_literals() -> None:
    assert set(describe_expected(["RPAR", "COMMA"])) == {"')'", "','"}


def test_describe_expected_falls_back_for_regex_terminals() -> None:
    assert describe_expected(["IDENT"]) == ["identifier"]


def test_parse_simple_module() -> None:
    design = parse_design(
        """
        module tb;
          initial $display("ok");
        endmodule
        """
    )
    assert design.top.name == "tb"
