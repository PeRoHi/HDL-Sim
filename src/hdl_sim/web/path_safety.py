"""Keep user-supplied paths inside a writable jail.

Assume: nested relatives such as ``lib/and2.v`` are allowed (existing UI
multi-file layout). Absolute paths, ``..``, NUL, drive letters, and
symlink escapes are rejected.
"""

from __future__ import annotations

import os
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


def reject_symlink(path: Path) -> Path:
    """Reject a path that is itself a symlink (do not follow it)."""

    if path.is_symlink():
        raise ValueError("symlink not allowed")
    return path


def jailed_regular_file(root: Path, rel: str) -> Path:
    """Resolve ``root / rel`` inside *root* and require a non-symlink file."""

    lexical = Path(root) / Path(normalize_relpath(rel))
    reject_symlink(lexical)
    dest = join_under(root, rel)
    reject_symlink(dest)
    if not dest.is_file():
        raise ValueError("file not found")
    return dest


def atomic_write_text(
    path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    refuse_empty: bool = False,
) -> None:
    """Write *text* via a same-directory temp file and ``os.replace``.

    If *refuse_empty* is true, do not replace an existing non-empty file
    with an empty (or whitespace-only) payload. That avoids clobbering a
    corrupted JSON / sidecar with an empty write.
    """

    dest = Path(path)
    if refuse_empty and dest.is_file() and dest.stat().st_size > 0 and not (text or "").strip():
        raise ValueError("refusing to overwrite existing file with empty content")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding=encoding)
        os.replace(tmp, dest)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
