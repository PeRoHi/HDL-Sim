"""Open HDL-Sim UI in a native desktop window via pywebview."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hdl_sim.web.launcher import RunningServer


def pywebview_available() -> bool:
    try:
        import webview  # noqa: F401

        return True
    except ImportError:
        return False


def pywebview_help() -> str:
    return (
        "専用ウィンドウには pywebview が必要です。\n"
        "次のコマンドを実行してください:\n\n"
        "  python -m pip install pywebview\n\n"
        "または:\n\n"
        "  python -m pip install hdl-sim[desktop]"
    )


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
    )

    def _on_closing() -> bool:
        if server is not None:
            server.stop()
        return True

    window.events.closing += _on_closing
    webview.start(debug=False)
