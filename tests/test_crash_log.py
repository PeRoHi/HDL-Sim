"""Tests for crash log helper."""

from hdl_sim.web.crash_log import crash_log_paths, should_write_crash_log, write_crash_log


def test_should_write_crash_log_skips_normal_exit() -> None:
    assert should_write_crash_log(SystemExit(0)) is False
    assert should_write_crash_log(SystemExit()) is False
    assert should_write_crash_log(KeyboardInterrupt()) is False
    assert should_write_crash_log(SystemExit(1)) is True
    assert should_write_crash_log(RuntimeError("x")) is True


def test_crash_log_paths_returns_list() -> None:
    assert isinstance(crash_log_paths(), list)


def test_write_crash_log_writes_file() -> None:
    path = write_crash_log(RuntimeError("demo"), context="test")
    if path is not None:
        assert path.is_file()
        assert "test" in path.read_text(encoding="utf-8")
