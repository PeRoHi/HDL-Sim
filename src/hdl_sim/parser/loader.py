"""Load Verilog designs from one or more source files."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from dataclasses import dataclass

from lark.exceptions import UnexpectedCharacters, UnexpectedInput, UnexpectedToken

from hdl_sim.parser.ast import Design, Module
from hdl_sim.parser.parser import parse_design
from hdl_sim.parser.preprocess import expand_includes, preprocess


class VerilogSyntaxError(ValueError):
    """Syntax error with file name, line/column, and a source snippet."""

    def __init__(
        self,
        message: str,
        *,
        file: str = "",
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        super().__init__(message)
        self.file = file
        self.line = line
        self.column = column


_TOKEN_LABELS = {
    "SEMI": ";",
    "COMMA": ",",
    "LPAR": "(",
    "RPAR": ")",
    "LSQB": "[",
    "RSQB": "]",
    "LBRACE": "{",
    "RBRACE": "}",
    "EQUAL": "=",
    "COLON": ":",
    "DOT": ".",
    "HASH": "#",
    "AT": "@",
    "IDENT": "識別子(名前)",
    "INT": "数値",
    "NUMBER": "数値",
    "BASED_NUMBER": "数値 (例 8'h0F)",
    "ENDMODULE": "endmodule",
    "END": "end",
    "BEGIN": "begin",
    "$END": "(ファイル終端)",
}


def _friendly_tokens(names: Iterable[str]) -> str:
    labels = []
    for name in sorted(set(names)):
        labels.append(_TOKEN_LABELS.get(name, name))
    return " / ".join(labels[:8])


def _source_snippet(source: str, line: int, column: int, *, context: int = 2) -> str:
    lines = source.splitlines()
    if not lines or line < 1:
        return ""
    start = max(1, line - context)
    end = min(len(lines), line + 1)
    out: list[str] = []
    for n in range(start, end + 1):
        text = lines[n - 1] if n - 1 < len(lines) else ""
        out.append(f"{n:>5} | {text}")
        if n == line:
            out.append(f"      | {' ' * max(0, column - 1)}^ ここで構文を解釈できません")
    return "\n".join(out)


def format_syntax_error(exc: UnexpectedInput, source: str, file_label: str) -> VerilogSyntaxError:
    """Convert a lark parse error into a readable, located message."""

    line = getattr(exc, "line", None) or 0
    column = getattr(exc, "column", None) or 0
    where = f"{file_label} {line}行目 {column}文字目" if file_label else f"{line}行目 {column}文字目"

    if isinstance(exc, UnexpectedToken):
        token = getattr(exc, "token", None)
        got = f"'{token}'" if token is not None and str(token) else "(不明なトークン)"
        expected = _friendly_tokens(exc.accepts or exc.expected or [])
        detail = f"予期しない {got} が現れました。"
        if expected:
            detail += f" この位置に来られるのは: {expected}"
    elif isinstance(exc, UnexpectedCharacters):
        ch = getattr(exc, "char", "")
        detail = f"解釈できない文字 '{ch}' があります。全角文字や閉じ忘れの引用符がないか確認してください。"
    else:
        detail = str(exc).splitlines()[0]

    snippet = _source_snippet(source, line, column)
    message = f"構文エラー: {where}\n{detail}"
    if snippet:
        message += f"\n{snippet}"
    message += "\nヒント: 直前の行のセミコロン (;) や括弧の閉じ忘れもこの位置のエラーとして報告されます。"
    return VerilogSyntaxError(message, file=file_label, line=line, column=column)


def read_verilog_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp932", "shift_jis"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


@dataclass(frozen=True, slots=True)
class LoadResult:
    design: Design
    timescale: str | None = None


def load_design(
    paths: Iterable[Path | str],
    *,
    defines: dict[str, str] | None = None,
    include_paths: Iterable[Path | str] | None = None,
) -> Design:
    return load_design_with_meta(paths, defines=defines, include_paths=include_paths).design


def load_design_with_meta(
    paths: Iterable[Path | str],
    *,
    defines: dict[str, str] | None = None,
    include_paths: Iterable[Path | str] | None = None,
) -> LoadResult:
    """Parse and merge modules from multiple Verilog files."""

    modules: list[Module] = []
    seen: set[str] = set()
    timescale: str | None = None
    path_list = [Path(path) for path in paths]
    search_paths = [Path(path) for path in include_paths] if include_paths else []
    for source_path in path_list:
        search_paths.append(source_path.parent)
    unique_paths: list[Path] = []
    for directory in search_paths:
        resolved = directory.resolve()
        if resolved not in unique_paths:
            unique_paths.append(resolved)

    module_origin: dict[str, str] = {}
    for source_path in path_list:
        raw = read_verilog_text(source_path)
        pre = preprocess(raw, extra_defines=defines)
        if pre.timescale:
            timescale = pre.timescale
        cleaned = expand_includes(pre.source, unique_paths, extra_defines=pre.defines or defines)
        try:
            design = parse_design(cleaned)
        except UnexpectedInput as exc:
            raise format_syntax_error(exc, cleaned, source_path.name) from exc
        for module in design.modules:
            if module.name in seen:
                msg = (
                    f"モジュール '{module.name}' が複数回定義されています: "
                    f"{module_origin.get(module.name, '?')} と {source_path.name}。"
                    "どちらか一方を削除するか、ファイルを取り除いてください。"
                )
                raise ValueError(msg)
            seen.add(module.name)
            module_origin[module.name] = source_path.name
            modules.append(module)

    if not modules:
        msg = "no modules found in provided Verilog files"
        raise ValueError(msg)

    return LoadResult(design=Design(modules=tuple(modules)), timescale=timescale)
