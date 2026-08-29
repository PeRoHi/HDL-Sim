"""Port helpers: detect listeners and free the default HDL-Sim UI port."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

DEFAULT_UI_PORT = 8765

# Command-line tokens that identify this app (dev Python or frozen exe).
_OURS_TOKENS = ("python", "hdl-sim", "hdl_sim", "hdlsim")


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
        return True


def parse_pid(raw: str) -> int | None:
    """Accept only a positive integer written as digits (no sign, no spaces)."""

    text = str(raw).strip()
    if not text.isdigit():
        return None
    pid = int(text)
    if pid <= 0:
        return None
    return pid


def local_listen_port(local: str) -> int | None:
    """Return the TCP port from a netstat local-address field.

    Exact match only: ``127.0.0.1:18765`` is not port 8765.
    Supports ``host:port`` and ``[ipv6]:port``.
    """

    text = (local or "").strip()
    if not text:
        return None
    if text.startswith("["):
        end = text.find("]")
        if end < 0:
            return None
        rest = text[end + 1 :]
        if rest.startswith(":") and rest[1:].isdigit():
            return int(rest[1:])
        return None
    if ":" not in text:
        return None
    port_s = text.rsplit(":", 1)[-1]
    if not port_s.isdigit():
        return None
    return int(port_s)


def parse_netstat_listening_pids(stdout: str, port: int) -> list[int]:
    """Parse ``netstat -ano`` text for PIDs listening on *port* exactly."""

    pids: set[int] = set()
    for line in stdout.splitlines():
        if "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        if local_listen_port(parts[1]) != port:
            continue
        pid = parse_pid(parts[-1])
        if pid is not None:
            pids.add(pid)
    return sorted(pids)


def listener_pids(port: int) -> list[int]:
    if sys.platform == "win32":
        return _listener_pids_windows(port)
    return _listener_pids_unix(port)


def _listener_pids_windows(port: int) -> list[int]:
    try:
        proc = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    return parse_netstat_listening_pids(proc.stdout, port)


def _listener_pids_unix(port: int) -> list[int]:
    for cmd in (
        ["ss", "-ltnp", f"sport = :{port}"],
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
    ):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except OSError:
            continue
        pids: set[int] = set()
        for line in proc.stdout.splitlines():
            if "pid=" in line:
                for chunk in line.split(","):
                    chunk = chunk.strip()
                    if chunk.startswith("pid="):
                        pid = parse_pid(chunk[4:])
                        if pid is not None:
                            pids.add(pid)
            parts = line.split()
            if parts:
                pid = parse_pid(parts[-1])
                if pid is not None:
                    pids.add(pid)
        if pids:
            return sorted(pids)
    return []


def command_looks_like_ours(text: str) -> bool:
    lowered = (text or "").lower()
    return any(token in lowered for token in _OURS_TOKENS)


def pid_looks_like_python(pid: int) -> bool:
    """True when *pid* looks like this app (Python or frozen HDL-Sim).

    Fail closed: if the process cannot be inspected, do not treat it as ours.
    Windows liveness uses tasklist, never ``os.kill(pid, 0)``.
    """

    if not isinstance(pid, int) or pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return False
        return command_looks_like_ours(proc.stdout)
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", errors="ignore")
        return command_looks_like_ours(cmdline)
    except OSError:
        pass
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return command_looks_like_ours(proc.stdout)


def kill_pid(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            proc = subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                text=True,
                check=False,
            )
            return proc.returncode == 0
        import os
        import signal

        os.kill(pid, signal.SIGTERM)
        return True
    except OSError:
        return False


def release_port(
    port: int,
    *,
    on_log: Callable[[str], None] | None = None,
    only_python: bool = True,
) -> list[int]:
    """Stop processes listening on *port*. Returns PIDs that were killed."""

    killed: list[int] = []
    for pid in listener_pids(port):
        if only_python and not pid_looks_like_python(pid):
            if on_log:
                on_log(f"port {port}: skip non-python PID {pid}")
            continue
        if kill_pid(pid):
            killed.append(pid)
            if on_log:
                on_log(f"port {port}: stopped PID {pid}")
    if killed:
        time.sleep(0.4)
    return killed


def ensure_default_port(
    host: str = "127.0.0.1",
    port: int = DEFAULT_UI_PORT,
    *,
    on_log: Callable[[str], None] | None = None,
) -> int:
    """Always prefer *port*; stop stale listeners so the latest UI code is served."""

    if port_is_free(host, port):
        return port
    if on_log:
        on_log(f"port {port} is busy — stopping previous HDL-Sim server...")
    release_port(port, on_log=on_log)
    if port_is_free(host, port):
        return port
    raise OSError(
        f"Port {port} is still in use. Close other HDL-Sim windows or run:\n"
        f"  netstat -ano | findstr :{port}"
    )


def probe_hdl_sim_url(host: str, port: int, *, timeout: float = 0.8) -> dict | None:
    url = f"http://{host}:{port}/api/ui-info"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def wait_for_server(
    host: str,
    port: int,
    *,
    timeout: float = 15.0,
    interval: float = 0.15,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if probe_hdl_sim_url(host, port, timeout=0.5) is not None:
            return True
        time.sleep(interval)
    return False
