"""FastAPI application: Silos-style browser UI for HDL-Sim."""

from __future__ import annotations

import contextlib
import io
import tempfile
import traceback
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from hdl_sim.engine.elaborator import elaborate
from hdl_sim.engine.simulator import Simulator
from hdl_sim.parser.ast import Design, Module, PortDirection
from hdl_sim.parser.loader import load_design_with_meta
from hdl_sim.web.vcd_json import parse_vcd_timeline, timeline_to_json

ROOT = Path(__file__).resolve().parents[3]
UI_DIR = ROOT / "ui"
EXAMPLES_DIR = ROOT / "examples"


class SourceFile(BaseModel):
    path: str = Field(description="Virtual path, e.g. tb.v")
    content: str


class ElaborateRequest(BaseModel):
    files: list[SourceFile]
    top: str | None = None


class SimulateRequest(BaseModel):
    files: list[SourceFile]
    top: str | None = None
    until: int | None = 50
    max_events: int | None = 500
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


def hierarchy_tree(design: Design, *, top: str | None) -> dict[str, Any]:
    """Build a simple module/instance tree for the sidebar."""

    modules = {m.name: m for m in design.modules}
    top_name = top or design.modules[0].name
    if top_name not in modules:
        return {"name": top_name, "kind": "module", "children": []}

    def build(module_name: str, instance_label: str | None) -> dict[str, Any]:
        module = modules[module_name]
        label = instance_label or module_name
        children: list[dict[str, Any]] = []
        for port in module.ports:
            children.append(
                {
                    "name": port.name,
                    "kind": "port",
                    "direction": _port_dir_name(port.direction),
                    "children": [],
                }
            )
        for decl in module.declarations:
            children.append(
                {
                    "name": decl.name,
                    "kind": decl.kind.name.lower(),
                    "children": [],
                }
            )
        for inst in module.instances:
            if inst.module_type in modules:
                children.append(build(inst.module_type, inst.instance_name))
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
        paths.append(path)
    loaded = load_design_with_meta(paths)
    return loaded, base, tmp


def create_app() -> FastAPI:
    app = FastAPI(title="HDL-Sim UI", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/examples")
    def list_examples() -> list[dict[str, str]]:
        if not EXAMPLES_DIR.is_dir():
            return []
        items: list[dict[str, str]] = []
        for path in sorted(EXAMPLES_DIR.rglob("*.v")):
            rel = path.relative_to(EXAMPLES_DIR).as_posix()
            items.append(
                {
                    "id": rel,
                    "label": rel,
                    "path": str(path),
                }
            )
        return items

    @app.get("/api/examples/{example_id:path}")
    def get_example(example_id: str) -> dict[str, str]:
        root = EXAMPLES_DIR.resolve()
        path = (EXAMPLES_DIR / example_id).resolve()
        if not path.is_file():
            raise HTTPException(status_code=404, detail="example not found")
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="example not found") from exc
        return {
            "id": example_id,
            "path": example_id,
            "content": path.read_text(encoding="utf-8"),
        }

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
                "overview": design_overview(design),
                "hierarchy": hierarchy_tree(design, top=top),
                "net_count": len(elaborated.nets),
                "continuous_assigns": len(elaborated.continuous_assigns),
                "initial_blocks": len(elaborated.initial_blocks),
                "always_blocks": len(elaborated.always_blocks),
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
            }
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "trace": traceback.format_exc(),
                "console": "",
            }

    if UI_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=UI_DIR), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(UI_DIR / "index.html")

    return app


def main() -> int:
    import uvicorn

    uvicorn.run(
        "hdl_sim.web.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8765,
        reload=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
