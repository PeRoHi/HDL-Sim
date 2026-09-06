"""Path jail primitives shared by the Web UI, `` `include ``, and ``$dumpfile``.

Jail checks run on the lexical path after nested percent-decode. Symlink
leaves and existing ancestors are refused before ``resolve``.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote

_UNQUOTE_ROUNDS = 8


def nested_unquote(raw: str, *, max_rounds: int = _UNQUOTE_ROUNDS) -> str:
    """Decode percent-encoding repeatedly (capped) before path-component checks."""

    if raw is None or not isinstance(raw, str):
        raise ValueError("invalid file path")
    text = raw
    for _ in range(max_rounds):
        nxt = unquote(text)
        if nxt == text:
            return text
        text = nxt
    if unquote(text) != text:
        raise ValueError("invalid file path")
    return text


def normalize_relpath(raw: str) -> str:
    """Return a jail-relative POSIX path, or raise ``ValueError``."""

    if raw is None or not isinstance(raw, str):
        raise ValueError("invalid file path")
    if "\x00" in raw:
        raise ValueError("invalid file path")
    text = nested_unquote(raw).replace("\\", "/").strip()
    if not text or text.startswith("/") or text.startswith("//"):
        raise ValueError("invalid file path")
    if len(text) >= 2 and text[1] == ":":
        raise ValueError("invalid file path")
    parts = [p for p in text.split("/") if p and p != "."]
    if not parts or any(p == ".." for p in parts):
        raise ValueError("invalid file path")
    return "/".join(parts)


def ensure_under(root: Path, candidate: Path) -> Path:
    """Resolve *candidate* and require it to stay inside *root*."""

    root_r = root.resolve()
    cand_r = candidate.resolve()
    if cand_r != root_r and root_r not in cand_r.parents:
        raise ValueError("path escapes jail")
    return cand_r


def reject_symlink(path: Path) -> Path:
    """Reject a path that is itself a symlink (do not follow it)."""

    if path.is_symlink():
        raise ValueError("symlink not allowed")
    return path


def reject_symlink_chain(path: Path, *, stop_at: Path | None = None) -> Path:
    """Refuse *path* and any existing ancestor that is a symlink.

    Walk stops at *stop_at* (inclusive) when given, so a jailed tree can
    sit under an unrelated symlink (home dir) without being rejected.
    """

    current = Path(path)
    limit = Path(stop_at).resolve() if stop_at is not None else None
    seen: set[str] = set()
    while True:
        key = str(current)
        if key in seen:
            raise ValueError("symlink not allowed")
        seen.add(key)
        if limit is not None:
            try:
                if current.resolve() == limit:
                    break
            except OSError:
                break
        reject_symlink(current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return path


def join_under(root: Path, rel: str) -> Path:
    """Join ``root / rel`` after normalizing *rel*; reject escapes and symlinks."""

    safe = normalize_relpath(rel)
    root_path = Path(root)
    lexical = root_path / Path(safe)
    reject_symlink_chain(lexical, stop_at=root_path)
    dest = ensure_under(root_path, lexical)
    reject_symlink_chain(dest, stop_at=root_path)
    return dest


def jailed_regular_file(root: Path, rel: str) -> Path:
    """Resolve ``root / rel`` inside *root* and require a non-symlink file."""

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
    """Write *text* via a same-directory temp file, ``fsync``, and ``os.replace``.

    If *refuse_empty* is true, do not replace an existing non-empty file
    with an empty (or whitespace-only) payload.

    Refuse writing through a symlink leaf, parent, or leftover tmp name.
    """

    dest = Path(path)
    parent = dest.parent
    if dest.is_symlink() or parent.is_symlink():
        raise ValueError("symlink not allowed")
    reject_symlink_chain(dest, stop_at=parent)
    if refuse_empty and dest.is_file() and dest.stat().st_size > 0 and not (text or "").strip():
        raise ValueError("refusing to overwrite existing file with empty content")
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink():
        raise ValueError("symlink not allowed")
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
    if tmp.is_symlink():
        raise ValueError("symlink not allowed")
    try:
        with tmp.open("w", encoding=encoding, newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if tmp.is_symlink():
            raise ValueError("symlink not allowed")
        os.replace(tmp, dest)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
