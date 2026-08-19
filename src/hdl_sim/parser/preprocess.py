"""Verilog source preprocessing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_COMMENT_LINE = re.compile(r"//.*?$", re.MULTILINE)
_DEFINE = re.compile(r"`define\s+(\w+)\s+([^\n]+)")
_UNDEF = re.compile(r"`undef\s+(\w+)\s*")
_TIMESCALE = re.compile(r"`timescale\s+(\S+)\s*/\s*(\S+)\s*")
_DIRECTIVE_LINE = re.compile(r"^\s*`(disable_codecoverage|enable_codecoverage|celldefine|endcelldefine)\b.*$")
_IFDEF = re.compile(r"^\s*`ifdef\s+(\w+)")
_IFNDEF = re.compile(r"^\s*`ifndef\s+(\w+)")
_ELSE = re.compile(r"^\s*`else\b")
_ELSIF = re.compile(r"^\s*`elsif\s+(\w+)")
_ENDIF = re.compile(r"^\s*`endif\b")


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

    cleaned = _apply_conditionals(strip_comments(source), defines)
    cleaned = _TIMESCALE.sub(_blank_keep_newlines, cleaned)
    cleaned = _DEFINE.sub(_blank_keep_newlines, cleaned)
    cleaned = _UNDEF.sub(_blank_keep_newlines, cleaned)
    cleaned = re.sub(
        r"^\s*`(disable_codecoverage|enable_codecoverage|celldefine|endcelldefine)\b.*$",
        "",
        cleaned,
        flags=re.MULTILINE,
    )
    cleaned = apply_defines(cleaned, defines)
    return PreprocessResult(source=cleaned.rstrip(), timescale=timescale, defines=defines)


@dataclass
class _IfFrame:
    parent_on: bool
    current_on: bool
    already_taken: bool


def _emitting(stack: list[_IfFrame]) -> bool:
    return all(frame.current_on for frame in stack)


def _apply_conditionals(source: str, defines: dict[str, str]) -> str:
    """Evaluate `ifdef / `ifndef / `else / `elsif / `endif while keeping line numbers."""

    lines = source.splitlines(keepends=True)
    stack: list[_IfFrame] = []
    out: list[str] = []

    def blank(line: str) -> str:
        return "\n" if line.endswith("\n") else ""

    for line in lines:
        stripped = line.split("\n", 1)[0]
        ifdef = _IFDEF.match(stripped)
        ifndef = _IFNDEF.match(stripped)
        elsif = _ELSIF.match(stripped)
        if ifdef or ifndef:
            name = (ifdef or ifndef).group(1)
            parent_on = _emitting(stack)
            taken = parent_on and ((name in defines) if ifdef else (name not in defines))
            stack.append(_IfFrame(parent_on, taken, taken))
            out.append(blank(line))
            continue
        if _ELSE.match(stripped):
            if not stack:
                out.append(blank(line))
                continue
            frame = stack[-1]
            frame.current_on = frame.parent_on and not frame.already_taken
            frame.already_taken = True
            out.append(blank(line))
            continue
        if elsif:
            if not stack:
                out.append(blank(line))
                continue
            frame = stack[-1]
            name = elsif.group(1)
            if frame.already_taken or not frame.parent_on:
                frame.current_on = False
            else:
                frame.current_on = name in defines
                if frame.current_on:
                    frame.already_taken = True
            out.append(blank(line))
            continue
        if _ENDIF.match(stripped):
            if stack:
                stack.pop()
            out.append(blank(line))
            continue
        if not _emitting(stack):
            out.append(blank(line))
            continue
        defined = _DEFINE.match(stripped.lstrip())
        if defined:
            defines[defined.group(1)] = defined.group(2).strip()
            out.append(blank(line))
            continue
        undefined = _UNDEF.match(stripped.lstrip())
        if undefined:
            defines.pop(undefined.group(1), None)
            out.append(blank(line))
            continue
        out.append(line)
    return "".join(out)



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
            root = Path(directory).resolve()
            if candidate != root and root not in candidate.parents:
                continue
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
