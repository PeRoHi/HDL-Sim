"""FastAPI application: Silos-style browser UI for HDL-Sim."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import traceback
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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

UI_BUILD = "0.5.12"
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


class ElaborateRequest(BaseModel):
    files: list[SourceFile]
    top: str | None = None


class SimulateRequest(BaseModel):
    files: list[SourceFile]
    top: str | None = None
    until: int | None = 15000
    max_events: int | None = 2000
    generate_vcd: bool = True


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
    from hdl_sim.parser.ast import BitSelect, IdentRef, PartSelect

    if isinstance(expr, IdentRef):
        return expr.name
    if isinstance(expr, BitSelect):
        return f"{_expr_to_str(expr.base)}[{_expr_to_str(expr.index)}]"
    if isinstance(expr, PartSelect):
        return (
            f"{_expr_to_str(expr.base)}[{_expr_to_str(expr.msb)}:"
            f"{_expr_to_str(expr.lsb)}]"
        )
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
        files.append({"path": rel, "content": read_verilog_text(path)})
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

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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
            return {"ok": True, **saved}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/elaborate")
    def api_elaborate(req: ElaborateRequest) -> dict[str, Any]:
        if not req.files:
            raise HTTPException(status_code=400, detail="files required")
        try:
            loaded, _base, _tmp = load_design_from_files(req.files)
            design = loaded.design
            top = req.top or design.modules[-1].name
            elaborated = elaborate(design, top=top)
            return {
                "ok": True,
                "top": elaborated.top_module,
                "module_names": design_overview(design)["module_names"],
                "overview": design_overview(design),
                "hierarchy": hierarchy_tree(design, top=top),
                "net_count": len(elaborated.nets),
                "continuous_assigns": len(elaborated.continuous_assigns),
                "initial_blocks": len(elaborated.initial_blocks),
                "always_blocks": len(elaborated.always_blocks),
                "suggested_until": suggested_sim_until(design, top=top),
            }
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "trace": traceback.format_exc(),
            }

    @app.post("/api/simulate")
    def api_simulate(req: SimulateRequest) -> dict[str, Any]:
        if not req.files:
            raise HTTPException(status_code=400, detail="files required")
        try:
            loaded, base, _tmp = load_design_from_files(req.files)
            design = loaded.design
            top = req.top
            if top is None:
                top = design.modules[-1].name

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
            if vcd_path is not None and vcd_path.is_file():
                vcd_text = vcd_path.read_text(encoding="utf-8")
                waveform = timeline_to_json(parse_vcd_timeline(vcd_text))

            return {
                "ok": True,
                "top_module": result.top_module,
                "stop_time": result.stop_time,
                "events_processed": result.events_processed,
                "console": console.getvalue(),
                "vcd": vcd_text,
                "waveform": waveform,
                "signals": nets_overview(sim),
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
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "trace": traceback.format_exc(),
                "console": "",
            }

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
