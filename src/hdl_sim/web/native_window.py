"""Open HDL-Sim UI in a native desktop window via pywebview."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hdl_sim.web.launcher import RunningServer


def pywebview_available() -> bool:
    try:
        import webview  # noqa: F401

        import sys
        if sys.platform == "win32":
            import clr  # noqa: F401

        return True
    except Exception:
        return False


def pywebview_help() -> str:
    return (
        "専用ウィンドウには pywebview が必要です。\n"
        "次のコマンドを実行してください:\n\n"
        "  python -m pip install pywebview\n\n"
        "または:\n\n"
        "  python -m pip install hdl-sim[desktop]"
    )


class NativeApi:
    def pick_files(self) -> list[dict]:
        import webview
        from pathlib import Path
        from hdl_sim.web.paths import project_root
        
        if not webview.windows:
            return []
            
        window = webview.windows[0]
        result = window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            directory=str(project_root()),
            file_types=('Verilog Files (*.v;*.sv;*.vh;*.svh)', 'All Files (*.*)')
        )
        if not result:
            return []
            
        files = []
        for p in result:
            path = Path(p)
            try:
                files.append({"name": path.name, "content": path.read_text(encoding="utf-8")})
            except Exception:
                pass
        return files

    def pick_spj_file(self) -> dict | None:
        import webview
        from pathlib import Path
        from hdl_sim.web.paths import user_data_dir
        
        if not webview.windows:
            return None
            
        window = webview.windows[0]
        spj_dir = user_data_dir() / "spj"
        result = window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            directory=str(spj_dir if spj_dir.exists() else user_data_dir()),
            file_types=('SPJ Files (*.spj)', 'All Files (*.*)')
        )
        if not result:
            return None
            
        path = Path(result[0])
        try:
            return {"name": path.name, "content": path.read_text(encoding="utf-8")}
        except Exception:
            return None


def open_native_window(
    url: str,
    *,
    title: str = "HDL-Sim",
    width: int = 1280,
    height: int = 820,
    min_size: tuple[int, int] = (800, 500),
    server: RunningServer | None = None,
) -> None:
    """Block until the native window is closed."""

    import webview

    window = webview.create_window(
        title,
        url,
        width=width,
        height=height,
        min_size=min_size,
        js_api=NativeApi(),
    )

    def _on_closing() -> bool:
        if server is not None:
            server.stop()
        return True

    window.events.closing += _on_closing
    try:
        webview.start(debug=False)
    except Exception as e:
        import sys
        print(f"Warning: webview.start failed: {e}", file=sys.stderr)
        raise
