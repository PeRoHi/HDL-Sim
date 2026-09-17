"""Unit tests for path jail helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from hdl_sim.web.path_safety import (
    client_error_from_exception,
    ensure_under,
    join_under,
    normalize_project_stem,
    normalize_relpath,
    summarize_client_error,
)


def test_normalize_relpath_allows_nested_verilog() -> None:
    assert normalize_relpath("lib/and2.v") == "lib/and2.v"
    assert normalize_relpath("tb.v") == "tb.v"
    assert normalize_relpath(r"lib\\and2.v") == "lib/and2.v"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        ".",
        "..",
        "../secret.v",
        "a/../b.v",
        "/etc/passwd",
        "C:/Windows/secret.v",
        "//server/share",
        "foo\x00.v",
        "foo%00.v",
        "foo%0a.v",
        "foo%7f.v",
        "%2e%2e/secret.v",
        "%252e%252e/secret.v",
        "lib/%2e%2e/secret.v",
    ],
)
def test_normalize_relpath_rejects_escapes(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_relpath(raw)


def test_normalize_project_stem() -> None:
    assert normalize_project_stem("demo.spj") == "demo"
    assert normalize_project_stem("api_demo") == "api_demo"
    # Basename only: a dotted path cannot climb out of verilog_sources/.
    assert normalize_project_stem("../evil.spj") == "evil"
    with pytest.raises(ValueError):
        normalize_project_stem("..")
    with pytest.raises(ValueError):
        normalize_project_stem("bad name")


def test_iter_regular_files_skips_symlink_dirs(tmp_path: Path) -> None:
    from hdl_sim.web.path_safety import iter_regular_files

    root = tmp_path / "ex"
    outside = tmp_path / "out"
    root.mkdir()
    outside.mkdir()
    (root / "keep.v").write_text("module k; endmodule\n", encoding="utf-8")
    (outside / "secret.v").write_text("module s; endmodule\n", encoding="utf-8")
    linked = root / "linked"
    try:
        linked.symlink_to(outside)
    except OSError:
        pytest.skip("symlink not permitted")
    names = {p.name for p in iter_regular_files(root, suffix=".v")}
    assert names == {"keep.v"}


def test_join_under_rejects_symlink_escape(tmp_path: Path) -> None:
    jail = tmp_path / "jail"
    outside = tmp_path / "outside"
    jail.mkdir()
    outside.mkdir()
    secret = outside / "secret.v"
    secret.write_text("module x; endmodule\n", encoding="utf-8")
    link = jail / "link"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink not permitted")
    with pytest.raises(ValueError):
        join_under(jail, "link/secret.v")


def test_ensure_under_accepts_root_file(tmp_path: Path) -> None:
    dest = tmp_path / "a.v"
    dest.write_text("x", encoding="utf-8")
    assert ensure_under(tmp_path, dest) == dest.resolve()


def test_jailed_regular_file_rejects_symlink(tmp_path: Path) -> None:
    from hdl_sim.web.path_safety import jailed_regular_file, reject_symlink

    jail = tmp_path / "ui"
    outside = tmp_path / "outside.txt"
    jail.mkdir()
    outside.write_text("stolen", encoding="utf-8")
    (jail / "ok.html").write_text("<html></html>", encoding="utf-8")
    assert jailed_regular_file(jail, "ok.html").is_file()
    link = jail / "index.html"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink not permitted")
    with pytest.raises(ValueError):
        reject_symlink(link)
    with pytest.raises(ValueError):
        jailed_regular_file(jail, "index.html")


def test_atomic_write_replaces_regular_leftover_tmp(tmp_path: Path) -> None:
    from hdl_sim.web.path_safety import atomic_write_text

    dest = tmp_path / "proj.spj"
    leftover = dest.with_name(f".{dest.name}.{__import__('os').getpid()}.tmp")
    leftover.write_text("stale", encoding="utf-8")
    atomic_write_text(dest, "fresh")
    assert dest.read_text(encoding="utf-8") == "fresh"
    assert not leftover.exists()


def test_atomic_write_refuses_symlink_tmp(tmp_path: Path) -> None:
    from hdl_sim.web.path_safety import atomic_write_text
    import os

    dest = tmp_path / "proj.spj"
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
    try:
        tmp.symlink_to(outside)
    except OSError:
        pytest.skip("symlink not permitted")
    with pytest.raises(ValueError, match="symlink"):
        atomic_write_text(dest, "new")
    assert outside.read_text(encoding="utf-8") == "keep"
    assert tmp.is_symlink()


def test_read_text_nofollow_rejects_symlink(tmp_path: Path) -> None:
    from hdl_sim.web.path_safety import read_text_nofollow

    real = tmp_path / "real.txt"
    real.write_text("ok", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlink not permitted")
    assert read_text_nofollow(real) == "ok"
    with pytest.raises(ValueError, match="symlink"):
        read_text_nofollow(link)


def test_atomic_write_text_replaces_and_cleans_tmp(tmp_path: Path) -> None:
    from hdl_sim.web.path_safety import atomic_write_text

    dest = tmp_path / "proj.spj"
    dest.write_text("old", encoding="utf-8")
    atomic_write_text(dest, "new")
    assert dest.read_text(encoding="utf-8") == "new"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_atomic_write_refuses_empty_overwrite(tmp_path: Path) -> None:
    from hdl_sim.web.path_safety import atomic_write_text

    dest = tmp_path / "proj.spj"
    dest.write_text('{"ok": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        atomic_write_text(dest, "", refuse_empty=True)
    assert dest.read_text(encoding="utf-8") == '{"ok": true}'


def test_atomic_write_refuses_symlink_dest(tmp_path: Path) -> None:
    from hdl_sim.web.path_safety import atomic_write_text

    real = tmp_path / "real.spj"
    real.write_text("keep", encoding="utf-8")
    dest = tmp_path / "link.spj"
    try:
        dest.symlink_to(real)
    except OSError:
        pytest.skip("symlink not permitted")
    with pytest.raises(ValueError, match="symlink"):
        atomic_write_text(dest, "new")
    assert real.read_text(encoding="utf-8") == "keep"


def test_join_under_refuses_parent_symlink(tmp_path: Path) -> None:
    jail = tmp_path / "jail"
    outside = tmp_path / "outside"
    jail.mkdir()
    outside.mkdir()
    (outside / "secret.v").write_text("stolen", encoding="utf-8")
    parent = jail / "nested"
    try:
        parent.symlink_to(outside)
    except OSError:
        pytest.skip("symlink not permitted")
    with pytest.raises(ValueError):
        join_under(jail, "nested/secret.v")


def test_summarize_client_error_covers_arrays_and_os_leaks() -> None:
    assert summarize_client_error("invalid file path") == "invalid file path"
    assert summarize_client_error("[Errno 2] No such file: /tmp/secret") == "request failed"
    assert summarize_client_error(["ok", "[Errno 13] /home/user/x"]) == ["ok", "request failed"]
    assert client_error_from_exception(FileNotFoundError("/tmp/hdl_sim_ui_abc/x.v")) == "request failed"
    assert client_error_from_exception(ValueError("モジュール 'ghost' が見つかりません")) == (
        "モジュール 'ghost' が見つかりません"
    )
