"""Resolve project paths for dev and PyInstaller builds."""

from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def ui_dir() -> Path:
    if getattr(sys, "frozen", False):
        bundled = Path(getattr(sys, "_MEIPASS", project_root())) / "ui"
        if bundled.is_dir():
            return bundled
    return project_root() / "ui"


def examples_dir() -> Path:
    if getattr(sys, "frozen", False):
        bundled = Path(getattr(sys, "_MEIPASS", project_root())) / "examples"
        if bundled.is_dir():
            return bundled
    return project_root() / "examples"
