"""Runtime helpers for dev tree, PyInstaller exe, and pythonw (.pyw) launches."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def bootstrap_import_path() -> None:
    """Allow `python -m hdl_sim.web...` from a source checkout without pip install."""

    if is_frozen():
        return
    try:
        import hdl_sim  # noqa: F401

        return
    except ModuleNotFoundError:
        pass

    src = Path(__file__).resolve().parents[2]
    if (src / "hdl_sim").is_dir():
        src_s = str(src)
        if src_s not in sys.path:
            sys.path.insert(0, src_s)


def ensure_stdio() -> None:
    """pythonw / windowed exe have no stdout; uvicorn logging requires a stream."""

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115


def prepare_runtime() -> None:
    bootstrap_import_path()
    ensure_stdio()
