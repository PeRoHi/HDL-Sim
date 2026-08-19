"""Keep user-supplied relative paths inside a writable root."""

from __future__ import annotations

from pathlib import Path


def normalize_relpath(raw: str) -> str:
    text = str(raw).replace("\\", "/").strip()
    if not text or text.startswith("/") or (len(text) >= 2 and text[1] == ":"):
        raise ValueError(f"invalid file path: {raw}")
    parts = [p for p in text.split("/") if p and p != "."]
    if not parts or any(p == ".." for p in parts):
        raise ValueError(f"invalid file path: {raw}")
    return "/".join(parts)


def ensure_under(root: Path, candidate: Path) -> Path:
    root_r = root.resolve()
    cand_r = candidate.resolve()
    if cand_r != root_r and root_r not in cand_r.parents:
        raise ValueError(f"path escapes {root_r}")
    return cand_r


def join_under(root: Path, rel: str) -> Path:
    safe = normalize_relpath(rel)
    dest = (root / safe).resolve()
    return ensure_under(root, dest)
