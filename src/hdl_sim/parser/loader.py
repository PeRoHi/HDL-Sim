"""Load Verilog designs from one or more source files."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from dataclasses import dataclass

from lark.exceptions import UnexpectedInput

from hdl_sim.parser.ast import Design, Module
from hdl_sim.parser.errors import HdlSimSyntaxError
from hdl_sim.parser.parser import describe_expected, parse_design
from hdl_sim.parser.preprocess import expand_includes, preprocess


def _wrap_syntax_error(exc: UnexpectedInput, source_path: Path, text: str) -> HdlSimSyntaxError:
    token = getattr(exc, "token", None)
    if token is not None:
        message = f"予期しないトークンです: {token!s}"
    else:
        char = text[exc.pos_in_stream] if exc.pos_in_stream < len(text) else ""
        message = f"予期しない文字です: {char!r}" if char else "構文エラーです"

    accepts = getattr(exc, "accepts", None) or getattr(exc, "allowed", None)
    if accepts:
        message += f"（期待: {', '.join(describe_expected(accepts))}）"

    try:
        excerpt = exc.get_context(text)
    except Exception:  # pragma: no cover - defensive only
        excerpt = ""

    return HdlSimSyntaxError(
        file=source_path,
        line=getattr(exc, "line", None),
        column=getattr(exc, "column", None),
        message=message,
        excerpt=excerpt,
    )


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

    for source_path in path_list:
        raw = read_verilog_text(source_path)
        pre = preprocess(raw, extra_defines=defines)
        if pre.timescale:
            timescale = pre.timescale
        cleaned = expand_includes(pre.source, unique_paths, extra_defines=pre.defines or defines)
        try:
            design = parse_design(cleaned)
        except UnexpectedInput as exc:
            raise _wrap_syntax_error(exc, source_path, cleaned) from exc
        for module in design.modules:
            if module.name in seen:
                msg = f"duplicate module definition: {module.name} in {source_path.name}"
                raise ValueError(msg)
            seen.add(module.name)
            modules.append(module)

    if not modules:
        msg = "no modules found in provided Verilog files"
        raise ValueError(msg)

    return LoadResult(design=Design(modules=tuple(modules)), timescale=timescale)
