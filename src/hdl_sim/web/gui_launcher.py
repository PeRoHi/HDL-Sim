"""Small desktop launcher window (Windows-friendly, no terminal)."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from hdl_sim import __version__
from hdl_sim.web.launcher import (
    DEFAULT_PORT,
    RunningServer,
    dependency_help,
    install_dependencies,
    is_frozen,
    missing_dependencies,
    open_browser_later,
    start_server,
)
from hdl_sim.web.paths import ui_dir


class HDLSimGuiLauncher:
    def __init__(self, *, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
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

        self.btn_open = ttk.Button(buttons, text="ブラウザを開く", command=self.open_browser, state=tk.DISABLED)
        self.btn_open.pack(side=tk.LEFT)

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
            open_browser=True,
            blocking=False,
            on_log=self.append_log,
        )
        if isinstance(result, int):
            self.status.set("起動に失敗しました")
            msg = (
                "サーバーの起動に失敗しました。ログを確認してください。"
                if is_frozen()
                else dependency_help()
            )
            messagebox.showerror("HDL-Sim", msg)
            return
        self.server = result
        self.status.set("起動しました")
        self.url.set(self.server.url)
        self.btn_open.configure(state=tk.NORMAL)
        self.append_log(f"URL: {self.server.url}")
        if self.server.port != DEFAULT_PORT:
            self.append_log(f"注意: 既定ポート {DEFAULT_PORT} 以外で起動しています")

    def open_browser(self) -> None:
        if self.server is not None:
            open_browser_later(self.server.url)

    def on_close(self) -> None:
        if self.server is not None:
            self.server.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_gui(*, host: str = "127.0.0.1", port: int = 8765) -> None:
    HDLSimGuiLauncher(host=host, port=port).run()


def main() -> int:
    run_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
