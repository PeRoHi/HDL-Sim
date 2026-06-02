"""Tests for dev/frozen runtime helpers."""

import sys

from hdl_sim.web.runtime import bootstrap_import_path, ensure_stdio, is_frozen


def test_is_frozen_false_in_dev() -> None:
    assert is_frozen() is False


def test_ensure_stdio_restores_missing_streams(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    ensure_stdio()
    assert sys.stdout is not None
    assert sys.stderr is not None
    assert hasattr(sys.stdout, "write")


def test_bootstrap_import_path_is_idempotent() -> None:
    bootstrap_import_path()
    import hdl_sim

    assert hdl_sim.__version__
