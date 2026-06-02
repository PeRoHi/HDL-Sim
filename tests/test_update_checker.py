"""Tests for GitHub release update checker."""

from hdl_sim.web.update_checker import check_for_updates, compare_versions, normalize_version


def test_normalize_version_strips_v_prefix() -> None:
    assert normalize_version("v0.5.1") == "0.5.1"


def test_compare_versions() -> None:
    assert compare_versions("0.5.1", "0.5.0") > 0
    assert compare_versions("0.5.0", "0.5.1") < 0
    assert compare_versions("0.5.0", "0.5.0") == 0


def test_check_for_updates_uses_github_payload(monkeypatch) -> None:
    payload = {
        "tag_name": "v0.9.0",
        "name": "HDL-Sim 0.9.0",
        "html_url": "https://github.com/PeRoHi/HDL-Sim/releases/tag/v0.9.0",
        "published_at": "2026-01-01T00:00:00Z",
        "assets": [
            {"name": "HDL-Sim-Setup-0.9.0.exe", "browser_download_url": "https://example.com/setup.exe"},
        ],
    }

    monkeypatch.setattr("hdl_sim.web.update_checker._fetch_latest_release", lambda *a, **k: payload)
    monkeypatch.setattr("hdl_sim.web.update_checker._cache", {"at": 0.0, "payload": None})

    result = check_for_updates("0.5.0", force_refresh=True)
    assert result["ok"] is True
    assert result["latest_version"] == "0.9.0"
    assert result["update_available"] is True
    assert result["download_url"] == "https://example.com/setup.exe"


def test_check_for_updates_no_update_when_current(monkeypatch) -> None:
    payload = {"tag_name": "v0.5.0", "html_url": "https://example.com", "assets": []}
    monkeypatch.setattr("hdl_sim.web.update_checker._fetch_latest_release", lambda *a, **k: payload)
    monkeypatch.setattr("hdl_sim.web.update_checker._cache", {"at": 0.0, "payload": None})

    result = check_for_updates("0.5.0", force_refresh=True)
    assert result["update_available"] is False
