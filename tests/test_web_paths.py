"""Tests for user data directory resolution."""

from hdl_sim.web import paths


def test_user_data_dir_dev_uses_project_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(paths, "install_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "_read_data_dir_override", lambda: None)
    monkeypatch.setattr(paths.sys, "frozen", False, raising=False)

    data = paths.user_data_dir()
    assert data == tmp_path


def test_user_data_dir_reads_override(tmp_path, monkeypatch) -> None:
    override = tmp_path / "my-data"
    cfg = tmp_path / "data_dir.txt"
    cfg.write_text(str(override) + "\n", encoding="utf-8")

    monkeypatch.setattr(paths, "install_dir", lambda: tmp_path)

    data = paths.user_data_dir()
    assert data == override
    assert data.is_dir()
