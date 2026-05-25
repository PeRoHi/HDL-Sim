"""Persistent project storage for the Web UI (./projects/)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from hdl_sim.web.paths import project_root

PROJECT_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
META_FILE = ".hdl_sim_project.json"


def projects_dir() -> Path:
    root = project_root() / "projects"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _validate_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or not PROJECT_NAME_RE.match(cleaned):
        raise ValueError("project name must contain only letters, digits, _ or -")
    return cleaned


def _project_path(name: str) -> Path:
    safe = _validate_name(name)
    path = (projects_dir() / safe).resolve()
    if projects_dir().resolve() not in path.parents and path != projects_dir().resolve():
        raise ValueError("invalid project path")
    return path


def list_projects() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in sorted(projects_dir().iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        files = list_project_files(entry.name)
        meta = _read_meta(entry)
        rows.append(
            {
                "name": entry.name,
                "label": meta.get("label", entry.name),
                "file_count": len(files),
                "top": meta.get("top"),
            }
        )
    return rows


def _read_meta(project_dir: Path) -> dict[str, Any]:
    meta_path = project_dir / META_FILE
    if not meta_path.is_file():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def create_project(name: str, *, top: str | None = None, label: str | None = None) -> dict[str, Any]:
    path = _project_path(name)
    if path.exists():
        raise FileExistsError(f"project already exists: {name}")
    path.mkdir(parents=True, exist_ok=False)
    meta = {"label": label or name, "top": top}
    (path / META_FILE).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"name": name, "label": meta["label"], "top": top, "files": []}


def list_project_files(name: str) -> list[str]:
    project = _project_path(name)
    if not project.is_dir():
        raise FileNotFoundError(name)
    paths: list[str] = []
    for path in sorted(project.rglob("*.v")):
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
    meta = _read_meta(project)
    return {
        "name": name,
        "label": meta.get("label", name),
        "top": meta.get("top"),
        "files": files,
    }


def save_project(
    name: str,
    files: list[dict[str, str]],
    *,
    top: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    project = _project_path(name)
    project.mkdir(parents=True, exist_ok=True)

    keep = set()
    for item in files:
        rel = item["path"].replace("\\", "/").lstrip("/")
        if ".." in rel.split("/"):
            raise ValueError(f"invalid file path: {rel}")
        dest = project / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(item["content"], encoding="utf-8")
        keep.add(dest.resolve())

    for existing in project.rglob("*.v"):
        if existing.resolve() not in keep:
            existing.unlink()

    meta = _read_meta(project)
    if top is not None:
        meta["top"] = top
    if label is not None:
        meta["label"] = label
    meta.setdefault("label", name)
    (project / META_FILE).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return load_project(name)
