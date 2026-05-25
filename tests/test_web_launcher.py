"""Tests for user-friendly UI launcher helpers."""

from hdl_sim.web import create_app
from hdl_sim.web.launcher import (
    build_parser,
    dependency_help,
    find_free_port,
    install_dependencies,
    is_frozen,
    missing_dependencies,
)
from hdl_sim.web.paths import examples_dir, project_root, ui_dir


def test_web_package_create_app_is_lazy_and_works() -> None:
    app = create_app()
    assert app.title == "HDL-Sim UI"


def test_launcher_parser_defaults() -> None:
    args = build_parser().parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8765
    assert args.no_open is False
    assert args.gui is False


def test_launcher_parser_gui_flag() -> None:
    args = build_parser().parse_args(["--gui"])
    assert args.gui is True


def test_find_free_port_returns_int() -> None:
    assert isinstance(find_free_port(8765), int)


def test_dependency_help_is_plain_language() -> None:
    text = dependency_help()
    assert "pip install" in text
    assert "fastapi" in text


def test_missing_dependencies_reports_list() -> None:
    missing = missing_dependencies()
    assert isinstance(missing, list)


def test_project_paths_exist_in_dev_tree() -> None:
    assert project_root().is_dir()
    assert ui_dir().is_dir()
    assert examples_dir().is_dir()


def test_missing_dependencies_skipped_when_frozen(monkeypatch) -> None:
    monkeypatch.setattr("hdl_sim.web.launcher.is_frozen", lambda: True)
    assert missing_dependencies() == []


def test_install_dependencies_skipped_when_frozen(monkeypatch) -> None:
    monkeypatch.setattr("hdl_sim.web.launcher.is_frozen", lambda: True)
    ok, msg = install_dependencies()
    assert ok is True
    assert "同梱" in msg or "bundled" in msg.lower() or "PyInstaller" in msg


def test_is_frozen_false_in_dev() -> None:
    assert is_frozen() is False
