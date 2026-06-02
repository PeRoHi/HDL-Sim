"""Load Verilog designs from one or more source files."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from dataclasses import dataclass

from hdl_sim.parser.ast import Design, Module
from hdl_sim.parser.parser import parse_design
from hdl_sim.parser.preprocess import expand_includes, preprocess


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
        design = parse_design(cleaned)
        for module in design.modules:
            if module.name in seen:
                msg = f"duplicate module definition: {module.name} in {source_path}"
                raise ValueError(msg)
            seen.add(module.name)
            modules.append(module)

    if not modules:
        msg = "no modules found in provided Verilog files"
        raise ValueError(msg)

    return LoadResult(design=Design(modules=tuple(modules)), timescale=timescale)
