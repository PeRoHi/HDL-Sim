"""Write startup crash logs next to the installed app (frozen builds)."""

from __future__ import annotations

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


def crash_log_paths() -> list[Path]:
    paths: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        paths.append(exe_dir / "hdl-sim-crash.log")
    try:
        local = Path.home() / "AppData" / "Local" / "HDL-Sim" / "hdl-sim-crash.log"
        paths.append(local)
    except Exception:
        pass
    return paths


def should_write_crash_log(exc: BaseException) -> bool:
    """Normal process exit (code 0) is not a crash."""
    if isinstance(exc, KeyboardInterrupt):
        return False
    if isinstance(exc, SystemExit):
        code = exc.code
        return not (code is None or code == 0)
    return True


def write_crash_log(exc: BaseException, *, context: str = "") -> Path | None:
    if not should_write_crash_log(exc):
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    body = f"[{stamp}] {context}\n{traceback.format_exc()}\n"
    written: Path | None = None
    for path in crash_log_paths():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            written = path
        except OSError:
            continue
    return written
