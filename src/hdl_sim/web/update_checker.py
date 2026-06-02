"""Check GitHub Releases for newer HDL-Sim builds (works for installed exe too)."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

from hdl_sim import __version__

DEFAULT_REPO = "PeRoHi/HDL-Sim"
DEFAULT_RELEASES_URL = f"https://api.github.com/repos/{DEFAULT_REPO}/releases/latest"
CACHE_TTL_SEC = 300

_cache: dict[str, Any] = {"at": 0.0, "payload": None}


def normalize_version(raw: str) -> str:
    cleaned = raw.strip().lstrip("vV")
    match = re.match(r"(\d+(?:\.\d+)*)", cleaned)
    return match.group(1) if match else cleaned


def compare_versions(left: str, right: str) -> int:
    """Return 1 if left > right, -1 if left < right, 0 if equal."""

    def parts(value: str) -> list[int]:
        return [int(p) for p in normalize_version(value).split(".") if p.isdigit()]

    a = parts(left)
    b = parts(right)
    length = max(len(a), len(b))
    for i in range(length):
        da = a[i] if i < len(a) else 0
        db = b[i] if i < len(b) else 0
        if da > db:
            return 1
        if da < db:
            return -1
    return 0


def _fetch_latest_release(url: str = DEFAULT_RELEASES_URL, *, timeout: float = 8.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "HDL-Sim-UpdateChecker",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _pick_windows_asset(release: dict[str, Any]) -> str | None:
    """Prefer ZIP (primary distribution), then signed/unsigned Setup exe."""
    zip_url: str | None = None
    exe_url: str | None = None
    for asset in release.get("assets") or []:
        name = str(asset.get("name") or "")
        lower = name.lower()
        url = str(asset.get("browser_download_url") or "") or None
        if not url or "hdl-sim" not in lower:
            continue
        if lower.endswith(".zip"):
            zip_url = url
        elif lower.endswith(".exe") and ("setup" in lower or lower.startswith("hdl-sim")):
            exe_url = url
    return zip_url or exe_url


def check_for_updates(
    current_version: str | None = None,
    *,
    repo: str = DEFAULT_REPO,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Return update metadata; safe to call offline (update_available=False)."""

    current = normalize_version(current_version or __version__)
    base = {
        "ok": True,
        "current_version": current,
        "latest_version": current,
        "update_available": False,
        "release_url": f"https://github.com/{repo}/releases/latest",
        "download_url": None,
        "release_name": None,
        "published_at": None,
        "source": "cache",
        "error": None,
    }

    now = time.time()
    if not force_refresh and _cache["payload"] is not None and now - _cache["at"] < CACHE_TTL_SEC:
        cached = dict(_cache["payload"])
        cached["current_version"] = current
        cached["update_available"] = compare_versions(cached.get("latest_version", current), current) > 0
        cached["source"] = "cache"
        return cached

    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        release = _fetch_latest_release(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        result = dict(base)
        result["ok"] = False
        result["error"] = str(exc)
        return result

    tag = normalize_version(str(release.get("tag_name") or release.get("name") or current))
    download = _pick_windows_asset(release)
    html_url = str(release.get("html_url") or base["release_url"])

    result = {
        "ok": True,
        "current_version": current,
        "latest_version": tag,
        "update_available": compare_versions(tag, current) > 0,
        "release_url": html_url,
        "download_url": download,
        "release_name": release.get("name") or release.get("tag_name"),
        "published_at": release.get("published_at"),
        "source": "github",
        "error": None,
    }
    _cache["at"] = now
    _cache["payload"] = dict(result)
    return result
