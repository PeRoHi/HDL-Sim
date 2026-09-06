"""Persistent project storage for the Web UI (./projects/)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from hdl_sim.web.path_safety import atomic_write_text, join_under, reject_symlink
from hdl_sim.web.paths import user_data_dir

PROJECT_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
META_FILE = ".hdl_sim_project.json"


def projects_dir() -> Path:
    root = user_data_dir() / "projects"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _validate_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or not PROJECT_NAME_RE.match(cleaned):
        raise ValueError("project name must contain only letters, digits, _ or -")
    return cleaned


def _project_path(name: str) -> Path:
    safe = _validate_name(name)
    return join_under(projects_dir(), safe)


def list_projects() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in sorted(projects_dir().iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        try:
            files = list_project_files(entry.name)
            meta = _read_meta(entry)
        except ValueError:
            continue
        rows.append(
            {
                "name": entry.name,
                "label": meta.get("label", entry.name),
                "file_count": len(files),
                "top": meta.get("top"),
            }
        )
    return rows


def _read_meta(project_dir: Path, *, required: bool = False) -> dict[str, Any]:
    meta_path = project_dir / META_FILE
    if not meta_path.is_file():
        if required:
            raise ValueError("loadFailed")
        return {}
    if meta_path.is_symlink():
        raise ValueError("symlink not allowed")
    raw = meta_path.read_text(encoding="utf-8")
    if not raw.strip() or meta_path.stat().st_size == 0:
        raise ValueError("loadFailed")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("loadFailed") from exc
    if not isinstance(data, dict):
        raise ValueError("loadFailed")
    return data


def create_project(name: str, *, top: str | None = None, label: str | None = None) -> dict[str, Any]:
    path = _project_path(name)
    if path.exists():
        raise FileExistsError(f"project already exists: {name}")
    path.mkdir(parents=True, exist_ok=False)
    meta = {"label": label or name, "top": top}
    atomic_write_text(path / META_FILE, json.dumps(meta, indent=2), encoding="utf-8")
    return {"name": name, "label": meta["label"], "top": top, "files": []}


def list_project_files(name: str) -> list[str]:
    project = _project_path(name)
    if not project.is_dir():
        raise FileNotFoundError(name)
    paths: list[str] = []
    for path in sorted(project.rglob("*.v")):
        if path.is_symlink():
            continue
        rel = path.relative_to(project).as_posix()
        if rel == META_FILE:
            continue
        paths.append(rel)
    return paths


def load_project(name: str) -> dict[str, Any]:
    project = _project_path(name)
    if not project.is_dir():
        raise FileNotFoundError(name)
    files: list[dict[str, str]] = []
    for rel in list_project_files(name):
        content = (project / rel).read_text(encoding="utf-8")
        files.append({"path": rel, "content": content})
    meta = _read_meta(project, required=True) if (project / META_FILE).exists() else {}
    wave = meta.get("wave")
    return {
        "name": name,
        "label": meta.get("label", name),
        "top": meta.get("top"),
        "files": files,
        "wave": wave if isinstance(wave, dict) else None,
    }


def save_project(
    name: str,
    files: list[dict[str, str]],
    *,
    top: str | None = None,
    label: str | None = None,
    wave: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project = _project_path(name)
    project.mkdir(parents=True, exist_ok=True)

    keep = set()
    for item in files:
        dest = join_under(project, item["path"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        reject_symlink(dest)
        atomic_write_text(dest, item["content"], encoding="utf-8")
        keep.add(dest.resolve())

    for existing in project.rglob("*.v"):
        if existing.resolve() not in keep:
            existing.unlink()

    try:
        meta = _read_meta(project)
    except ValueError as exc:
        if str(exc) != "loadFailed":
            raise
        meta = {}
    if top is not None:
        meta["top"] = top
    if label is not None:
        meta["label"] = label
    if wave is not None:
        meta["wave"] = wave
    meta.setdefault("label", name)
    atomic_write_text(project / META_FILE, json.dumps(meta, indent=2), encoding="utf-8")

    return load_project(name)
