"""Keep user-supplied paths inside a writable jail.

Assume: nested relatives such as ``lib/and2.v`` are allowed (existing UI
multi-file layout). Absolute paths, ``..``, NUL, drive letters, and
symlink escapes are rejected.
"""

from __future__ import annotations

from pathlib import Path

_PROJECT_STEM_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")


def normalize_relpath(raw: str) -> str:
    """Return a jail-relative POSIX path, or raise ``ValueError``."""

    if raw is None or not isinstance(raw, str):
        raise ValueError("invalid file path")
    if "\x00" in raw:
        raise ValueError("invalid file path")
    text = raw.replace("\\", "/").strip()
    if not text or text.startswith("/") or text.startswith("//"):
        raise ValueError("invalid file path")
    if len(text) >= 2 and text[1] == ":":
        raise ValueError("invalid file path")
    parts = [p for p in text.split("/") if p and p != "."]
    if not parts or any(p == ".." for p in parts):
        raise ValueError("invalid file path")
    return "/".join(parts)


def normalize_project_stem(raw: str) -> str:
    """Basename of a project / .spj name used as a ``verilog_sources/`` folder."""

    name = Path(str(raw).replace("\\", "/")).name.strip()
    if name.lower().endswith(".spj"):
        name = name[:-4]
    if not name or any(ch not in _PROJECT_STEM_CHARS for ch in name):
        raise ValueError("invalid project name")
    return name


def ensure_under(root: Path, candidate: Path) -> Path:
    """Resolve *candidate* and require it to stay inside *root*."""

    root_r = root.resolve()
    cand_r = candidate.resolve()
    if cand_r != root_r and root_r not in cand_r.parents:
        raise ValueError("path escapes jail")
    return cand_r


def join_under(root: Path, rel: str) -> Path:
    """Join ``root / rel`` after normalizing *rel*; reject escapes."""

    safe = normalize_relpath(rel)
    return ensure_under(root, root / safe)
