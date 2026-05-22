#!/usr/bin/env python3
"""One-command launcher for the HDL-Sim browser UI.

Double-click this file on many desktops, or run:

    python3 start_ui.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hdl_sim.web.launcher import main


if __name__ == "__main__":
    raise SystemExit(main())
