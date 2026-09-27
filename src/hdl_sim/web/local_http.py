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

from hdl_sim.path_jail import has_c0_del
from hdl_sim.web.port_util import DEFAULT_UI_PORT, parse_ascii_port

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_UI_PORT_ENV = "HDL_SIM_UI_PORT"


def listen_port_from_scope(server: object | None) -> int:
    """ASGI ``scope['server']`` port, else the configured UI port."""

    if isinstance(server, (tuple, list)) and len(server) >= 2 and server[1] is not None:
        try:
            port = int(server[1])
        except (TypeError, ValueError):
            port = 0
        if 1 <= port <= 65535:
            return port
    try:
        return expected_ui_port()
    except ValueError:
        return 0


def expected_ui_port() -> int:
    """Configured UI port. Unset env uses the default; an invalid value is an error."""

    if _UI_PORT_ENV not in os.environ:
        return DEFAULT_UI_PORT
    return parse_ascii_port(os.environ[_UI_PORT_ENV])


def split_hostport(host_header: str) -> tuple[str, int | None]:
    raw = host_header if isinstance(host_header, str) else ""
    if has_c0_del(raw):
        raise ValueError("invalid host")
    text = raw.strip()
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
        if rest.startswith(":"):
            return name, parse_ascii_port(rest[1:])
        raise ValueError("invalid host")
    if ":" in text:
        name, port_s = text.rsplit(":", 1)
        return name.lower(), parse_ascii_port(port_s)
    return text.lower(), None


def host_is_loopback(host_header: str, *, port: int | None = None) -> bool:
    try:
        name, parsed_port = split_hostport(host_header)
    except ValueError:
        return False
    if name not in LOOPBACK_HOSTS:
        return False
    try:
        expected = expected_ui_port() if port is None else port
    except ValueError:
        return False
    if parsed_port is None:
        return False
    return parsed_port == expected


def origin_is_allowed(origin: str | None, *, port: int | None = None) -> bool:
    """Return True when Origin is absent (non-browser) or a loopback UI origin."""

    if origin is None:
        return True
    if has_c0_del(origin):
        return False
    text = origin.strip()
    if not text:
        return True
    if text.lower() == "null":
        return False
    parsed = urlparse(text)
    if parsed.scheme != "http":
        return False
    netloc = parsed.netloc or ""
    if "@" in netloc:
        return False
    try:
        host, parsed_port = split_hostport(netloc)
    except ValueError:
        return False
    if host not in LOOPBACK_HOSTS:
        return False
    try:
        expected = expected_ui_port() if port is None else port
    except ValueError:
        return False
    origin_port = parsed_port if parsed_port is not None else 80
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
