"""Verilog source preprocessing."""

from __future__ import annotations

import re
from dataclasses import dataclass

_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_COMMENT_LINE = re.compile(r"//.*?$", re.MULTILINE)
_DEFINE = re.compile(r"`define\s+(\w+)\s+([^\n]+)")
_UNDEF = re.compile(r"`undef\s+(\w+)\s*")
_TIMESCALE = re.compile(r"`timescale\s+(\S+)\s*/\s*(\S+)\s*")
_DIRECTIVE_LINE = re.compile(r"^\s*`(disable_codecoverage|enable_codecoverage|celldefine|endcelldefine)\b.*$", re.MULTILINE)
_IFDEF_BLOCK = re.compile(r"^\s*`ifn?def\b.*?^\s*`endif\b", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True, slots=True)
class PreprocessResult:
    source: str
    timescale: str | None = None
    defines: dict[str, str] | None = None


def _blank_keep_newlines(match: re.Match[str]) -> str:
    """Replace matched text with newlines only, preserving line numbers."""

    return "\n" * match.group(0).count("\n")


def strip_comments(source: str) -> str:
    without_block = _COMMENT_BLOCK.sub(_blank_keep_newlines, source)
    return _COMMENT_LINE.sub("", without_block)


def apply_defines(source: str, defines: dict[str, str]) -> str:
    result = source
    for name, value in sorted(defines.items(), key=lambda item: len(item[0]), reverse=True):
        result = re.sub(rf"`{name}\b", value.strip(), result)
    return result


def preprocess(source: str, *, extra_defines: dict[str, str] | None = None) -> PreprocessResult:
    """Prepare Verilog source: comments, defines, and directives."""

    defines: dict[str, str] = dict(extra_defines or {})
    timescale: str | None = None

    for match in _TIMESCALE.finditer(source):
        timescale = f"{match.group(1)}/{match.group(2)}"
    for match in _DEFINE.finditer(source):
        defines[match.group(1)] = match.group(2).strip()
    for match in _UNDEF.finditer(source):
        defines.pop(match.group(1), None)

    cleaned = strip_comments(source)
    cleaned = _TIMESCALE.sub(_blank_keep_newlines, cleaned)
    cleaned = _DEFINE.sub(_blank_keep_newlines, cleaned)
    cleaned = _UNDEF.sub(_blank_keep_newlines, cleaned)
    cleaned = _IFDEF_BLOCK.sub(_blank_keep_newlines, cleaned)
    cleaned = _DIRECTIVE_LINE.sub("", cleaned)
    cleaned = apply_defines(cleaned, defines)

    # 末尾のみ strip し、行番号がエラー表示でずれないよう先頭の改行は残す
    return PreprocessResult(source=cleaned.rstrip(), timescale=timescale, defines=defines)



_INCLUDE = re.compile(r"`include\s+\"([^\"]+)\"", re.MULTILINE)


def expand_includes(
    source: str,
    search_paths: list[Path],
    *,
    extra_defines: dict[str, str] | None = None,
    _seen: set[Path] | None = None,
) -> str:
    """Expand `include "file.v"` directives recursively."""

    seen = _seen or set()

    def replace(match: re.Match[str]) -> str:
        include_name = match.group(1)
        for directory in search_paths:
            candidate = (directory / include_name).resolve()
            if not candidate.is_file():
                continue
            if candidate in seen:
                return ""
            seen.add(candidate)
            from hdl_sim.parser.loader import read_verilog_text
            nested = read_verilog_text(candidate)
            nested = preprocess(nested, extra_defines=extra_defines).source
            nested = expand_includes(
                nested,
                search_paths,
                extra_defines=extra_defines,
                _seen=seen,
            )
            return nested + "\n"
        msg = f"unable to find include file: {include_name}"
        raise FileNotFoundError(msg)

    return _INCLUDE.sub(replace, source)

def normalize_source(source: str, *, extra_defines: dict[str, str] | None = None) -> str:
    return preprocess(source, extra_defines=extra_defines).source
