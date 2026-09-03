"""Readable error messages: syntax errors with location, elaborate context."""

from __future__ import annotations

from pathlib import Path

import pytest

from hdl_sim.engine.elaborator import elaborate
from hdl_sim.parser.loader import VerilogSyntaxError, load_design_with_meta
from hdl_sim.parser.parser import parse_design


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_syntax_error_reports_file_line_and_snippet(tmp_path: Path) -> None:
    src = """`timescale 1ns/1ps
/* block
   comment */
module m;
  reg [3:0 x;
  initial x = 1;
endmodule
"""
    path = _write(tmp_path, "broken.v", src)
    with pytest.raises(VerilogSyntaxError) as ei:
        load_design_with_meta([path])
    err = ei.value
    assert err.file == "broken.v"
    # コメント・timescale を除去しても元ファイルの行番号と一致する
    assert err.line == 5
    text = str(err)
    assert "broken.v" in text
    assert "5行目" in text
    assert "reg [3:0 x;" in text
    assert "^" in text


def test_duplicate_module_error_names_both_files(tmp_path: Path) -> None:
    a = _write(tmp_path, "a.v", "module dup; endmodule\n")
    b = _write(tmp_path, "b.v", "module dup; endmodule\n")
    with pytest.raises(ValueError) as ei:
        load_design_with_meta([a, b])
    text = str(ei.value)
    assert "dup" in text
    assert "a.v" in text
    assert "b.v" in text


def test_missing_module_error_lists_known_modules() -> None:
    design = parse_design(
        """
        module top;
          wire w;
          ghost u_ghost (w);
        endmodule
        """
    )
    with pytest.raises(ValueError) as ei:
        elaborate(design, top="top")
    text = str(ei.value)
    assert "ghost" in text
    assert "u_ghost" in text
    assert "top" in text


def test_unknown_port_error_lists_available_ports() -> None:
    design = parse_design(
        """
        module child(input a, output b);
          assign b = a;
        endmodule
        module top;
          wire x, y;
          child u_c (.a(x), .nonexistent(y));
        endmodule
        """
    )
    with pytest.raises(ValueError) as ei:
        elaborate(design, top="top")
    text = str(ei.value)
    assert "nonexistent" in text
    assert "u_c" in text
    assert "a, b" in text


def test_unknown_connection_signal_mentions_declaration_hint() -> None:
    design = parse_design(
        """
        module child(input a);
        endmodule
        module top;
          child u_c (.a(undeclared_sig));
        endmodule
        """
    )
    with pytest.raises(ValueError) as ei:
        elaborate(design, top="top")
    text = str(ei.value)
    assert "undeclared_sig" in text
    assert "宣言" in text
