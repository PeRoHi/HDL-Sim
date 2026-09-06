"""Web-facing path helpers and client-safe error summarizer."""

from __future__ import annotations

import re
from pathlib import Path

from hdl_sim.path_jail import (
    atomic_write_text,
    ensure_under,
    jailed_regular_file,
    join_under,
    nested_unquote,
    normalize_relpath,
    reject_symlink,
    reject_symlink_chain,
)

_PROJECT_STEM_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")

# Product messages that may be shown to the local UI as-is.
_ALLOWED_CLIENT_ERRORS = frozenset(
    {
        "invalid file path",
        "invalid project name",
        "path escapes jail",
        "symlink not allowed",
        "file not found",
        "refusing to overwrite existing file with empty content",
        "refusing to overwrite existing project with empty files",
        "loadFailed",
        "invalid host",
        "invalid origin",
        "missing host",
        "invalid dumpfile path",
        "dumpfile path must be relative to the simulation directory",
        "invalid spj file path",
        "spj referenced file not found",
        "invalid spj content",
        "invalid spj path",
        "invalid project path",
        "project name must contain only letters, digits, _ or -",
        "spj filename must use letters, digits, _ or - and end with .spj",
        "no elaboration entry files (only include-only sources?)",
        "no modules found in provided Verilog files",
        "project not found",
        "spj file not found",
        "example not found",
        "storage error",
        "files required",
        "invalid spj format",
        "invalid spj",
        "不明な参照",
        "internal simulation error",
        "unable to find include file",
        "not found",
    }
)

_OS_LEAK = re.compile(
    r"(?:"
    r"\bErrno\b"
    r"|\[Errno"
    r"|Traceback \(most recent call last\)"
    r"|[A-Za-z]:[\\/]"
    r"|/(?:home|tmp|var|etc|usr|opt|Users|workspace)/"
    r")"
)

__all__ = [
    "atomic_write_text",
    "client_error_from_exception",
    "ensure_under",
    "jailed_regular_file",
    "join_under",
    "looks_like_os_leak",
    "nested_unquote",
    "normalize_project_stem",
    "normalize_relpath",
    "reject_symlink",
    "reject_symlink_chain",
    "summarize_client_error",
]


def normalize_project_stem(raw: str) -> str:
    """Basename of a project / .spj name used as a ``verilog_sources/`` folder."""

    name = Path(nested_unquote(str(raw)).replace("\\", "/")).name.strip()
    if name.lower().endswith(".spj"):
        name = name[:-4]
    if not name or any(ch not in _PROJECT_STEM_CHARS for ch in name):
        raise ValueError("invalid project name")
    return name


def looks_like_os_leak(text: str) -> bool:
    """True when *text* looks like an OS path, errno, or traceback."""

    if not text:
        return False
    if "\x00" in text:
        return True
    return bool(_OS_LEAK.search(text))


def summarize_client_error(detail: object) -> object:
    """Reduce client-facing error payloads. Covers strings and arrays."""

    if isinstance(detail, list):
        return [summarize_client_error(item) for item in detail]
    if isinstance(detail, dict):
        return {key: summarize_client_error(value) for key, value in detail.items()}
    if detail is None:
        return "request failed"
    if not isinstance(detail, str):
        detail = str(detail)
    text = detail.strip()
    if not text:
        return "request failed"
    if text in _ALLOWED_CLIENT_ERRORS:
        return text
    if looks_like_os_leak(text):
        return "request failed"
    if text.startswith("unable to find include file"):
        return "unable to find include file"
    if text.startswith("project already exists:"):
        return "project already exists"
    return text


def client_error_from_exception(exc: BaseException) -> str:
    """Map an exception to a client-safe string (never OS path / errno)."""

    from hdl_sim.engine.evaluator import EvaluationError
    from hdl_sim.parser.loader import VerilogSyntaxError

    if isinstance(exc, FileNotFoundError):
        summarized = summarize_client_error(str(exc))
        return summarized if isinstance(summarized, str) else "request failed"
    if isinstance(exc, (VerilogSyntaxError, EvaluationError, ValueError)):
        text = str(exc)
        if looks_like_os_leak(text):
            return "request failed"
        if isinstance(exc, VerilogSyntaxError):
            return text
        summarized = summarize_client_error(text)
        return summarized if isinstance(summarized, str) else "request failed"
    return "request failed"
