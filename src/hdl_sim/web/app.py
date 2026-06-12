"""FastAPI application: Silos-style browser UI for HDL-Sim."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import traceback
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.types import Scope
from pydantic import BaseModel, Field

from hdl_sim import __version__
from hdl_sim.engine.elaborator import elaborate
from hdl_sim.engine.simulator import Simulator
from hdl_sim.parser.ast import Design, Module, PortDirection
from hdl_sim.parser.loader import load_design_with_meta, read_verilog_text
from hdl_sim.web.vcd_json import parse_vcd_timeline, timeline_to_json

from hdl_sim.web.paths import examples_dir, ui_dir
from hdl_sim.web import projects as project_store
from hdl_sim.web import spj_store
from hdl_sim.web.update_checker import check_for_updates

UI_BUILD = "1.0.6"
_NO_CACHE_SUFFIXES = (".js", ".css", ".html", ".map")

# Multi-file projects (Silos-style: DUT + TB + lib in one workspace)
EXAMPLE_PROJECTS: dict[str, dict[str, Any]] = {
    "@project/counter": {
        "label": "Project: 4-bit counter (DUT + TB)",
        "files": ["project/counter_dut.v", "project/tb_counter.v"],
        "top": "tb_counter",
    },
    "@project/and_gate": {
        "label": "Project: AND gate (lib + TB)",
        "files": ["lib/and2.v", "tb_multi.v"],
        "top": "tb_multi",
    },
}

# Legacy single-key bundles (example id → file list)
EXAMPLE_BUNDLES: dict[str, list[str]] = {
    "tb_multi.v": ["lib/and2.v", "tb_multi.v"],
}

EXAMPLE_TOPS: dict[str, str] = {
    "tb_multi.v": "tb_multi",
    "project/tb_counter.v": "tb_counter",
    "silos_regression.v": "silos_regression_tb",
    "hierarchy.v": "tb",
}

_shared_waveform_state: dict[str, Any] = {}

class WaveformSyncRequest(BaseModel):
    waveform: dict[str, Any]
    filteredWaveform: dict[str, Any] | None = None
    selection: list[str] = Field(default_factory=list)
    order: list[str] = Field(default_factory=list)


class NoCacheStaticFiles(StaticFiles):
    """Serve UI assets without aggressive browser caching (dev-friendly)."""

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        if path.endswith(_NO_CACHE_SUFFIXES):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response


UI_DIR = ui_dir()
EXAMPLES_DIR = examples_dir()


class SourceFile(BaseModel):
    path: str = Field(description="Virtual path, e.g. tb.v")
    content: str
    include_only: bool = Field(
        default=False,
        description="Write to workspace for `include` but do not parse as a top-level module file",
    )


class ProjectCreateRequest(BaseModel):
    name: str
    top: str | None = None
    label: str | None = None


class ProjectSaveRequest(BaseModel):
    files: list[SourceFile]
    top: str | None = None
    label: str | None = None
    wave: dict[str, Any] | None = None


class ElaborateRequest(BaseModel):
    files: list[SourceFile]
    top: str | None = None


class SimulateRequest(BaseModel):
    files: list[SourceFile]
    top: str | None = None
    until: int | None = 15000
    max_events: int | None = 2000
    generate_vcd: bool = True


def resolve_top_module(design: Design, top: str | None) -> str:
    """Pick elaboration top; ignore stale UI values like ``tb`` when absent from design."""

    names = {m.name for m in design.modules}
    requested = (top or "").strip()
    if requested and requested in names:
        return requested

    for suffix in ("_tp", "_tb", "_test", "_testbench"):
        for module in design.modules:
            if module.name.endswith(suffix):
                return module.name

    for candidate in ("stimulus", "tb", "testbench", "top"):
        if candidate in names:
            return candidate

    by_instances = sorted(design.modules, key=lambda m: len(m.instances), reverse=True)
    if by_instances and by_instances[0].instances:
        return by_instances[0].name

    try:
        return design.top.name
    except ValueError:
        return design.modules[-1].name


def _port_dir_name(direction: PortDirection) -> str:
    return {
        PortDirection.INPUT: "input",
        PortDirection.OUTPUT: "output",
        PortDirection.INOUT: "inout",
    }[direction]


def _module_to_dict(module: Module) -> dict[str, Any]:
    return {
        "name": module.name,
        "parameters": [p.name for p in module.parameters],
        "ports": [
            {
                "name": p.name,
                "direction": _port_dir_name(p.direction),
            }
            for p in module.ports
        ],
        "declarations": [
            {"name": d.name, "kind": d.kind.name.lower()}
            for d in module.declarations
        ],
        "instances": [
            {
                "name": inst.instance_name,
                "module": inst.module_type,
                "connections": [
                    {"port": c.port, "signal": _expr_to_str(c.expr)}
                    for c in inst.connections
                ],
            }
            for inst in module.instances
        ],
        "initial_count": len(module.initial_blocks),
        "always_count": len(module.always_blocks),
    }


def _expr_to_str(expr: Any) -> str:
    from hdl_sim.parser.ast import BitSelect, IdentRef, IntLiteral, PartSelect

    if isinstance(expr, IdentRef):
        return expr.name
    if isinstance(expr, IntLiteral):
        return str(expr.value)
    if isinstance(expr, BitSelect):
        base = expr.signal
        if expr.word is not None:
            base = f"{base}[{_expr_to_str(expr.word)}]"
        return f"{base}[{_expr_to_str(expr.index)}]"
    if isinstance(expr, PartSelect):
        base = expr.signal
        if expr.word is not None:
            base = f"{base}[{_expr_to_str(expr.word)}]"
        return f"{base}[{_expr_to_str(expr.msb)}:{_expr_to_str(expr.lsb)}]"
    return str(expr)


def design_overview(design: Design) -> dict[str, Any]:
    return {
        "modules": [_module_to_dict(m) for m in design.modules],
        "module_names": [m.name for m in design.modules],
    }


def nets_overview(sim: Simulator) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, net in sorted(sim._nets.items()):
        parts = name.split(".")
        rows.append(
            {
                "name": name,
                "width": net.width,
                "kind": net.kind.name.lower(),
                "value": net.value,
                "x_mask": net.x_mask,
                "z_mask": net.z_mask,
                "path": parts,
            }
        )
    return rows


def _signal_path(path_prefix: str, name: str) -> str:
    return f"{path_prefix}{name}" if path_prefix else name


def suggested_sim_until(design: Design, *, top: str | None) -> int | None:
    """Heuristic default simulation stop time from top-level parameters."""

    from hdl_sim.engine.params import ParameterEvaluator

    modules = {m.name: m for m in design.modules}
    top_name = top or design.modules[0].name
    module = modules.get(top_name)
    if module is None:
        return None
    evaluator = ParameterEvaluator()
    try:
        evaluator.resolve_module_params(module.parameters)
    except Exception:
        return None
    step = evaluator.snapshot().get("STEP")
    if step is not None and step > 0:
        return step * 15
    return None


def simulation_time_hints(
    design: Design,
    *,
    top: str | None,
    stop_time: int,
    until: int | None,
) -> list[str]:
    """User-facing hints when until is shorter than bench timing."""

    suggested = suggested_sim_until(design, top=top)
    if suggested is None or until is None:
        return []
    if until >= suggested:
        return []
    if stop_time < until:
        return []
    return [
        f"Until={until} は短すぎる可能性があります（STEP ベンチなら Until≈{suggested} 以上を推奨）。"
        " クロック・リセットが動く前に停止していると波形がフラットに見えます。",
    ]


def hierarchy_tree(design: Design, *, top: str | None) -> dict[str, Any]:
    """Build a simple module/instance tree for the sidebar."""

    modules = {m.name: m for m in design.modules}
    top_name = top or design.modules[0].name
    if top_name not in modules:
        return {"name": top_name, "kind": "module", "children": []}

    def build(
        module_name: str,
        instance_label: str | None,
        *,
        path_prefix: str = "",
    ) -> dict[str, Any]:
        module = modules[module_name]
        label = instance_label or module_name
        children: list[dict[str, Any]] = []
        for port in module.ports:
            children.append(
                {
                    "name": port.name,
                    "kind": "port",
                    "direction": _port_dir_name(port.direction),
                    "signalPath": _signal_path(path_prefix, port.name),
                    "children": [],
                }
            )
        for decl in module.declarations:
            children.append(
                {
                    "name": decl.name,
                    "kind": decl.kind.name.lower(),
                    "signalPath": _signal_path(path_prefix, decl.name),
                    "children": [],
                }
            )
        for inst in module.instances:
            child_prefix = (
                f"{path_prefix}{inst.instance_name}."
                if path_prefix
                else f"{inst.instance_name}."
            )
            if inst.module_type in modules:
                children.append(build(inst.module_type, inst.instance_name, path_prefix=child_prefix))
            else:
                children.append(
                    {
                        "name": inst.instance_name,
                        "kind": "instance",
                        "module": inst.module_type,
                        "children": [],
                    }
                )
        return {"name": label, "kind": "module", "module": module_name, "children": children}

    return build(top_name, None)


def load_design_from_files(files: list[SourceFile]) -> tuple[Any, Path, tempfile.TemporaryDirectory[str]]:
    """Write virtual sources to a temp directory and load them."""

    tmp = tempfile.TemporaryDirectory(prefix="hdl_sim_ui_")
    base = Path(tmp.name)
    paths: list[Path] = []
    for item in files:
        path = base / item.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item.content, encoding="utf-8")
        if not item.include_only:
            paths.append(path)
    if not paths:
        msg = "no elaboration entry files (only include-only sources?)"
        raise ValueError(msg)
    loaded = load_design_with_meta(paths)
    return loaded, base, tmp


def _read_example_paths(rel_paths: list[str]) -> list[dict[str, str]]:
    root = EXAMPLES_DIR.resolve()
    files: list[dict[str, str]] = []
    for rel in rel_paths:
        path = (EXAMPLES_DIR / rel).resolve()
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"example file not found: {rel}")
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="example not found") from exc
        files.append(
            {
                "path": rel,
                "content": read_verilog_text(path),
                "source_path": str(path),
            }
        )
    return files


def _read_example_bundle(example_id: str) -> tuple[list[dict[str, str]], str | None]:
    """Load one example, including companion files for multi-file testbenches."""

    if example_id in EXAMPLE_PROJECTS:
        proj = EXAMPLE_PROJECTS[example_id]
        return _read_example_paths(proj["files"]), proj.get("top")

    rel_paths = EXAMPLE_BUNDLES.get(example_id, [example_id])
    top = EXAMPLE_TOPS.get(example_id)
    return _read_example_paths(rel_paths), top


def _project_member_paths() -> set[str]:
    members: set[str] = set()
    for proj in EXAMPLE_PROJECTS.values():
        members.update(proj["files"])
    for paths in EXAMPLE_BUNDLES.values():
        members.update(paths)
    return members


def create_app() -> FastAPI:
    app = FastAPI(title="HDL-Sim UI", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    import os
    import sys
    import time
    import asyncio

    last_ping_time = time.time()
    HEARTBEAT_TIMEOUT = 180.0

    @app.post("/api/waveform_sync")
    async def sync_waveform_state(req: WaveformSyncRequest):
        global _shared_waveform_state
        _shared_waveform_state = req.model_dump()
        return {"status": "ok"}

    @app.get("/api/waveform_sync")
    async def get_waveform_state():
        return _shared_waveform_state

    @app.post("/api/open_waveform_window")
    async def api_open_waveform_window():
        import sys
        is_native = "webview" in sys.modules
        if is_native:
            try:
                import webview
                if webview.windows and hasattr(webview.windows[0].js_api, "open_waveform_window"):
                    webview.windows[0].js_api.open_waveform_window("/assets/waveform.html")
                    return {"opened_native": True}
            except Exception:
                pass
        return {"opened_native": False}

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/ping")
    def ping() -> dict[str, str]:
        nonlocal last_ping_time
        last_ping_time = time.time()
        return {"status": "ok"}

    @app.on_event("startup")
    async def startup_event() -> None:
        async def heartbeat_watcher() -> None:
            nonlocal last_ping_time
            while True:
                await asyncio.sleep(5)
                if time.time() - last_ping_time > HEARTBEAT_TIMEOUT:
                    print(f"No ping received for {HEARTBEAT_TIMEOUT} seconds. Shutting down.", file=sys.stderr)
                    os._exit(0)
        asyncio.create_task(heartbeat_watcher())

    @app.get("/api/ui-info")
    def ui_info() -> dict[str, Any]:
        index_path = UI_DIR / "index.html"
        index_text = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""
        return {
            "version": __version__,
            "version_label": f"Ver {__version__}",
            "build": UI_BUILD,
            "ui_dir": str(UI_DIR.resolve()),
            "spj_dir": str(spj_store.spj_dir().resolve()),
            "data_dir": str(spj_store.spj_dir().resolve().parent),
            "release_url": "https://github.com/PeRoHi/HDL-Sim/releases/latest",
            "ide_layout": "pane-explorer" in index_text and "tb-btn" in index_text,
            "index_mtime": index_path.stat().st_mtime if index_path.is_file() else None,
        }

    @app.get("/api/update-check")
    def api_update_check(refresh: bool = False) -> dict[str, Any]:
        try:
            return check_for_updates(__version__, force_refresh=refresh)
        except Exception as exc:
            return {
                "ok": False,
                "current_version": __version__,
                "latest_version": __version__,
                "update_available": False,
                "release_url": "https://github.com/PeRoHi/HDL-Sim/releases/latest",
                "download_url": None,
                "error": str(exc),
            }

    @app.get("/api/examples")
    def list_examples() -> list[dict[str, Any]]:
        if not EXAMPLES_DIR.is_dir():
            return []
        items: list[dict[str, Any]] = []

        for pid, proj in EXAMPLE_PROJECTS.items():
            items.append(
                {
                    "id": pid,
                    "label": proj["label"],
                    "kind": "project",
                    "files": proj["files"],
                    "top": proj.get("top"),
                }
            )

        bundled = _project_member_paths()
        for path in sorted(EXAMPLES_DIR.rglob("*.v")):
            rel = path.relative_to(EXAMPLES_DIR).as_posix()
            if rel in bundled:
                continue
            items.append(
                {
                    "id": rel,
                    "label": rel,
                    "kind": "file",
                    "path": str(path),
                }
            )
        return items

    @app.get("/api/examples/{example_id:path}")
    def get_example(example_id: str) -> dict[str, Any]:
        files, top = _read_example_bundle(example_id)
        main_id = example_id
        if example_id in EXAMPLE_PROJECTS:
            main_id = EXAMPLE_PROJECTS[example_id]["files"][-1]
        main = next((f for f in files if f["path"] == main_id), files[-1])
        label = EXAMPLE_PROJECTS.get(example_id, {}).get("label", example_id)
        return {
            "id": example_id,
            "path": example_id,
            "label": label,
            "content": main["content"],
            "files": files,
            "top": top,
            "kind": "project" if example_id in EXAMPLE_PROJECTS else "file",
        }

    @app.get("/api/projects")
    def api_list_projects() -> list[dict[str, Any]]:
        try:
            return project_store.list_projects()
        except OSError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/projects")
    def api_create_project(req: ProjectCreateRequest) -> dict[str, Any]:
        try:
            return project_store.create_project(req.name, top=req.top, label=req.label)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_name}")
    def api_load_project(project_name: str) -> dict[str, Any]:
        try:
            return project_store.load_project(project_name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="project not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/projects/{project_name}")
    def api_save_project(project_name: str, req: ProjectSaveRequest) -> dict[str, Any]:
        if not req.files:
            raise HTTPException(status_code=400, detail="files required")
        try:
            payload = [{"path": f.path, "content": f.content} for f in req.files]
            return project_store.save_project(
                project_name,
                payload,
                top=req.top,
                label=req.label,
                wave=req.wave,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/spj/info")
    def api_spj_info() -> dict[str, Any]:
        try:
            return {
                "path": str(spj_store.spj_dir().resolve()),
                "files": spj_store.list_spj_files(),
            }
        except OSError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/spj/{filename}")
    def api_load_spj(filename: str) -> dict[str, Any]:
        try:
            loaded = spj_store.load_spj_file(filename)
            return {"filename": loaded["filename"], **loaded["data"]}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="spj file not found") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/spj/{filename}")
    def api_save_spj(filename: str, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("format") != "hdl-sim-project":
            raise HTTPException(status_code=400, detail="invalid spj format")
        if not payload.get("files"):
            raise HTTPException(status_code=400, detail="files required")
        try:
            saved = spj_store.save_spj_file(filename, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # 参照元 .v ファイルがある場合は、編集内容をその実ファイルにも書き戻す
        updated_sources: list[str] = []
        source_errors: list[str] = []
        for item in payload.get("files", []):
            source_path = item.get("source_path")
            content = item.get("content")
            if not source_path or content is None:
                continue
            try:
                target = Path(source_path)
                if not target.is_file():
                    source_errors.append(f"{item.get('path')}: 参照先が存在しません ({source_path})")
                    continue
                if read_verilog_text(target) != content:
                    target.write_text(content, encoding="utf-8")
                    updated_sources.append(str(target))
            except OSError as exc:
                source_errors.append(f"{item.get('path')}: 書き込み失敗 ({exc})")
        return {
            "ok": True,
            **saved,
            "updated_sources": updated_sources,
            "source_errors": source_errors,
        }

    def _error_payload(exc: Exception) -> dict[str, Any]:
        """設計側の誤りは原因メッセージのみ、内部エラーはトレース付きで返す。"""

        from hdl_sim.engine.evaluator import EvaluationError
        from hdl_sim.parser.loader import VerilogSyntaxError

        user_error = isinstance(
            exc, (VerilogSyntaxError, ValueError, FileNotFoundError, EvaluationError, KeyError)
        )
        payload: dict[str, Any] = {
            "ok": False,
            "error": str(exc) if not isinstance(exc, KeyError) else f"不明な参照: {exc}",
        }
        if isinstance(exc, VerilogSyntaxError):
            payload["error_kind"] = "syntax"
            payload["error_file"] = exc.file
            payload["error_line"] = exc.line
            payload["error_column"] = exc.column
        elif user_error:
            payload["error_kind"] = "design"
        else:
            payload["error_kind"] = "internal"
            payload["trace"] = traceback.format_exc()
        return payload

    @app.post("/api/elaborate")
    def api_elaborate(req: ElaborateRequest) -> dict[str, Any]:
        if not req.files:
            raise HTTPException(status_code=400, detail="files required")
        try:
            loaded, _base, _tmp = load_design_from_files(req.files)
            design = loaded.design
            requested_top = (req.top or "").strip() or None
            top = resolve_top_module(design, req.top)
            elaborated = elaborate(design, top=top)
            payload: dict[str, Any] = {
                "ok": True,
                "top": elaborated.top_module,
                "signal_names": sorted(elaborated.nets.keys()),
                "module_names": design_overview(design)["module_names"],
                "overview": design_overview(design),
                "hierarchy": hierarchy_tree(design, top=top),
                "net_count": len(elaborated.nets),
                "continuous_assigns": len(elaborated.continuous_assigns),
                "initial_blocks": len(elaborated.initial_blocks),
                "always_blocks": len(elaborated.always_blocks),
                "suggested_until": suggested_sim_until(design, top=top),
            }
            if requested_top and requested_top != top:
                payload["top_auto"] = top
                payload["top_requested"] = requested_top
            return payload
        except Exception as exc:
            return _error_payload(exc)

    @app.post("/api/simulate")
    def api_simulate(req: SimulateRequest) -> dict[str, Any]:
        if not req.files:
            raise HTTPException(status_code=400, detail="files required")
        try:
            loaded, base, _tmp = load_design_from_files(req.files)
            design = loaded.design
            requested_top = (req.top or "").strip() or None
            top = resolve_top_module(design, req.top)

            vcd_path = base / "wave.vcd" if req.generate_vcd else None
            sim = Simulator(
                design,
                top=top,
                timescale=loaded.timescale or "1ns",
                vcd_path=vcd_path,
            )
            console = io.StringIO()
            with contextlib.redirect_stdout(console):
                result = sim.run(until=req.until, max_events=req.max_events)

            waveform: dict[str, Any] | None = None
            vcd_text = ""
            vcd_read = vcd_path
            if (
                vcd_read is not None
                and not vcd_read.is_file()
                and result.vcd_path is not None
                and result.vcd_path.is_file()
            ):
                vcd_read = result.vcd_path
            if vcd_read is not None and vcd_read.is_file():
                vcd_text = vcd_read.read_text(encoding="utf-8")
                waveform = timeline_to_json(parse_vcd_timeline(vcd_text))

            payload = {
                "ok": True,
                "top_module": result.top_module,
                "top": top,
                "stop_time": result.stop_time,
                "events_processed": result.events_processed,
                "console": console.getvalue(),
                "vcd": vcd_text,
                "waveform": waveform,
                "signals": nets_overview(sim),
                "signal_names": sorted(sim._nets.keys()),
                "hierarchy": hierarchy_tree(design, top=top),
                "overview": design_overview(design),
                "module_names": design_overview(design)["module_names"],
                "files_loaded": [f.path for f in req.files],
                "suggested_until": suggested_sim_until(design, top=top),
                "hints": simulation_time_hints(
                    design,
                    top=top,
                    stop_time=result.stop_time,
                    until=req.until,
                ),
            }
            if requested_top and requested_top != top:
                payload["top_auto"] = top
                payload["top_requested"] = requested_top
            return payload
        except Exception as exc:
            return {**_error_payload(exc), "console": ""}

    if UI_DIR.is_dir():
        app.mount("/assets", NoCacheStaticFiles(directory=UI_DIR), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(
                UI_DIR / "index.html",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                },
            )

    return app


def main() -> int:
    from hdl_sim.web.launcher import main as launcher_main

    return launcher_main()


if __name__ == "__main__":
    raise SystemExit(main())
