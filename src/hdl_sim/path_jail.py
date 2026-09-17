"""Path jail primitives shared by the Web UI, `` `include ``, and ``$dumpfile``.

Jail checks run on the lexical path after nested percent-decode. Symlink
leaves and existing ancestors are refused before ``resolve``.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from urllib.parse import unquote

_UNQUOTE_ROUNDS = 8


def has_c0_del(text: str) -> bool:
    """True when *text* contains C0 controls or DEL (including CR/LF/NUL/TAB)."""

    return any(ord(ch) < 32 or ord(ch) == 127 for ch in text)


def nested_unquote(raw: str, *, max_rounds: int = _UNQUOTE_ROUNDS) -> str:
    """Decode percent-encoding repeatedly (capped) before path-component checks.

    Each decoded stage is checked for C0/DEL so ``%00`` / ``%0a`` cannot pass.
    """

    if raw is None or not isinstance(raw, str):
        raise ValueError("invalid file path")
    text = raw
    if has_c0_del(text):
        raise ValueError("invalid file path")
    for _ in range(max_rounds):
        nxt = unquote(text)
        if has_c0_del(nxt):
            raise ValueError("invalid file path")
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
    text = nested_unquote(raw).replace("\\", "/").strip()
    if has_c0_del(text):
        raise ValueError("invalid file path")
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


def read_bytes_nofollow(path: Path) -> bytes:
    """Read a regular file without following a leaf symlink (``O_NOFOLLOW``)."""

    dest = Path(path)
    if dest.is_symlink():
        raise ValueError("symlink not allowed")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(os.fspath(dest), flags)
    except OSError as exc:
        raise ValueError("file not found") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("file not found")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def read_text_nofollow(path: Path, *, encoding: str = "utf-8") -> str:
    """Read text via ``read_bytes_nofollow``."""

    return read_bytes_nofollow(path).decode(encoding)


def iter_regular_files(root: Path, *, suffix: str | None = None) -> list[Path]:
    """List regular files under *root* without following directory symlinks."""

    base = Path(root)
    if not base.is_dir() or base.is_symlink():
        return []
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = [
            name
            for name in dirnames
            if not (current / name).is_symlink()
        ]
        for name in filenames:
            path = current / name
            if path.is_symlink() or not path.is_file():
                continue
            if suffix is not None and path.suffix != suffix:
                continue
            found.append(path)
    return found


def atomic_write_text(
    path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    refuse_empty: bool = False,
) -> None:
    """Write *text* via exclusive tmp (``O_EXCL|O_NOFOLLOW``), ``fsync``, replace.

    If *refuse_empty* is true, do not replace an existing non-empty file
    with an empty (or whitespace-only) payload.

    Leftover regular ``.tmp`` is unlinked then recreated. A symlink ``.tmp``
    is refused without unlinking (do not remove the link target).
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
    if tmp.exists():
        tmp.unlink()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd: int | None = None
    created = False
    try:
        fd = os.open(os.fspath(tmp), flags, 0o644)
        created = True
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            fd = None
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if tmp.is_symlink():
            raise ValueError("symlink not allowed")
        os.replace(tmp, dest)
        created = False
    except Exception:
        if created and tmp.exists() and not tmp.is_symlink():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise
    finally:
        if fd is not None:
            os.close(fd)
