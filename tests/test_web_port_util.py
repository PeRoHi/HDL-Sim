"""Tests for UI port management."""

from __future__ import annotations

from unittest.mock import patch

from hdl_sim.web.port_util import (
    ensure_default_port,
    pid_looks_like_python,
    port_is_free,
    release_port,
)


def test_port_is_free_localhost() -> None:
    assert isinstance(port_is_free("127.0.0.1", 58765), bool)


def test_ensure_default_port_uses_requested_port_when_free() -> None:
    with patch("hdl_sim.web.port_util.port_is_free", side_effect=[True]):
        assert ensure_default_port("127.0.0.1", 8765) == 8765


def test_ensure_default_port_stops_stale_listener() -> None:
    with patch("hdl_sim.web.port_util.port_is_free", side_effect=[False, True]):
        with patch("hdl_sim.web.port_util.release_port") as release:
            assert ensure_default_port("127.0.0.1", 8765) == 8765
            release.assert_called_once()


def test_release_port_skips_non_python(monkeypatch) -> None:
    monkeypatch.setattr("hdl_sim.web.port_util.listener_pids", lambda _p: [999])
    monkeypatch.setattr("hdl_sim.web.port_util.pid_looks_like_python", lambda _p: False)
    with patch("hdl_sim.web.port_util.kill_pid") as kill:
        assert release_port(8765) == []
        kill.assert_not_called()


def test_pid_looks_like_python_recognizes_frozen_build() -> None:
    fake_run = type(
        "R",
        (),
        {"stdout": '"HDL-Sim.exe","4242","Console","1","50,000 K"', "returncode": 0},
    )()
    with patch("hdl_sim.web.port_util.sys") as fake_sys:
        fake_sys.platform = "win32"
        with patch("hdl_sim.web.port_util.subprocess.run", return_value=fake_run):
            assert pid_looks_like_python(4242) is True
