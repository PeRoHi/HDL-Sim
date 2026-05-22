"""Load Verilog designs from one or more source files."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from hdl_sim.parser.ast import Design, Module
from hdl_sim.parser.parser import parse_design


def load_design(paths: Iterable[Path | str]) -> Design:
    """Parse and merge modules from multiple Verilog files."""

    modules: list[Module] = []
    seen: set[str] = set()

    for path in paths:
        source_path = Path(path)
        design = parse_design(source_path.read_text(encoding="utf-8"))
        for module in design.modules:
            if module.name in seen:
                msg = f"duplicate module definition: {module.name} in {source_path}"
                raise ValueError(msg)
            seen.add(module.name)
            modules.append(module)

    if not modules:
        msg = "no modules found in provided Verilog files"
        raise ValueError(msg)

    return Design(modules=tuple(modules))
