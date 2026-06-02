"""Resolve project paths for dev and PyInstaller builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def install_dir() -> Path:
    """Directory containing the app executable (frozen) or repo root (dev)."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def project_root() -> Path:
    return install_dir()


def _read_data_dir_override() -> Path | None:
    cfg = install_dir() / "data_dir.txt"
    if not cfg.is_file():
        return None
    text = cfg.read_text(encoding="utf-8").strip()
    if not text:
        return None
    return Path(text)


def user_data_dir() -> Path:
    """Writable folder for projects/, spj/, and user files."""

    override = _read_data_dir_override()
    if override is not None:
        override.mkdir(parents=True, exist_ok=True)
        return override

    if getattr(sys, "frozen", False):
        inst = install_dir()
        try:
            probe = inst / "spj"
            probe.mkdir(parents=True, exist_ok=True)
            test = probe / ".write_test"
            test.write_text("ok", encoding="utf-8")
            test.unlink()
            return inst
        except OSError:
            data = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "HDL-Sim"
            data.mkdir(parents=True, exist_ok=True)
            return data

    return project_root()


def ui_dir() -> Path:
    if getattr(sys, "frozen", False):
        bundled = Path(getattr(sys, "_MEIPASS", project_root())) / "ui"
        if bundled.is_dir():
            return bundled
    return project_root() / "ui"


def examples_dir() -> Path:
    if getattr(sys, "frozen", False):
        beside_exe = install_dir() / "examples"
        if beside_exe.is_dir():
            return beside_exe
        bundled = Path(getattr(sys, "_MEIPASS", project_root())) / "examples"
        if bundled.is_dir():
            return bundled
    return project_root() / "examples"
