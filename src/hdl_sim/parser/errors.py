"""Structured parse errors surfaced to the Web UI.

A raw ``lark`` exception is precise but Python-internal (exception class
names, grammar terminal names, no reference to the user's file). This
wraps it with the pieces a UI needs to point the user at the mistake:
which file, which line/column, and a short excerpt of the offending line.
"""

from __future__ import annotations

from pathlib import Path


class HdlSimSyntaxError(Exception):
    """A Verilog syntax error, located in the user's source."""

    def __init__(
        self,
        *,
        file: Path,
        line: int | None,
        column: int | None,
        message: str,
        excerpt: str,
    ) -> None:
        self.file = file
        self.line = line
        self.column = column
        self.message = message
        self.excerpt = excerpt
        where = f"{file}:{line}:{column}" if line is not None else str(file)
        super().__init__(f"{where}: {message}")
