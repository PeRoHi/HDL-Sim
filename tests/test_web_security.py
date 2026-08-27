"""Local Web API jail, loopback Host/Origin, and CORS (no wildcard)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hdl_sim.engine.simulator import Simulator
from hdl_sim.parser.loader import load_design_with_meta
from hdl_sim.web.app import SourceFile, create_app, load_design_from_files
from hdl_sim.web.local_http import (
    host_is_loopback,
    local_api_rejection,
    loopback_origins,
    origin_is_allowed,
)
from hdl_sim.web import spj_store


def _loopback_headers(origin: str | None = "http://127.0.0.1:8765") -> dict[str, str]:
    headers = {"Host": "127.0.0.1:8765"}
    if origin is not None:
        headers["Origin"] = origin
    return headers


def test_host_and_origin_gate() -> None:
    assert host_is_loopback("127.0.0.1:8765")
    assert host_is_loopback("localhost:8765")
    assert host_is_loopback("[::1]:8765")
    assert not host_is_loopback("evil.example:8765")
    assert not host_is_loopback("127.0.0.1")
    assert not host_is_loopback("127.0.0.1:80")
    assert origin_is_allowed(None)
    assert origin_is_allowed("http://127.0.0.1:8765")
    assert not origin_is_allowed("null")
    assert not origin_is_allowed("http://evil.example:8765")
    assert local_api_rejection("127.0.0.1:8765", None) is None
    assert local_api_rejection("127.0.0.1:8765", "null") == "invalid origin"
    assert local_api_rejection("evil.example:8765", None) == "invalid host"


def test_cors_is_not_wildcard() -> None:
    origins = loopback_origins()
    assert "*" not in origins
    assert "http://127.0.0.1:8765" in origins
    app = create_app()
    cors = None
    for middleware in app.user_middleware:
        cls = getattr(middleware, "cls", None)
        if cls is not None and cls.__name__ == "CORSMiddleware":
            cors = middleware
            break
    assert cors is not None
    kwargs = getattr(cors, "kwargs", {}) or getattr(cors, "options", {})
    allow = kwargs.get("allow_origins") or []
    assert "*" not in allow
    assert kwargs.get("allow_credentials") is False


def test_http_rejects_non_loopback_host_and_null_origin() -> None:
    httpx = pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    app = create_app()
    client = TestClient(app, base_url="http://127.0.0.1:8765")
    bad_host = client.post(
        "/api/save_v_file",
        json={"project_name": "demo", "file_name": "a.v", "source": "module a; endmodule\n"},
        headers={"Host": "evil.example:8765", "Origin": "http://127.0.0.1:8765"},
    )
    assert bad_host.status_code == 403
    null_origin = client.post(
        "/api/save_v_file",
        json={"project_name": "demo", "file_name": "a.v", "source": "module a; endmodule\n"},
        headers=_loopback_headers("null"),
    )
    assert null_origin.status_code == 403
    health = client.get("/api/health", headers={"Host": "127.0.0.1:8765"})
    assert health.status_code == 200


def test_save_v_file_and_spj_reject_traversal(tmp_path, monkeypatch) -> None:
    from fastapi import HTTPException

    monkeypatch.setattr("hdl_sim.web.paths.user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("hdl_sim.web.spj_store.user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("hdl_sim.web.app.user_data_dir", lambda: tmp_path)
    (tmp_path / "spj").mkdir()

    app = create_app()
    save_v = next(r for r in app.routes if getattr(r, "path", None) == "/api/save_v_file").endpoint
    ok = save_v({"project_name": "demo", "file_name": "lib/a.v", "source": "module a; endmodule\n"})
    assert ok["ok"] is True
    assert ok["path"] == "verilog_sources/demo/lib/a.v"
    written = tmp_path / "verilog_sources" / "demo" / "lib" / "a.v"
    assert written.is_file()
    assert ".." not in ok["path"]

    with pytest.raises(HTTPException) as escaped:
        save_v({"project_name": "demo", "file_name": "../escape.v", "source": "x"})
    assert escaped.value.status_code == 400

    with pytest.raises(HTTPException):
        save_v({"project_name": "..", "file_name": "a.v", "source": "x"})

    with pytest.raises(ValueError):
        spj_store.save_spj_file(
            "demo.spj",
            {"files": [{"path": "../escape.v", "content": "module x; endmodule\n"}]},
        )


def test_legacy_spj_rejects_dotdot(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("hdl_sim.web.paths.user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("hdl_sim.web.spj_store.user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("hdl_sim.web.spj_store.spj_dir", lambda: tmp_path / "spj")
    (tmp_path / "spj").mkdir()
    secret = tmp_path / "secret.v"
    secret.write_text("module secret; endmodule\n", encoding="utf-8")
    (tmp_path / "spj" / "escape.spj").write_text(
        '{"files": ["../secret.v"], "project": {"name": "escape"}}',
        encoding="utf-8",
    )
    app = create_app()
    load = next(
        r
        for r in app.routes
        if getattr(r, "path", None) == "/api/spj/{filename}"
        and "GET" in getattr(r, "methods", set())
    ).endpoint
    with pytest.raises(Exception):
        load("escape.spj")
    # The secret file must not be returned as design source.
    # (handler raises HTTPException or ValueError depending on call style)


def test_load_design_from_files_rejects_absolute_and_dotdot(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_design_from_files(
            [SourceFile(path="/etc/passwd", content="module x; endmodule\n")]
        )
    with pytest.raises(ValueError):
        load_design_from_files(
            [SourceFile(path="../outside.v", content="module x; endmodule\n")]
        )
    loaded, base, tmp = load_design_from_files(
        [SourceFile(path="lib/and2.v", content="module and2; endmodule\n")]
    )
    tmp.cleanup()
    assert loaded.design.modules[0].name == "and2"


def test_include_does_not_read_outside_search_dir(tmp_path: Path) -> None:
    secret = tmp_path / "secret.v"
    secret.write_text("module stolen; endmodule\n", encoding="utf-8")
    src_dir = tmp_path / "rtl"
    src_dir.mkdir()
    top = src_dir / "top.v"
    top.write_text(
        """
        module top;
          `include "../secret.v"
        endmodule
        """,
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError):
        load_design_with_meta([top], include_paths=[src_dir])


def test_dumpfile_absolute_rejected_when_anchored(tmp_path: Path) -> None:
    escape = tmp_path.parent / "hdl_sim_should_not_write.vcd"
    if escape.exists():
        escape.unlink()
    vcd = tmp_path / "wave.vcd"
    sim = Simulator.from_source(
        f"""
        module t;
          initial begin
            $dumpfile("{escape.as_posix()}");
            $dumpvars;
            $finish;
          end
        endmodule
        """,
        vcd_path=vcd,
        vcd_anchor=tmp_path,
    )
    with pytest.raises(ValueError, match="dumpfile"):
        sim.run(until=1, max_events=20)
    assert not escape.exists()


def test_internal_error_does_not_echo_traceback(monkeypatch) -> None:
    from hdl_sim.web import app as app_module

    def boom(*_args, **_kwargs):
        raise RuntimeError("secret internals")

    monkeypatch.setattr(app_module, "elaborate", boom)
    app = create_app()
    handler = next(r for r in app.routes if getattr(r, "path", None) == "/api/elaborate").endpoint
    from hdl_sim.web.app import ElaborateRequest

    data = handler(
        ElaborateRequest(files=[SourceFile(path="tb.v", content="module tb; endmodule\n")])
    )
    assert data["ok"] is False
    assert data["error_kind"] == "internal"
    assert "trace" not in data
    assert "secret internals" not in str(data.get("error", ""))
