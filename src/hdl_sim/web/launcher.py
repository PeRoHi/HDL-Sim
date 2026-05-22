"""Friendly launcher for the HDL-Sim browser UI."""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import webbrowser
from pathlib import Path


DEFAULT_PORT = 8765


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def ensure_src_on_path() -> None:
    src = project_root() / "src"
    src_s = str(src)
    if src_s not in sys.path:
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


def dependency_help() -> str:
    return (
        "必要な Web UI 依存関係が見つかりません。\n"
        "次のコマンドを一度だけ実行してください:\n\n"
        "  python3 -m pip install fastapi uvicorn lark pytest\n\n"
        "Windows の場合は `python`、macOS/Linux の場合は `python3` を使います。"
    )


def open_browser_later(url: str) -> None:
    def _open() -> None:
        webbrowser.open(url, new=2)

    threading.Timer(0.8, _open).start()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the HDL-Sim browser UI")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind (default: 8765)")
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser automatically")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload for development")
    return parser


def run(host: str = "127.0.0.1", port: int = DEFAULT_PORT, *, open_browser: bool = True, reload: bool = False) -> int:
    ensure_src_on_path()
    port = find_free_port(port)
    url = f"http://{host}:{port}"
    try:
        import uvicorn
    except ModuleNotFoundError:
        print(dependency_help(), file=sys.stderr)
        return 2

    print("=" * 58)
    print("HDL-Sim UI を起動します")
    print(f"ブラウザで開くURL: {url}")
    print("終了するには、この画面で Ctrl+C を押してください")
    print("=" * 58)
    if open_browser:
        open_browser_later(url)

    uvicorn.run(
        "hdl_sim.web.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(
        host=args.host,
        port=args.port,
        open_browser=not args.no_open,
        reload=args.reload,
    )


if __name__ == "__main__":
    raise SystemExit(main())
