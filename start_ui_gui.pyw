"""GUI launcher entry point (.pyw on Windows opens without a terminal)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import os

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115


def _bootstrap_crash_log(exc: BaseException) -> None:
    try:
        from hdl_sim.web.crash_log import write_crash_log

        write_crash_log(exc, context="start_ui_gui.bootstrap")
    except Exception:
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "HDL-Sim",
            "HDL-Sim の起動に失敗しました。\n"
            f"{exc}\n\n"
            "インストール先の hdl-sim-crash.log を確認してください。",
        )
        root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from hdl_sim.web.gui_launcher import main

        raise SystemExit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        _bootstrap_crash_log(exc)
        raise SystemExit(1) from exc
