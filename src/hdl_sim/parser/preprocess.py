"""Lightweight Verilog source preprocessing."""

from __future__ import annotations

import re


def strip_comments(source: str) -> str:
    """Remove line and block comments while preserving newlines."""

    without_block = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//.*?$", "", without_block, flags=re.MULTILINE)


def normalize_source(source: str) -> str:
    """Prepare Verilog source text for parsing."""

    return strip_comments(source).strip()
