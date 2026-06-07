"""Small desktop launcher window (Windows-friendly, no terminal)."""

from __future__ import annotations

import sys

from hdl_sim import __version__
from hdl_sim.web.launcher import (
    DEFAULT_PORT,
    RunningServer,
    dependency_help,
    install_dependencies,
    is_frozen,
    missing_dependencies,
    open_browser_later,
    open_ui_window,
    start_server,
)
from hdl_sim.web.crash_log import write_crash_log
from hdl_sim.web.native_window import pywebview_available, pywebview_help
from hdl_sim.web.paths import install_dir, ui_dir
from hdl_sim.web.runtime import ensure_stdio, prepare_runtime

tk = messagebox = scrolledtext = ttk = None  # lazy-loaded for dev GUI only


def _load_tk():
    global tk, messagebox, scrolledtext, ttk
    if tk is None:
        import tkinter as _tk
        from tkinter import messagebox as _messagebox
        from tkinter import scrolledtext as _scrolledtext
        from tkinter import ttk as _ttk

        tk, messagebox, scrolledtext, ttk = _tk, _messagebox, _scrolledtext, _ttk
    return tk, messagebox, scrolledtext, ttk


class HDLSimGuiLauncher:
    def __init__(self, *, host: str = "127.0.0.1", port: int = 8765, native_window: bool = True) -> None:
        _load_tk()
        self.host = host
        self.port = port
        self.native_window = native_window
        self.server: RunningServer | None = None

        self.root = tk.Tk()
        self.root.title("HDL-Sim")
        self.root.geometry("460x320")
        self.root.minsize(420, 280)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.status = tk.StringVar(value="準備中...")
        self.url = tk.StringVar(value="")

        self._build()
        self.root.after(200, self.bootstrap)

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="HDL-Sim UI", font=("Segoe UI", 16, "bold")).pack(anchor=tk.W)
        ttk.Label(frame, text=f"Ver {__version__}", font=("Consolas", 10)).pack(anchor=tk.W, pady=(0, 4))
        ttk.Label(
            frame,
            text="Verilog を編集してシミュレーションできます。",
            wraplength=420,
        ).pack(anchor=tk.W, pady=(4, 12))

        ttk.Label(frame, textvariable=self.status, font=("Segoe UI", 11)).pack(anchor=tk.W)
        ttk.Label(frame, textvariable=self.url, foreground="#2563eb").pack(anchor=tk.W, pady=(4, 12))

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(0, 8))

        self.btn_open = ttk.Button(buttons, text="UI を開く", command=self.open_ui, state=tk.DISABLED)
        self.btn_open.pack(side=tk.LEFT)

        if pywebview_available():
            self.btn_window = ttk.Button(buttons, text="専用ウィンドウ", command=self.open_native, state=tk.DISABLED)
            self.btn_window.pack(side=tk.LEFT, padx=(8, 0))
        else:
            self.btn_window = None
            ttk.Label(
                frame,
                text="専用ウィンドウ: pip install pywebview",
                foreground="#666",
                font=("Segoe UI", 9),
            ).pack(anchor=tk.W, pady=(0, 4))

        self.btn_install = ttk.Button(buttons, text="依存関係をインストール", command=self.install_deps)
        if not is_frozen():
            self.btn_install.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_quit = ttk.Button(buttons, text="終了", command=self.on_close)
        self.btn_quit.pack(side=tk.RIGHT)

        ttk.Label(frame, text="ログ").pack(anchor=tk.W)
        self.log = scrolledtext.ScrolledText(frame, height=8, state=tk.DISABLED, font=("Consolas", 10))
        self.log.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

    def append_log(self, line: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, line + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def bootstrap(self) -> None:
        if is_frozen():
            self.append_log("同梱版: 依存関係チェックをスキップして起動します")
            self.start()
            return
        missing = missing_dependencies()
        if missing:
            self.status.set("初回セットアップが必要です")
            self.url.set(f"不足: {', '.join(missing)}")
            self.append_log(dependency_help())
            return
        self.start()

    def install_deps(self) -> None:
        self.btn_install.configure(state=tk.DISABLED)
        self.status.set("依存関係をインストール中...")
        self.append_log("pip install fastapi uvicorn lark")

        def _work() -> None:
            ok, output = install_dependencies(on_line=lambda line: self.root.after(0, self.append_log, line))
            self.root.after(0, self._after_install, ok, output)

        import threading

        threading.Thread(target=_work, daemon=True).start()

    def _after_install(self, ok: bool, output: str) -> None:
        if not ok:
            self.status.set("インストールに失敗しました")
            self.append_log(output)
            self.btn_install.configure(state=tk.NORMAL)
            messagebox.showerror("HDL-Sim", "依存関係のインストールに失敗しました。\n" + output[:500])
            return
        self.append_log("インストール完了")
        self.btn_install.configure(state=tk.DISABLED)
        self.start()

    def start(self) -> None:
        if self.server is not None:
            open_browser_later(self.server.url)
            return
        self.status.set("サーバーを起動しています...")
        ui_path = ui_dir().resolve()
        self.append_log(f"UI: {ui_path}")
        index = ui_path / "index.html"
        if index.is_file():
            text = index.read_text(encoding="utf-8")
            layout = "IDE" if "pane-explorer" in text else "legacy"
            self.append_log(f"Layout: {layout}")
        result = start_server(
            self.host,
            self.port,
            open_browser=not self.native_window,
            native_window=False,
            blocking=False,
            on_log=self.append_log,
        )
        if isinstance(result, int):
            self.status.set("起動に失敗しました")
            log_hint = install_dir() / "hdl-sim-server-error.log"
            msg = (
                "サーバーの起動に失敗しました。\n"
                f"下のログ欄と {log_hint} を確認してください。"
                if is_frozen()
                else dependency_help()
            )
            messagebox.showerror("HDL-Sim", msg)
            return
        self.server = result
        self.status.set("起動しました")
        self.url.set(self.server.url)
        self.btn_open.configure(state=tk.NORMAL)
        if self.btn_window is not None:
            self.btn_window.configure(state=tk.NORMAL)
        self.append_log(f"URL: {self.server.url}")
        if self.server.port != DEFAULT_PORT:
            self.append_log(f"注意: 既定ポート {DEFAULT_PORT} 以外で起動しています")
        if self.native_window:
            self.root.after(100, self.open_native)

    def open_ui(self) -> None:
        if self.server is not None:
            open_browser_later(self.server.url)

    def open_native(self) -> None:
        if self.server is None:
            return
        if not pywebview_available():
            messagebox.showinfo("HDL-Sim", pywebview_help())
            return
        self.root.withdraw()
        try:
            open_ui_window(self.server.url, server=self.server, native=True, on_log=self.append_log)
        finally:
            self.on_close()

    def on_close(self) -> None:
        if self.server is not None:
            self.server.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_gui(*, host: str = "127.0.0.1", port: int = 8765, native_window: bool = True) -> None:
    _load_tk()
    HDLSimGuiLauncher(host=host, port=port, native_window=native_window).run()


def main() -> int:
    prepare_runtime()
    try:
        run_gui(native_window=True)
        return 0
    except Exception as exc:
        log_path = write_crash_log(exc, context="gui_launcher.main")
        _frozen_error(
            "HDL-Sim の起動に失敗しました。\n"
            f"{exc}\n\n"
            + (f"ログ: {log_path}" if log_path else "ログ: インストール先の hdl-sim-crash.log")
        )
        return 1


def run_frozen_desktop(*, host: str = "127.0.0.1", port: int = 8765) -> int:
    """PyInstaller .exe: start server and open the native IDE window directly."""

    ensure_stdio()
    result = start_server(
        host,
        port,
        open_browser=False,
        native_window=False,
        blocking=False,
    )
    if isinstance(result, int):
        _frozen_error("HDL-Sim の起動に失敗しました。")
        return result

    if pywebview_available():
        try:
            open_ui_window(result.url, server=result, native=True)
            return 0
        except Exception as exc:
            write_crash_log(exc, context="run_frozen_desktop.native_window")
            _frozen_error(
                f"専用ウィンドウを開けませんでした。\n{exc}\n\n"
                "WebView2 が未インストールの可能性があります。\n"
                "https://go.microsoft.com/fwlink/p/?LinkId=2124703\n\n"
                "ブラウザで開きます。"
            )

    open_browser_later(result.url)
    try:
        result.thread.join()
    except KeyboardInterrupt:
        result.stop()
    return 0


def _frozen_error(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("HDL-Sim", message)
        root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
