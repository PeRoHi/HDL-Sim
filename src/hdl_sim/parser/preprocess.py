"""Verilog source preprocessing."""

from __future__ import annotations

import re
from dataclasses import dataclass

_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_COMMENT_LINE = re.compile(r"//.*?$", re.MULTILINE)
_DEFINE = re.compile(r"`define\s+(\w+)\s+([^\n]+)")
_UNDEF = re.compile(r"`undef\s+(\w+)\s*")
_TIMESCALE = re.compile(r"`timescale\s+(\S+)\s*/\s*(\S+)\s*")


@dataclass(frozen=True, slots=True)
class PreprocessResult:
    source: str
    timescale: str | None = None
    defines: dict[str, str] | None = None


def strip_comments(source: str) -> str:
    without_block = _COMMENT_BLOCK.sub("", source)
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
    cleaned = _TIMESCALE.sub("", cleaned)
    cleaned = _DEFINE.sub("", cleaned)
    cleaned = _UNDEF.sub("", cleaned)
    cleaned = apply_defines(cleaned, defines)

    return PreprocessResult(source=cleaned.strip(), timescale=timescale, defines=defines)


def normalize_source(source: str, *, extra_defines: dict[str, str] | None = None) -> str:
    return preprocess(source, extra_defines=extra_defines).source
