"""Tests for UI port management."""

from __future__ import annotations

from unittest.mock import patch

from hdl_sim.web.port_util import (
    command_looks_like_ours,
    ensure_default_port,
    local_listen_port,
    parse_netstat_listening_pids,
    parse_pid,
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


def test_parse_pid_digits_only() -> None:
    assert parse_pid("1234") == 1234
    assert parse_pid("0") is None
    assert parse_pid("-1") is None
    assert parse_pid("+12") is None
    assert parse_pid("12a") is None
    assert parse_pid("") is None


def test_local_listen_port_is_exact() -> None:
    assert local_listen_port("127.0.0.1:8765") == 8765
    assert local_listen_port("0.0.0.0:18765") == 18765
    assert local_listen_port("[::1]:8765") == 8765
    assert local_listen_port("[::]:18765") == 18765
    assert local_listen_port("127.0.0.1:8765") != 18765
    assert local_listen_port("not-a-port") is None


def test_netstat_does_not_match_suffix_port() -> None:
    stdout = """
  TCP    127.0.0.1:8765         0.0.0.0:0              LISTENING       1111
  TCP    0.0.0.0:18765          0.0.0.0:0              LISTENING       2222
  TCP    [::1]:8765             [::]:0                 LISTENING       3333
  TCP    [::]:28765             [::]:0                 LISTENING       4444
  TCP    127.0.0.1:8765         0.0.0.0:0              LISTENING       notpid
"""
    assert parse_netstat_listening_pids(stdout, 8765) == [1111, 3333]
    assert parse_netstat_listening_pids(stdout, 18765) == [2222]
    assert parse_netstat_listening_pids(stdout, 28765) == [4444]


def test_command_looks_like_ours_includes_frozen_exe() -> None:
    assert command_looks_like_ours("C:\\\\Python\\\\python.exe")
    assert command_looks_like_ours("HDL-Sim.exe")
    assert command_looks_like_ours("/opt/hdl-sim/bin/hdl-sim-ui")
    assert not command_looks_like_ours("nginx.exe")
    assert not command_looks_like_ours("node")


def test_pid_looks_like_python_fail_closed_on_proc_error(monkeypatch) -> None:
    monkeypatch.setattr("hdl_sim.web.port_util.sys.platform", "linux")

    def boom(_self):
        raise OSError("no /proc")

    monkeypatch.setattr("pathlib.Path.read_bytes", boom)
    monkeypatch.setattr(
        "hdl_sim.web.port_util.subprocess.run",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("no ps")),
    )
    assert pid_looks_like_python(99999) is False


def test_pid_looks_like_python_rejects_non_positive() -> None:
    assert pid_looks_like_python(0) is False
    assert pid_looks_like_python(-3) is False
