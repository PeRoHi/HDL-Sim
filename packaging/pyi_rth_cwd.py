"""PyInstaller runtime hook: fix cwd and DLL search path for onedir builds."""

from __future__ import annotations

import os
import sys


def _app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.getcwd()


if getattr(sys, "frozen", False):
    app_dir = _app_dir()
    try:
        os.chdir(app_dir)
    except OSError:
        pass

    internal = os.path.join(app_dir, "_internal")
    if os.path.isdir(internal):
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(internal)
        os.environ["PATH"] = internal + os.pathsep + os.environ.get("PATH", "")
