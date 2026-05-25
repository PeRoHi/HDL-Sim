"""Port helpers: detect listeners and free the default HDL-Sim UI port."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Callable

DEFAULT_UI_PORT = 8765


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
        return True


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
    suffix = f":{port}"
    pids: set[int] = set()
    for line in proc.stdout.splitlines():
        if "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local = parts[1]
        if not local.endswith(suffix):
            continue
        try:
            pids.add(int(parts[-1]))
        except ValueError:
            continue
    return sorted(pids)


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
                        try:
                            pids.add(int(chunk[4:]))
                        except ValueError:
                            pass
            parts = line.split()
            if parts and parts[-1].isdigit():
                pids.add(int(parts[-1]))
        if pids:
            return sorted(pids)
    return []


def pid_looks_like_python(pid: int) -> bool:
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
        return "python" in proc.stdout.lower()
    try:
        Path = __import__("pathlib").Path
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", errors="ignore")
        return "python" in cmdline.lower()
    except OSError:
        return True


def kill_pid(pid: int) -> bool:
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
