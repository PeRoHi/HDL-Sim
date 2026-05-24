"""Friendly launcher for the HDL-Sim browser UI."""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from hdl_sim.web.paths import project_root

DEFAULT_PORT = 8765
REQUIRED_PACKAGES = ("fastapi", "uvicorn", "lark")


def ensure_src_on_path() -> None:
    if getattr(sys, "frozen", False):
        return
    src = project_root() / "src"
    src_s = str(src)
    if src.is_dir() and src_s not in sys.path:
        sys.path.insert(0, src_s)


def find_free_port(start: int = DEFAULT_PORT) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    return start


def missing_dependencies() -> list[str]:
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


def open_browser_later(url: str) -> None:
    def _open() -> None:
        webbrowser.open(url, new=2)

    threading.Timer(0.8, _open).start()


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
) -> RunningServer | int:
    ensure_src_on_path()
    port = find_free_port(port)
    url = f"http://{host}:{port}"
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

    thread = threading.Thread(target=_serve, daemon=True, name="hdl-sim-ui")
    thread.start()

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
