"""Run the HDL-Sim browser UI with `python -m hdl_sim.web`."""

from __future__ import annotations

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    try:
        import hdl_sim  # noqa: F401
    except ModuleNotFoundError:
        src = Path(__file__).resolve().parents[2]
        if (src / "hdl_sim").is_dir() and str(src) not in sys.path:
            sys.path.insert(0, str(src))

from hdl_sim.web.runtime import prepare_runtime

prepare_runtime()

from hdl_sim.web import main


if __name__ == "__main__":
    raise SystemExit(main())
