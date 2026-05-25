"""Friendly launcher for the HDL-Sim browser UI."""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from hdl_sim.web.port_util import (
    DEFAULT_UI_PORT,
    ensure_default_port,
    port_is_free,
    release_port,
    wait_for_server,
)
from hdl_sim.web.paths import project_root

DEFAULT_PORT = DEFAULT_UI_PORT
REQUIRED_PACKAGES = ("fastapi", "uvicorn", "lark")


def is_frozen() -> bool:
    """True when running as a PyInstaller (or similar) bundled executable."""

    return getattr(sys, "frozen", False)


def ensure_src_on_path() -> None:
    if getattr(sys, "frozen", False):
        return
    src = project_root() / "src"
    src_s = str(src)
    if src.is_dir() and src_s not in sys.path:
        sys.path.insert(0, src_s)


def find_free_port(start: int = DEFAULT_PORT) -> int:
    """Return the first bindable port (legacy helper). Prefer ensure_default_port()."""

    for port in range(start, start + 50):
        if port_is_free("127.0.0.1", port):
            return port
    return start


def prepare_ui_port(
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    *,
    on_log: Callable[[str], None] | None = None,
) -> int:
    """Bind the default UI port, stopping stale python servers when needed."""

    return ensure_default_port(host, port, on_log=on_log)


def missing_dependencies() -> list[str]:
    if is_frozen():
        return []
    missing: list[str] = []
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package)
        except ModuleNotFoundError:
            missing.append(package)
    return missing


def dependency_help() -> str:
    return (
        "必要な Web UI 依存関係が見つかりません。\n"
        "次のコマンドを一度だけ実行してください:\n\n"
        "  python -m pip install fastapi uvicorn lark\n\n"
        "Windows では GUI 起動なら「依存関係をインストール」ボタンでも入れられます。"
    )


def install_dependencies(*, on_line: Callable[[str], None] | None = None) -> tuple[bool, str]:
    if is_frozen():
        msg = "PyInstaller 版では依存関係は同梱済みです（pip install は不要）。"
        if on_line is not None:
            on_line(msg)
        return True, msg
    cmd = [sys.executable, "-m", "pip", "install", *REQUIRED_PACKAGES]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return False, str(exc)
    output = (proc.stdout or "") + (proc.stderr or "")
    if on_line is not None:
        for line in output.splitlines():
            on_line(line)
    if proc.returncode != 0:
        return False, output.strip() or f"pip install failed with code {proc.returncode}"
    return True, output.strip()


def open_browser_later(url: str, *, delay: float = 0.3) -> None:
    import time

    stamp = int(time.time())
    open_url = f"{url.rstrip('/')}/?launch={stamp}"

    def _open() -> None:
        webbrowser.open(open_url, new=1)

    threading.Timer(delay, _open).start()


@dataclass(slots=True)
class RunningServer:
    host: str
    port: int
    url: str
    thread: threading.Thread
    server: object

    def stop(self) -> None:
        should_exit = getattr(self.server, "should_exit", None)
        if should_exit is not None:
            self.server.should_exit = True
        self.thread.join(timeout=5)


def start_server(
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    *,
    open_browser: bool = True,
    reload: bool = False,
    blocking: bool = True,
    on_log: Callable[[str], None] | None = None,
) -> RunningServer | int:
    ensure_src_on_path()
    try:
        port = prepare_ui_port(host, port, on_log=on_log)
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    url = f"http://{host}:{port}"
    if not is_frozen():
        missing = missing_dependencies()
        if missing:
            print(dependency_help(), file=sys.stderr)
            print(f"Missing: {', '.join(missing)}", file=sys.stderr)
            return 2

    import uvicorn

    config = uvicorn.Config(
        "hdl_sim.web.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
    server = uvicorn.Server(config)

    def _serve() -> None:
        server.run()

    thread = threading.Thread(target=_serve, daemon=False, name="hdl-sim-ui")
    thread.start()

    if not wait_for_server(host, port):
        print(f"HDL-Sim server did not become ready on {url}", file=sys.stderr)
        server.should_exit = True
        thread.join(timeout=3)
        return 2

    if open_browser:
        open_browser_later(url)

    running = RunningServer(host=host, port=port, url=url, thread=thread, server=server)
    if blocking:
        print("=" * 58)
        print("HDL-Sim UI を起動します")
        print(f"ブラウザで開くURL: {url}")
        print("終了するには、この画面で Ctrl+C を押してください")
        print("=" * 58)
        try:
            thread.join()
        except KeyboardInterrupt:
            running.stop()
        return 0
    return running


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the HDL-Sim browser UI")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind (default: 8765)")
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser automatically")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload for development")
    parser.add_argument("--gui", action="store_true", help="Open the small GUI launcher (no terminal needed)")
    return parser


def run(
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    *,
    open_browser: bool = True,
    reload: bool = False,
    gui: bool = False,
) -> int:
    if gui:
        from hdl_sim.web.gui_launcher import run_gui

        run_gui(host=host, port=port)
        return 0
    result = start_server(
        host=host,
        port=port,
        open_browser=open_browser,
        reload=reload,
        blocking=True,
    )
    return int(result) if isinstance(result, int) else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(
        host=args.host,
        port=args.port,
        open_browser=not args.no_open,
        reload=args.reload,
        gui=args.gui,
    )


if __name__ == "__main__":
    raise SystemExit(main())
