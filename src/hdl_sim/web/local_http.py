"""Loopback Host / Origin checks for the local Web UI.

CORS is not authentication. Destructive and file APIs must see:
- ``Host`` of loopback plus the UI port (default 8765)
- ``Origin`` absent (non-browser) or the same loopback origin
- ``Origin: null`` rejected

Assume: the UI is served at ``http://127.0.0.1:<port>/`` (launcher default
port 8765). Binding ``--host 0.0.0.0`` does not authorize LAN Host headers.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from hdl_sim.web.port_util import DEFAULT_UI_PORT

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_UI_PORT_ENV = "HDL_SIM_UI_PORT"


def expected_ui_port() -> int:
    raw = os.environ.get(_UI_PORT_ENV, str(DEFAULT_UI_PORT))
    try:
        port = int(raw)
    except ValueError:
        return DEFAULT_UI_PORT
    if 1 <= port <= 65535:
        return port
    return DEFAULT_UI_PORT


def split_hostport(host_header: str) -> tuple[str, int | None]:
    text = (host_header or "").strip()
    if not text:
        raise ValueError("missing host")
    if text.startswith("["):
        end = text.find("]")
        if end < 0:
            raise ValueError("invalid host")
        name = text[1:end].lower()
        rest = text[end + 1 :]
        if rest == "":
            return name, None
        if rest.startswith(":") and rest[1:].isdigit():
            return name, int(rest[1:])
        raise ValueError("invalid host")
    if ":" in text:
        name, port_s = text.rsplit(":", 1)
        if port_s.isdigit():
            return name.lower(), int(port_s)
    return text.lower(), None


def host_is_loopback(host_header: str, *, port: int | None = None) -> bool:
    try:
        name, parsed_port = split_hostport(host_header)
    except ValueError:
        return False
    if name not in LOOPBACK_HOSTS:
        return False
    expected = expected_ui_port() if port is None else port
    if parsed_port is None:
        return False
    return parsed_port == expected


def origin_is_allowed(origin: str | None, *, port: int | None = None) -> bool:
    """Return True when Origin is absent (non-browser) or a loopback UI origin."""

    if origin is None:
        return True
    text = origin.strip()
    if not text:
        return True
    if text.lower() == "null":
        return False
    parsed = urlparse(text)
    if parsed.scheme != "http":
        return False
    host = (parsed.hostname or "").lower()
    if host not in LOOPBACK_HOSTS:
        return False
    expected = expected_ui_port() if port is None else port
    origin_port = parsed.port if parsed.port is not None else 80
    return origin_port == expected


def loopback_origins(*, port: int | None = None) -> list[str]:
    expected = expected_ui_port() if port is None else port
    return [
        f"http://127.0.0.1:{expected}",
        f"http://localhost:{expected}",
        f"http://[::1]:{expected}",
    ]


def local_api_rejection(host_header: str | None, origin: str | None, *, port: int | None = None) -> str | None:
    """Return an error code if the request must be rejected, else None."""

    if not host_is_loopback(host_header or "", port=port):
        return "invalid host"
    if not origin_is_allowed(origin, port=port):
        return "invalid origin"
    return None
