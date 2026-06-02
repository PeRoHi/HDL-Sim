"""Tests for crash log helper."""

from hdl_sim.web.crash_log import crash_log_paths, write_crash_log


def test_crash_log_paths_returns_list() -> None:
    assert isinstance(crash_log_paths(), list)


def test_write_crash_log_writes_file() -> None:
    path = write_crash_log(RuntimeError("demo"), context="test")
    if path is not None:
        assert path.is_file()
        assert "test" in path.read_text(encoding="utf-8")
