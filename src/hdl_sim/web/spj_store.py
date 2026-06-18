"""Persistent .spj project files for the Web UI (./spj/)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from hdl_sim.web.paths import user_data_dir

SPJ_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+\.spj$")


def spj_dir() -> Path:
    root = user_data_dir() / "spj"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _validate_filename(name: str) -> str:
    cleaned = name.strip().replace("\\", "/").split("/")[-1]
    if not cleaned.lower().endswith(".spj"):
        cleaned = f"{cleaned}.spj"
    if not SPJ_NAME_RE.match(cleaned):
        raise ValueError("spj filename must use letters, digits, _ or - and end with .spj")
    return cleaned


def _resolve_spj_path(name: str) -> Path:
    safe = _validate_filename(name)
    path = (spj_dir() / safe).resolve()
    if spj_dir().resolve() not in path.parents:
        raise ValueError("invalid spj path")
    return path


def list_spj_files() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in sorted(spj_dir().glob("*.spj")):
        rows.append({"name": entry.name, "label": entry.stem})
    return rows


def load_spj_file(name: str) -> dict[str, Any]:
    path = _resolve_spj_path(name)
    if not path.is_file():
        raise FileNotFoundError(name)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("invalid spj content")
    return {"filename": path.name, "data": data}


def save_spj_file(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_spj_path(name)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    
    vs_dir = user_data_dir() / "verilog_sources" / path.stem
    vs_dir.mkdir(parents=True, exist_ok=True)
    
    updated_sources = []
    if "files" in payload:
        for item in payload["files"]:
            if "path" in item and "content" in item:
                v_path = vs_dir / item["path"]
                v_path.write_text(item["content"], encoding="utf-8")
                updated_sources.append({"name": item["path"], "path": str(v_path.resolve())})
                
    return {"filename": path.name, "path": str(path.resolve()), "updated_sources": updated_sources}
