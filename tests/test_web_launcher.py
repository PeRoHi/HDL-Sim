"""Tests for user-friendly UI launcher helpers."""

from hdl_sim.web import create_app
from hdl_sim.web.launcher import build_parser, dependency_help, find_free_port


def test_web_package_create_app_is_lazy_and_works() -> None:
    app = create_app()
    assert app.title == "HDL-Sim UI"


def test_launcher_parser_defaults() -> None:
    args = build_parser().parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8765
    assert args.no_open is False


def test_find_free_port_returns_int() -> None:
    assert isinstance(find_free_port(8765), int)


def test_dependency_help_is_plain_language() -> None:
    text = dependency_help()
    assert "pip install" in text
    assert "fastapi" in text
